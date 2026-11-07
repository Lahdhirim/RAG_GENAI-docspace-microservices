from pydantic import BaseModel
from datetime import datetime

class Document(BaseModel):
    id: str
    relative_path: str
    content_hash: str
    size_bytes: int
    file_created_at: datetime | None = None
    file_modified_at: datetime | None = None
    file_accessed_at: datetime | None = None
    is_present: bool = True
    is_parsed: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None