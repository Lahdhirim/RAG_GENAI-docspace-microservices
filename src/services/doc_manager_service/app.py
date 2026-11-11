import os
from pathlib import Path
from threading import Lock
from typing import Literal

from database.queries import (
    get_document_query,
    get_documents_query,
    get_markdown_path_query,
    get_parsing_statuses_query,
)
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi import Path as ApiPath
from fastapi.responses import FileResponse

load_dotenv()

env = os.getenv("ENV", "development")
data_path = "/app/data" if env == "production" else "data"

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


@app.get("/parsing_statuses")
def parsing_statuses():
    with database_lock:
        parsing_statuses = get_parsing_statuses_query()
    return {"statuses": parsing_statuses}


MAX_PREVIEW_BYTES = 50 * 1024 * 1024


@app.get("/documents/{document_id}/preview", response_class=FileResponse)
def preview_document(
    document_id: str = ApiPath(min_length=1, max_length=64),
    kind: Literal["original", "markdown"] = "original",
    job_id: str | None = Query(default=None, min_length=1, max_length=64),
):
    unavailable = (
        "This document is currently unavailable."
        if kind == "original"
        else "Markdown is not available for this document."
    )
    with database_lock:
        document = get_document_query(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail=unavailable)

    if kind == "original":
        if not document.is_present:
            raise HTTPException(status_code=404, detail=unavailable)
        root = Path(data_path) / "bronze"
        path = root / document.relative_path
        extension, media_type = ".pdf", "application/pdf"
    else:
        with database_lock:
            stored_path = get_markdown_path_query(document_id, job_id)
        if not stored_path:
            raise HTTPException(status_code=404, detail=unavailable)
        root = Path(data_path) / "silver"
        path = Path(stored_path)
        extension, media_type = ".md", "text/plain"

    return _preview_file(path, root, extension, media_type, unavailable)


def _preview_file(
    path: Path, root: Path, extension: str, media_type: str, unavailable: str
) -> FileResponse:
    """Serve an existing file inside its bronze/silver directory."""
    try:
        path = path.resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise HTTPException(status_code=404, detail=unavailable)
        size = path.stat().st_size
    except (OSError, RuntimeError):
        raise HTTPException(status_code=404, detail=unavailable) from None
    if path.suffix.lower() != extension:
        raise HTTPException(
            status_code=415,
            detail="Only PDF originals and Markdown outputs can be previewed.",
        )
    if size > MAX_PREVIEW_BYTES:
        raise HTTPException(
            status_code=413,
            detail="This file is too large to preview (maximum 50 MiB).",
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
