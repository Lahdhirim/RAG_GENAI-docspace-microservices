from fastapi import FastAPI
from database.queries import get_documents_query

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Hello from doc-manager-service!"}

@app.get("/health") 
def health_check():
    return {"status": "OK"}

@app.get("/documents")
def get_documents():
    documents = get_documents_query()
    return {"documents": documents}
