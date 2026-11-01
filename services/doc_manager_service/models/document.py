from pydantic import BaseModel

class Document(BaseModel):
    id: str
    relative_path: str
    content_hash: str
    size_bytes: int
    file_created_at: str | None = None
    file_modified_at: str | None = None
    file_accessed_at: str | None = None
    is_present: bool = True
    is_parsed: bool = False
    created_at: str | None = None
    updated_at: str | None = None