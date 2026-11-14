from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

JobStatus = Literal["QUEUED", "RUNNING", "COMPLETED", "FAILED"]


class DocumentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1, max_length=64)
    version: str = Field(min_length=1, max_length=128)
    filename: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=10_000_000)

    @field_validator("content")
    @classmethod
    def nonempty_markdown(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Markdown content must not be empty.")
        return value


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID = Field(default_factory=uuid4)
    dataset: str = Field(default="docspace", min_length=1, max_length=64)
    documents: list[DocumentInput] = Field(min_length=1, max_length=20)


class JobResponse(BaseModel):
    job_id: UUID
    status: JobStatus
    document_ids: list[str]
    submitted_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    question: str = Field(min_length=1, max_length=20_000)
    dataset: str = Field(default="docspace", min_length=1, max_length=64)
