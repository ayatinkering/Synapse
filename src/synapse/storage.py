"""SQLite is authoritative; files are rebuildable renderings of saved outputs."""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
from uuid import UUID

from synapse.models import (
    TERMINAL,
    Analysis,
    Critique,
    Discovery,
    Event,
    Model,
    Report,
    Run,
    Snapshot,
    State,
    SynthesisConfig,
    SynthesisRecord,
    now,
)


class ServiceError(Exception):
    """A safe, user-facing error code, never an arbitrary adapter traceback."""


def fingerprint(run: Run) -> str:
    request = {
        "kind": run.kind,
        "fixture_id": run.fixture_id,
        "input": run.input.model_dump(mode="json"),
        "limits": run.limits.model_dump(mode="json"),
    }
    return sha256(json.dumps(request, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class Store:
    def __init__(self, directory: Path) -> None:
        self.path = directory / "synapse.sqlite3"
        with self.connection() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > 3:
                raise ServiceError("SCHEMA_UNSUPPORTED: Database requires a newer application.")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, request_key TEXT UNIQUE NOT NULL,
                    fixture_id TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS stage_outputs (
                    run_id TEXT NOT NULL REFERENCES runs(id), stage TEXT NOT NULL,
                    payload TEXT NOT NULL, PRIMARY KEY(run_id, stage));
                CREATE TABLE IF NOT EXISTS events (
                    run_id TEXT NOT NULL REFERENCES runs(id), sequence INTEGER NOT NULL,
                    payload TEXT NOT NULL, PRIMARY KEY(run_id, sequence));

            """)
            if version < 2:
                db.execute("BEGIN IMMEDIATE")
                db.execute("ALTER TABLE runs RENAME COLUMN fixture_id TO request_fingerprint")
                for run_id, payload in db.execute("SELECT id, payload FROM runs").fetchall():
                    db.execute(
                        "UPDATE runs SET request_fingerprint=? WHERE id=?",
                        (fingerprint(Run.model_validate_json(payload)), run_id),
                    )
            if version < 3:
                if version >= 2:
                    db.execute("BEGIN IMMEDIATE")
                db.execute("ALTER TABLE runs ADD COLUMN synthesis_key TEXT")
                db.execute("ALTER TABLE runs ADD COLUMN synthesis_fingerprint TEXT")
                db.execute("CREATE UNIQUE INDEX synthesis_keys ON runs(synthesis_key)")
                db.execute("PRAGMA user_version = 3")

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        db: sqlite3.Connection | None = None
        try:
            db = sqlite3.connect(self.path, timeout=5)
            db.execute("PRAGMA foreign_keys = ON")
            with db:
                yield db
        except sqlite3.Error as error:
            raise ServiceError(
                "STORAGE_ERROR: Could not read or save local research data."
            ) from error
        finally:
            if db is not None:
                db.close()

    def create(self, run: Run, key: str) -> tuple[UUID, bool]:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute(
                "SELECT id, request_fingerprint FROM runs WHERE request_key=?", (key,)
            ).fetchone()
            if previous:
                if previous[1] != fingerprint(run):
                    raise ServiceError(
                        "IDEMPOTENCY_CONFLICT: Submission key belongs to different input or limits."
                    )
                return UUID(previous[0]), False
            for (payload,) in db.execute("SELECT payload FROM runs"):
                if Run.model_validate_json(payload).state not in TERMINAL:
                    raise ServiceError(
                        "BUSY: Finish or cancel the active run before starting another."
                    )
            db.execute(
                "INSERT INTO runs (id, request_key, request_fingerprint, payload) "
                "VALUES (?, ?, ?, ?)",
                (str(run.id), key, fingerprint(run), run.model_dump_json()),
            )
            self.event(db, run, "submitted", "Research run queued.")
            return run.id, True

    def claim_synthesis(self, run_id: UUID, key: str, config: SynthesisConfig) -> bool:
        identity = sha256((str(run_id) + config.model_dump_json()).encode()).hexdigest()
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute(
                "SELECT id, synthesis_fingerprint FROM runs WHERE synthesis_key=?", (key,)
            ).fetchone()
            if old:
                if old != (str(run_id), identity):
                    raise ServiceError("IDEMPOTENCY_CONFLICT: Different synthesis request.")
                return False
            run = self.read_run(db, run_id)
            if run.kind != "live" or run.state != State.SOURCES_READY:
                raise ServiceError("INVALID_STATE: Synthesize a saved sources-ready run once.")
            for (payload,) in db.execute("SELECT payload FROM runs"):
                if Run.model_validate_json(payload).state not in TERMINAL:
                    raise ServiceError("BUSY: Another run is active.")
            run = run.model_copy(
                update={
                    "state": State.SYNTHESIZING,
                    "synthesis_config": config,
                    "model_id": config.model,
                    "prompt_version": "synthesis-v1",
                    "label": "Gemini synthesis — critique pending",
                    "cancel_requested": False,
                    "error": None,
                    "updated_at": now(),
                }
            )
            db.execute(
                "UPDATE runs SET payload=?, synthesis_key=?, synthesis_fingerprint=? WHERE id=?",
                (run.model_dump_json(), key, identity, str(run_id)),
            )
            self.event(db, run, "submitted", "Synthesis queued over saved evidence; no new search.")
            return True

    def claim_critique(self, run_id: UUID, key: str, config: SynthesisConfig) -> bool:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            runs = [Run.model_validate_json(p) for (p,) in db.execute("SELECT payload FROM runs")]
            for saved in runs:
                if saved.critique_key == key:
                    if saved.id != run_id or saved.critique_config != config:
                        raise ServiceError("IDEMPOTENCY_CONFLICT: Different critique request.")
                    return False
            run = self.read_run(db, run_id)
            if run.kind != "live" or run.state != State.REPORT_READY or run.critique_key:
                raise ServiceError("INVALID_STATE: Evaluate a saved report-ready run once.")
            if any(saved.state not in TERMINAL for saved in runs):
                raise ServiceError("BUSY: Another run is active.")
            run = run.model_copy(
                update={
                    "state": State.CRITIQUING,
                    "critique_key": key,
                    "critique_config": config,
                    "label": "Live research",
                    "cancel_requested": False,
                    "error": None,
                    "updated_at": now(),
                }
            )
            db.execute("UPDATE runs SET payload=? WHERE id=?", (run.model_dump_json(), str(run_id)))
            self.event(db, run, "submitted", "Critique queued over saved report and evidence.")
            return True

    def event(
        self,
        db: sqlite3.Connection,
        run: Run,
        kind: str,
        message: str,
        duration: float = 0,
        stage: State | None = None,
    ) -> None:
        sequence = db.execute(
            "SELECT COALESCE(MAX(sequence), 0)+1 FROM events WHERE run_id=?", (str(run.id),)
        ).fetchone()[0]
        event = Event(
            run_id=run.id,
            sequence=sequence,
            stage=stage or run.state,
            type=kind,
            message=message,
            duration_seconds=duration,
        )
        db.execute(
            "INSERT INTO events VALUES (?, ?, ?)", (str(run.id), sequence, event.model_dump_json())
        )

    def read_run(self, db: sqlite3.Connection, run_id: UUID) -> Run:
        row = db.execute("SELECT payload FROM runs WHERE id=?", (str(run_id),)).fetchone()
        if row is None:
            raise ServiceError("NOT_FOUND: Research run does not exist.")
        return Run.model_validate_json(row[0])

    def update(
        self,
        run_id: UUID,
        state: State | None = None,
        *,
        stage: str | None = None,
        output: Model | None = None,
        error: str | None = None,
        cancel: bool = False,
        duration: float = 0,
        checkpoint: bool = False,
    ) -> None:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            run = self.read_run(db, run_id)
            if run.state in TERMINAL:
                return
            previous_state = run.state
            run = run.model_copy(
                update={
                    "state": state or run.state,
                    "updated_at": now(),
                    "error": error,
                    "cancel_requested": run.cancel_requested or cancel,
                }
            )
            if stage is not None and output is not None:
                db.execute(
                    "INSERT INTO stage_outputs VALUES (?, ?, ?) "
                    "ON CONFLICT(run_id, stage) DO UPDATE SET payload=excluded.payload",
                    (str(run_id), stage, output.model_dump_json()),
                )
            db.execute("UPDATE runs SET payload=? WHERE id=?", (run.model_dump_json(), str(run_id)))
            self.event(
                db,
                run,
                "stage_checkpoint"
                if checkpoint
                else "stage_completed"
                if output is not None
                else "status",
                f"{stage} output saved."
                if stage
                else error or ("Cancellation requested." if cancel else run.state.value),
                duration,
                previous_state if output else run.state,
            )

    def get(self, run_id: UUID) -> Snapshot:
        with self.connection() as db:
            db.execute("BEGIN")
            run = self.read_run(db, run_id)
            outputs = dict(
                db.execute(
                    "SELECT stage, payload FROM stage_outputs WHERE run_id=?", (str(run_id),)
                )
            )
            events = [
                Event.model_validate_json(row[0])
                for row in db.execute(
                    "SELECT payload FROM events WHERE run_id=? ORDER BY sequence", (str(run_id),)
                )
            ]
        return Snapshot(
            run=run,
            events=events,
            discovery=Discovery.model_validate_json(outputs["discovery"])
            if "discovery" in outputs
            else None,
            analysis=Analysis.model_validate_json(outputs["analysis"])
            if "analysis" in outputs
            else None,
            report=Report.model_validate_json(outputs["report"]) if "report" in outputs else None,
            synthesis=SynthesisRecord.model_validate_json(outputs["synthesis"])
            if "synthesis" in outputs
            else None,
            critique_usage=SynthesisRecord.model_validate_json(outputs["critique_usage"])
            if "critique_usage" in outputs
            else None,
            critique=Critique.model_validate_json(outputs["critique"])
            if "critique" in outputs
            else None,
        )

    def list_runs(self) -> list[Run]:
        with self.connection() as db:
            runs = [
                Run.model_validate_json(row[0]) for row in db.execute("SELECT payload FROM runs")
            ]
        return sorted(runs, key=lambda run: run.created_at, reverse=True)

    def recover(self) -> None:
        for run in self.list_runs():
            if run.state not in TERMINAL:
                self.update(
                    run.id,
                    State.FAILED,
                    error="INTERRUPTED: Application stopped before this run finished.",
                )
