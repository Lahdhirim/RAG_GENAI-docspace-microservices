import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from models import IngestRequest, JobResponse, JobStatus
from pydantic import BaseModel

logger = logging.getLogger(__name__)


def now() -> datetime:
    return datetime.now(timezone.utc)


class JobRecord(BaseModel):
    request: IngestRequest
    status: JobStatus = "QUEUED"
    submitted_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None

    def response(self) -> JobResponse:
        return JobResponse(
            job_id=self.request.job_id,
            status=self.status,
            document_ids=[doc.document_id for doc in self.request.documents],
            submitted_at=self.submitted_at,
            started_at=self.started_at,
            finished_at=self.finished_at,
            error=self.error,
        )


class JobConflict(ValueError):
    pass


class JobStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.records: dict[UUID, JobRecord] = {}
        for path in sorted(root.glob("*.json")):
            record = JobRecord.model_validate_json(path.read_text(encoding="utf-8"))
            if path.stem != str(record.request.job_id):
                raise ValueError(f"Job ID does not match journal filename: {path.name}")
            self.records[record.request.job_id] = record

    def save(self, record: JobRecord) -> None:
        """Persist a job atomically before exposing its new state."""
        path = self.root / f"{record.request.job_id}.json"
        temporary = path.with_suffix(f".{uuid4().hex}.tmp")
        try:
            with temporary.open("w", encoding="utf-8") as stream:
                stream.write(record.model_dump_json())
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        self.records[record.request.job_id] = record

    def submit(self, request: IngestRequest) -> tuple[JobRecord, bool]:
        """Reuse a submitted job ID without repeating its ingestion."""
        existing = self.records.get(request.job_id)
        if existing is not None:
            if existing.request != request:
                raise JobConflict("This job ID already belongs to a different request.")
            return existing, False
        record = JobRecord(request=request, submitted_at=now())
        self.save(record)
        return record, True

    def recover(self) -> list[UUID]:
        """Recover queued work and flag interrupted ingestions for explicit review."""
        queued = []
        for record in self.records.values():
            if record.status == "RUNNING":
                # A partial graph may already exist, so do not replay paid work silently.
                self.save(
                    record.model_copy(
                        update={
                            "status": "FAILED",
                            "finished_at": now(),
                            "error": "Service stopped during ingestion; partial data may exist.",
                        }
                    )
                )
            elif record.status == "QUEUED":
                queued.append(record.request.job_id)
        return sorted(queued, key=lambda job_id: self.records[job_id].submitted_at)


class SerialIngestion:
    def __init__(self, store: JobStore, engine, engine_lock: asyncio.Lock):
        self.store = store
        self.engine = engine
        self.engine_lock = engine_lock
        self.queue: asyncio.Queue[UUID] = asyncio.Queue()
        self.task: asyncio.Task | None = None

    def start(self) -> None:
        for job_id in self.store.recover():
            self.queue.put_nowait(job_id)
        self.task = asyncio.create_task(self.run())
        self.task.add_done_callback(self.log_failure)

    @staticmethod
    def log_failure(task: asyncio.Task) -> None:
        if not task.cancelled() and task.exception() is not None:
            error = task.exception()
            logger.error(
                "Ingestion worker stopped",
                exc_info=(type(error), error, error.__traceback__),
            )

    async def stop(self) -> None:
        if self.task is None:
            return
        self.task.cancel()
        try:
            await self.task
        except asyncio.CancelledError:
            pass
        except Exception:
            # Preserve the original failure in the journal; startup will recover queued jobs.
            logger.exception("Ingestion worker had already stopped")

    def submit(self, request: IngestRequest) -> JobResponse:
        record, created = self.store.submit(request)
        if created:
            self.queue.put_nowait(request.job_id)
        return record.response()

    async def run(self) -> None:
        """Process one ingestion at a time while status requests remain available."""
        while True:
            job_id = await self.queue.get()
            try:
                async with self.engine_lock:
                    record = self.store.records[job_id].model_copy(
                        update={"status": "RUNNING", "started_at": now()}
                    )
                    self.store.save(record)
                    try:
                        await self.engine.ingest(
                            [doc.model_dump() for doc in record.request.documents],
                            record.request.dataset,
                        )
                    except asyncio.CancelledError:
                        self.store.save(
                            record.model_copy(
                                update={
                                    "status": "FAILED",
                                    "finished_at": now(),
                                    "error": "Service stopped during ingestion; partial data may exist.",
                                }
                            )
                        )
                        raise
                    except Exception:
                        logger.exception("Ingestion failed for job %s", job_id)
                        terminal = {
                            "status": "FAILED",
                            "error": "Ingestion failed; inspect the GraphRAG service logs.",
                        }
                    else:
                        terminal = {"status": "COMPLETED"}
                    self.store.save(
                        record.model_copy(update={**terminal, "finished_at": now()})
                    )
            finally:
                self.queue.task_done()
