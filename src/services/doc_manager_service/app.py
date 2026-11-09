from threading import Lock

from database.queries import get_documents_query, get_parsing_jobs_query
from fastapi import FastAPI, Query
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
