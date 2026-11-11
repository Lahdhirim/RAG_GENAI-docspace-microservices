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
        stored_path = (
            get_markdown_path_query(document_id, job_id)
            if document and kind == "markdown"
            else None
        )
    if document is None or (kind == "original" and not document.is_present):
        raise HTTPException(status_code=404, detail=unavailable)
    value = document.relative_path if kind == "original" else stored_path
    if not value:
        raise HTTPException(status_code=404, detail=unavailable)
    try:
        root = (
            Path(data_path) / ("bronze" if kind == "original" else "silver")
        ).resolve(strict=True)
        relative = Path(value)
        if ".." in relative.parts or (kind == "original" and relative.is_absolute()):
            raise HTTPException(status_code=404, detail=unavailable)
        if relative.is_absolute():
            candidate = relative
        elif kind == "markdown" and relative.parts[:2] == ("data", "silver"):
            candidate = Path(data_path).parent / relative
        elif kind == "markdown" and relative.parts[0] == "silver":
            candidate = Path(data_path) / relative
        else:
            candidate = root / relative
        path = candidate.resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            raise HTTPException(status_code=404, detail=unavailable)
        size = path.stat().st_size
    except (OSError, RuntimeError):
        raise HTTPException(status_code=404, detail=unavailable) from None
    media_type = (
        "text/plain"
        if kind == "markdown" and path.suffix.lower() == ".md"
        else PREVIEW_TYPES.get(path.suffix.lower()) if kind == "original" else None
    )
    if media_type is None:
        raise HTTPException(
            status_code=415, detail="Preview is not supported for this file type."
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
