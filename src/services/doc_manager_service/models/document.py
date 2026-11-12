from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class SubmissionStatus(str, Enum):
    """Submission state of a document to the parser service."""

    NOT_SUBMITTED = "NOT_SUBMITTED"
    SUBMITTED = "SUBMITTED"
    FAILED = "FAILED"


class Document(BaseModel):
    """Metadata and processing state of a tracked document."""

    id: str
    relative_path: str
    filename: str
    extension: str
    content_hash: str
    size_bytes: int
    file_created_at: datetime | None = None
    file_modified_at: datetime | None = None
    file_accessed_at: datetime | None = None
    submission_status: SubmissionStatus = SubmissionStatus.NOT_SUBMITTED
    submission_error: str | None = None
    is_present: bool = True
    is_parsed: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
