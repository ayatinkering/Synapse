"""Single-owner, bounded background orchestration for offline research runs."""

import os
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock
from time import monotonic
from uuid import UUID

from filelock import FileLock, Timeout

from synapse.export import render
from synapse.fixtures import FixtureAdapter, Stages, get_fixture, list_fixtures
from synapse.models import (
    TERMINAL,
    Analysis,
    Critique,
    Discovery,
    FixtureInfo,
    Limits,
    Report,
    Run,
    Snapshot,
    State,
)
from synapse.storage import ServiceError, Store
from synapse.validation import (
    independent_sources,
    validate_analysis,
    validate_critique,
    validate_discovery,
    validate_report,
)


class ResearchService:
    def __init__(
        self,
        data_dir: Path = Path("data/synapse"),
        *,
        stages: Stages | None = None,
        limits: Limits | None = None,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self.directory = data_dir.resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self._owner = FileLock(self.directory / ".owner.lock", thread_local=False)
        try:
            self._owner.acquire(timeout=0)
        except Timeout as error:
            raise ServiceError("IN_USE: Another application owns this data directory.") from error
        try:
            self.store = Store(self.directory)
            self.store.recover()
        except Exception:
            self._owner.release()
            raise
        self.stages = stages or FixtureAdapter()
        self.limits = limits or Limits()
        self.clock = clock
        self._guard = RLock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="synapse")
        self._futures: dict[UUID, Future[None]] = {}
        self._storage_failure = False
        self._closed = False

    def __enter__(self) -> "ResearchService":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        with self._guard:
            if self._closed:
                return
            self._closed = True
        self._executor.shutdown(wait=True)
        self._owner.release()

    @staticmethod
    def list_fixtures() -> list[FixtureInfo]:
        return list_fixtures()

    def submit(self, fixture_id: str, idempotency_key: str) -> UUID:
        info = get_fixture(fixture_id)
        if not idempotency_key.strip() or len(idempotency_key) > 200:
            raise ServiceError("INVALID_KEY: Submission key must contain 1–200 characters.")
        with self._guard:
            if self._closed:
                raise ServiceError("CLOSED: Application worker is closed.")
            run = Run(fixture_id=info.id, input=info.input, limits=self.limits)
            run_id, created = self.store.create(run, idempotency_key)
            if created:
                self._futures[run_id] = self._executor.submit(self._execute, run_id)
            return run_id

    def get_run(self, run_id: UUID) -> Snapshot:
        if self._storage_failure:
            raise ServiceError("STORAGE_ERROR: Worker could not save. Check storage, then restart.")
        return self.store.get(run_id)

    def list_runs(self) -> list[Run]:
        return self.store.list_runs()

    def wait(self, run_id: UUID, timeout: float = 10) -> Snapshot:
        """Wait for an owned job (useful for deterministic callers and acceptance checks)."""
        with self._guard:
            future = self._futures.get(run_id)
        if future:
            future.result(timeout=timeout)
        return self.get_run(run_id)

    def cancel(self, run_id: UUID) -> None:
        self.store.update(run_id, cancel=True)

    def checkpoint(self, run_id: UUID, started: float) -> bool:
        run = self.store.get(run_id).run
        if run.cancel_requested:
            self.store.update(
                run_id, State.CANCELLED, error="CANCELLED: Cancelled at a stage boundary."
            )
            return False
        if self.clock() - started >= run.limits.deadline_seconds:
            self.store.update(
                run_id,
                State.FAILED,
                error="DEADLINE_EXCEEDED: Offline run exceeded its time budget.",
            )
            return False
        return True

    def _execute(self, run_id: UUID) -> None:
        started = self.clock()
        try:
            self.store.update(run_id, State.DISCOVERING)
            if not self.checkpoint(run_id, started):
                return
            run = self.store.get(run_id).run
            tick = self.clock()
            discovery = Discovery.model_validate_json(self.stages.discover(run).model_dump_json())
            validate_discovery(run, discovery)
            self.store.update(
                run_id,
                State.ANALYZING,
                stage="discovery",
                output=discovery,
                duration=self.clock() - tick,
            )
            if not self.checkpoint(run_id, started):
                return
            tick = self.clock()
            analysis = Analysis.model_validate_json(
                self.stages.analyze(run, discovery).model_dump_json()
            )
            validate_analysis(run, discovery, analysis)
            self.store.update(
                run_id,
                State.SYNTHESIZING,
                stage="analysis",
                output=analysis,
                duration=self.clock() - tick,
            )
            self._artifacts(self.store.get(run_id))
            if not self.checkpoint(run_id, started):
                return
            if independent_sources(analysis) < 2:
                self.store.update(
                    run_id,
                    State.INSUFFICIENT,
                    error="EVIDENCE_GAP: Fewer than two independent usable fixture sources.",
                )
                return
            tick = self.clock()
            report = Report.model_validate_json(
                self.stages.synthesize(run, analysis).model_dump_json()
            )
            validate_report(run, analysis, report)
            self.store.update(
                run_id,
                State.CRITIQUING,
                stage="report",
                output=report,
                duration=self.clock() - tick,
            )
            self._artifacts(self.store.get(run_id))
            if not self.checkpoint(run_id, started):
                return
            tick = self.clock()
            critique = Critique.model_validate_json(
                self.stages.critique(run, report).model_dump_json()
            )
            validate_critique(run, report, critique)
            self.store.update(
                run_id, stage="critique", output=critique, duration=self.clock() - tick
            )
            if self.checkpoint(run_id, started):
                self.store.update(run_id, State.COMPLETED)
        except ServiceError:
            self._record_failure(run_id, "STORAGE_ERROR: A local storage operation failed.")
        except OSError:
            self._record_failure(run_id, "STORAGE_ERROR: Could not write local artifacts.")
        except Exception:
            self._record_failure(
                run_id,
                "STAGE_FAILED: Execution or validation failed. Prior outputs retained.",
            )

    def _record_failure(self, run_id: UUID, message: str) -> None:
        try:
            self.store.update(run_id, State.FAILED, error=message)
        except ServiceError:
            self._storage_failure = True

    def _atomic_write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent, delete=False
            ) as handle:
                temporary = Path(handle.name)
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def _artifacts(self, snapshot: Snapshot) -> tuple[str, str]:
        markdown, bundle = render(snapshot)
        root = self.directory / "runs" / str(snapshot.run.id)
        if snapshot.analysis:
            for source in snapshot.analysis.sources:
                self._atomic_write(root / "sources" / f"{source.id}.txt", source.extracted_text)
        self._atomic_write(root / "report-v1.md", markdown)
        self._atomic_write(root / "bundle.json", bundle)
        return markdown, bundle

    def export_run(self, run_id: UUID) -> tuple[str, str]:
        snapshot = self.get_run(run_id)
        if snapshot.run.state not in TERMINAL:
            raise ServiceError("NOT_READY: Wait for this run to stop before exporting.")
        try:
            return self._artifacts(snapshot)
        except (OSError, ValueError) as error:
            raise ServiceError(
                "EXPORT_FAILED: Saved data could not be validated or written."
            ) from error
