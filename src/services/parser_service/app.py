import os
from datetime import datetime
from enum import Enum
from pathlib import Path

import redis
from components.parse import parse_document
from fastapi import FastAPI
from pydantic import BaseModel
from rq import Queue
from utils.logger import create_logger

logger = create_logger("parser_service", "logs/parser_service.log")

# Initialize FastAPI app
app = FastAPI()
logger.info("[PARSER SERVICE] Starting parser service.")

# Data directory
DATA_DIR = (
    Path("/app/data") if os.getenv("ENV") == "production" else Path("data").resolve()
)

# Redis service
redis_host = "redis" if os.getenv("ENV") == "production" else "localhost"
redis_conn = redis.Redis(host=redis_host, port=6379)
jobs_queue = Queue("parsing_jobs", connection=redis_conn)
logger.info("[PARSER SERVICE] Connected to Redis and initialized jobs queue.")


@app.get("/")
def read_root():
    return {"message": "Hello from parser-service!"}


@app.get("/health")
def health_check():
    return {"status": "OK"}


class JobData(BaseModel):
    document_id: str
    relative_path: str
    filename: str


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    NOT_FOUND = "NOT_FOUND"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


class JobResponse(BaseModel):
    job_id: str | None = None
    document_id: str
    filename: str
    document_path: str
    submitted_at: datetime | None = None
    status: JobStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    waiting_duration: float | None = None
    execution_duration: float | None = None


@app.post("/submit")
def submit_parsing_job(job_data: JobData) -> JobResponse:
    logger.info(
        "[PARSER SERVICE] Received parsing job for document %s with ID %s with relative_path: %s",
        job_data.filename,
        job_data.document_id,
        job_data.relative_path,
    )
    document_path = DATA_DIR / job_data.relative_path

    # Check that the document exists
    if not os.path.exists(document_path):
        logger.error(
            "[PARSER SERVICE] Document %s with ID %s does not exist at path: %s",
            job_data.filename,
            job_data.document_id,
            document_path,
        )
        return JobResponse(
            job_id=None,
            document_id=job_data.document_id,
            filename=job_data.filename,
            document_path=str(document_path),
            status=JobStatus.NOT_FOUND,
        )

    job = jobs_queue.enqueue(parse_document, str(document_path))
    logger.info(
        "[PARSER SERVICE] Enqueued parsing job %s for document %s with ID %s at path: %s",
        job.id,
        job_data.filename,
        job_data.document_id,
        document_path,
    )
    return JobResponse(
        job_id=job.id,
        document_id=job_data.document_id,
        filename=job_data.filename,
        document_path=str(document_path),
        submitted_at=datetime.now(),
        status=JobStatus.QUEUED,
    )
