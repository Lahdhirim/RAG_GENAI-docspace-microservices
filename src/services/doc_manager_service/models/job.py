from datetime import datetime

from pydantic import BaseModel
from utils.job_status import JobStatus


class ParsingJob(BaseModel):
    job_id: str
    document_id: str
    filename: str | None = None
    relative_path: str | None = None
    submitted_at: datetime
    status: JobStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    waiting_duration: float | None = None
    execution_duration: float | None = None
    error: str | None = None


class JobsResponse(BaseModel):
    jobs: list[ParsingJob]
