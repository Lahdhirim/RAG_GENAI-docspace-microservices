from threading import Lock

from database.queries import get_documents_query, get_parsing_statuses_query
from fastapi import FastAPI

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
