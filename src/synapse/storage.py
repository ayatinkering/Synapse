"""SQLite is authoritative; files are rebuildable renderings of saved outputs."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
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
    now,
)


class ServiceError(Exception):
    """A safe, user-facing error code, never an arbitrary adapter traceback."""


class Store:
    def __init__(self, directory: Path) -> None:
        self.path = directory / "synapse.sqlite3"
        with self.connection() as db:
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
                PRAGMA user_version = 1;
            """)

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
                "SELECT id, fixture_id FROM runs WHERE request_key=?", (key,)
            ).fetchone()
            if previous:
                if previous[1] != run.fixture_id:
                    raise ServiceError(
                        "IDEMPOTENCY_CONFLICT: This submission key belongs to another scenario."
                    )
                return UUID(previous[0]), False
            for (payload,) in db.execute("SELECT payload FROM runs"):
                if Run.model_validate_json(payload).state not in TERMINAL:
                    raise ServiceError(
                        "BUSY: Finish or cancel the active run before starting another."
                    )
            db.execute(
                "INSERT INTO runs VALUES (?, ?, ?, ?)",
                (str(run.id), key, run.fixture_id, run.model_dump_json()),
            )
            self.event(db, run, "submitted", "Offline run queued.")
            return run.id, True

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
                    "INSERT INTO stage_outputs VALUES (?, ?, ?)",
                    (str(run_id), stage, output.model_dump_json()),
                )
            db.execute("UPDATE runs SET payload=? WHERE id=?", (run.model_dump_json(), str(run_id)))
            self.event(
                db,
                run,
                "stage_completed" if output is not None else "status",
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
