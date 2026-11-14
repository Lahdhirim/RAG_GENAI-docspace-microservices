import asyncio
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from components import graph
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator
from utils.job_status import JobStatus
from utils.logger import create_logger

load_dotenv()
logger = create_logger("graph_rag_service", "logs/graph_rag_service.log")
DATASET = os.getenv("GRAPH_RAG_DATASET", "docspace")
DATA_DIR = Path(os.getenv("GRAPH_RAG_STATE_DIR", "data/graph_rag")).resolve()
os.environ.setdefault("SYSTEM_ROOT_DIRECTORY", str(DATA_DIR / "system"))
os.environ.setdefault("DATA_ROOT_DIRECTORY", str(DATA_DIR / "data"))
os.environ.setdefault("GRAPH_DATABASE_PROVIDER", "neo4j")
os.environ.setdefault("ENABLE_BACKEND_ACCESS_CONTROL", "false")

jobs = {}
jobs_queue = asyncio.Queue()
graph_lock = asyncio.Lock()


class JobData(BaseModel):
    job_id: UUID = Field(default_factory=uuid4)
    document_id: str = Field(min_length=1, max_length=64)
    version: str = Field(min_length=1, max_length=128)
    filename: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=10_000_000)
    dataset: str = DATASET

    @field_validator("content")
    @classmethod
    def nonempty_markdown(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Markdown content must not be empty.")
        return value


class JobResponse(BaseModel):
    job_id: UUID
    document_id: str
    status: JobStatus
    submitted_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None


class QueryData(BaseModel):
    model_config = {"str_strip_whitespace": True}
    question: str = Field(min_length=1, max_length=20_000)
    dataset: str = DATASET


async def process_ingestion_jobs():
    """Take queued documents one at a time and update their ingestion status."""
    while True:
        job_id = await jobs_queue.get()
        job = jobs[job_id]
        try:
            async with graph_lock:
                job.update(status="RUNNING", started_at=datetime.now(UTC))
                try:
                    await graph.ingest_document(job, job["dataset"])
                except asyncio.CancelledError:
                    job.update(
                        status="FAILED", error="Service stopped during ingestion."
                    )
                    raise
                except Exception:
                    logger.exception("Ingestion failed for job %s", job_id)
                    job.update(
                        status="FAILED",
                        error="Ingestion failed; inspect the service logs.",
                    )
                else:
                    job["status"] = "COMPLETED"
                finally:
                    job["finished_at"] = datetime.now(UTC)
        finally:
            jobs_queue.task_done()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.worker = asyncio.create_task(process_ingestion_jobs())
    try:
        yield
    finally:
        app.state.worker.cancel()
        try:
            await app.state.worker
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Docspace GraphRAG Service", lifespan=lifespan)


def check_dataset(dataset: str):
    if dataset != DATASET:
        raise HTTPException(422, f"This service uses dataset '{DATASET}'.")


@asynccontextmanager
async def graph_operation(dataset: str):
    """Keep queries and visualization separate from an active ingestion."""
    check_dataset(dataset)
    if graph_lock.locked():
        raise HTTPException(
            503, "The graph is busy; try again shortly.", headers={"Retry-After": "5"}
        )
    async with graph_lock:
        yield


@app.exception_handler(Exception)
async def graph_error(request, error):
    logger.error(
        "Graph operation failed", exc_info=(type(error), error, error.__traceback__)
    )
    return JSONResponse(
        status_code=502,
        content={"detail": "Graph operation failed; inspect the service logs."},
    )


@app.get("/health")
async def health_check():
    """Return the service health status."""
    if app.state.worker.done():
        raise HTTPException(503, "The ingestion worker has stopped.")
    return {"status": "OK"}


@app.post("/ingest", response_model=JobResponse, status_code=202)
async def ingest(job_data: JobData):
    """Queue a Markdown document and return its job ID immediately."""
    check_dataset(job_data.dataset)
    if app.state.worker.done():
        raise HTTPException(503, "The ingestion worker has stopped.")
    data = job_data.model_dump(mode="json")
    job_id = data["job_id"]
    if job_id in jobs:
        if any(jobs[job_id][key] != value for key, value in data.items()):
            raise HTTPException(
                409, "This job ID already belongs to a different document."
            )
        return jobs[job_id]
    jobs[job_id] = {**data, "status": "QUEUED", "submitted_at": datetime.now(UTC)}
    jobs_queue.put_nowait(job_id)
    return jobs[job_id]


@app.get("/job_status/{job_id}", response_model=JobResponse)
async def get_job_status(job_id: UUID):
    """Return the status and timings of an ingestion job."""
    job = jobs.get(str(job_id))
    if job is None:
        raise HTTPException(404, "Ingestion job not found.")
    return job


@app.post("/query")
async def query(query_data: QueryData):
    """Answer a question using Cognee graph completion."""
    async with graph_operation(query_data.dataset):
        results = await graph.query(query_data.question, query_data.dataset)
    return {"dataset": query_data.dataset, "results": results}


@app.post("/query_cypher")
async def query_cypher(query_data: QueryData):
    """Translate a question into Cypher and return the matching records."""
    async with graph_operation(query_data.dataset):
        results = await graph.query_cypher(query_data.question, query_data.dataset)
    return {"dataset": query_data.dataset, "results": results}


@app.get("/generate_html", response_class=HTMLResponse)
async def generate_html(dataset: str = DATASET):
    """Generate an HTML visualization of the knowledge graph."""
    async with graph_operation(dataset):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        output = DATA_DIR / "graph.html"
        await graph.generate_html(dataset, output)
        return HTMLResponse(
            output.read_text(encoding="utf-8"), headers={"Cache-Control": "no-store"}
        )
