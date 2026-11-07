import redis
from database.queries import get_documents_query
from fastapi import FastAPI

app = FastAPI()
r = redis.Redis(host="redis", port=6379)


@app.get("/")
def read_root():
    # Check Redis connection
    count = r.incr("hits")
    return {"message": "Hello from doc-manager-service!", "hits": count}


@app.get("/health")
def health_check():
    return {"status": "OK"}


@app.get("/documents")
def get_documents():
    documents = get_documents_query()
    return {"documents": documents}
