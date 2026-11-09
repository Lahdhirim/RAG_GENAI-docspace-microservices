import os
from pathlib import Path
from threading import Lock

from database.queries import (
    get_document_query,
    get_documents_query,
    get_parsing_jobs_query,
)
from fastapi import FastAPI, HTTPException, Query
from fastapi import Path as ApiPath
from fastapi.responses import FileResponse
from models.job import JobsResponse

app = FastAPI()
database_lock = Lock()


@app.get("/")
def read_root():
    return {"message": "Hello from doc-manager-service!"}


@app.get("/health")
def health_check():
    return {"status": "OK"}


@app.get("/documents")
def get_documents():
    with database_lock:
        documents = get_documents_query()
    return {"documents": documents}


@app.get("/jobs", response_model=JobsResponse)
def get_jobs(
    document_id: str | None = Query(default=None, min_length=1, max_length=64)
):
    with database_lock:
        jobs = get_parsing_jobs_query(document_id=document_id)
    return {"jobs": jobs}


# Resolve relative paths against the same data directory used by the scanner.
DOCUMENTS_ROOT = Path(
    os.getenv("DOCUMENTS_ROOT", str(Path(__file__).resolve().parents[3] / "data"))
)
MAX_PREVIEW_BYTES = 50 * 1024 * 1024
PREVIEW_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".txt": "text/plain",
    ".md": "text/plain",
    ".csv": "text/plain",
    ".json": "text/plain",
    ".log": "text/plain",
    ".xml": "text/plain",
}
UNAVAILABLE = "This document is currently unavailable."


@app.get("/documents/{document_id}/preview", response_class=FileResponse)
def preview_document(document_id: str = ApiPath(min_length=1, max_length=64)):
    with database_lock:
        document = get_document_query(document_id)
    if document is None or not document.is_present:
        raise HTTPException(status_code=404, detail=UNAVAILABLE)
    try:
        relative = Path(document.relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise HTTPException(status_code=404, detail=UNAVAILABLE)
        root = DOCUMENTS_ROOT.resolve(strict=True)
        path = (root / relative).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            raise HTTPException(status_code=404, detail=UNAVAILABLE)
        stat = path.stat()
    except OSError:
        raise HTTPException(status_code=404, detail=UNAVAILABLE) from None
    media_type = PREVIEW_TYPES.get(path.suffix.lower())
    if media_type is None:
        raise HTTPException(
            status_code=415, detail="Preview is not supported for this file type."
        )
    if stat.st_size > MAX_PREVIEW_BYTES:
        raise HTTPException(
            status_code=413,
            detail="This document is too large to preview (maximum 50 MiB).",
        )
    return FileResponse(
        path,
        media_type=media_type,
        filename=path.name,
        content_disposition_type="inline",
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox; default-src 'none'; frame-ancestors 'self'",
        },
    )
