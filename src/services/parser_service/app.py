import os
from datetime import datetime
from pathlib import Path

import redis
from fastapi import FastAPI
from pydantic import BaseModel
from rq import Queue
from utils.job_status import JobStatus
from utils.logger import create_logger

logger = create_logger("parser_api", "logs/parser_api.log")

# Initialize FastAPI app
app = FastAPI()
logger.info("[PARSER SERVICE] Starting parser service.")

# Data directory
DATA_DIR = (
    Path("/app/data/bronze")
    if os.getenv("ENV") == "production"
    else Path("data/bronze").resolve()
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


class JobResponse(BaseModel):
    job_id: str | None = None
    document_id: str | None = None
    filename: str | None = None
    document_path: str | None = None
    submitted_at: datetime | None = None
    status: JobStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    waiting_duration: float | None = None
    execution_duration: float | None = None
    error: str | None = None
    content: str | None = None
    silver_relative_path: str | None = None


@app.post("/submit")
def submit_parsing_job(job_data: JobData) -> JobResponse:
    """Check that the document exists and queue it for parsing."""
    logger.info(
        "[PARSER SERVICE SUBMIT JOB] Received parsing job for document %s with ID %s with relative_path: %s",
        job_data.filename,
        job_data.document_id,
        job_data.relative_path,
    )
    document_path = DATA_DIR / job_data.relative_path

    # Check that the document exists
    if not os.path.exists(document_path):
        logger.error(
            "[PARSER SERVICE SUBMIT JOB] Document %s with ID %s does not exist at path: %s",
            job_data.filename,
            job_data.document_id,
            document_path,
        )
        return JobResponse(
            job_id=None,
            document_id=job_data.document_id,
            filename=job_data.filename,
            document_path=str(document_path),
            status=JobStatus.FAILED,
            error=f"Document not found at path: {document_path}",
        )

    try:
        # Load the converter in the worker rather than in the API process.
        job = jobs_queue.enqueue(
            "components.parse.parse_document",
            str(document_path),
            meta={
                "document_id": job_data.document_id,
                "filename": job_data.filename,
            },
            job_timeout=600,
        )
        logger.info(
            "[PARSER SERVICE SUBMIT JOB] Enqueued parsing job %s for document %s with ID %s at path: %s",
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

    except Exception as e:
        logger.error(
            "[PARSER SERVICE SUBMIT JOB] Failed to enqueue parsing job for document %s with ID %s at path: %s, error: %s",
            job_data.filename,
            job_data.document_id,
            document_path,
            e,
        )
        return JobResponse(
            job_id=None,
            document_id=job_data.document_id,
            filename=job_data.filename,
            document_path=str(document_path),
            status=JobStatus.FAILED,
            error=f"Failed to enqueue parsing job: {e}",
        )


@app.get("/job_status/{job_id}")
def get_job_status(job_id: str) -> JobResponse:
    """Get a parsing job's status and results."""

    # Fetch the job from the queue
    job = jobs_queue.fetch_job(job_id)

    # Job not found in the queue
    if not job:
        logger.warning(
            "[PARSER SERVICE GET JOB STATUS] Job with ID %s not found in the queue.",
            job_id,
        )
        return JobResponse(
            job_id=job_id,
            document_id=None,
            filename=None,
            document_path=None,
            status=JobStatus.NOT_FOUND,
            error=f"Job with ID {job_id} not found in the queue.",
        )

    # Get job status
    rq_status = job.get_status(refresh=True)
    status_mapping = {
        "queued": JobStatus.QUEUED,
        "deferred": JobStatus.QUEUED,
        "scheduled": JobStatus.QUEUED,
        "started": JobStatus.RUNNING,
        "finished": JobStatus.COMPLETED,
        "failed": JobStatus.FAILED,
        "stopped": JobStatus.FAILED,
        "canceled": JobStatus.FAILED,
    }
    job_status = status_mapping.get(rq_status, JobStatus.NOT_STARTED)
    logger.info(
        "[PARSER SERVICE GET JOB STATUS] Job with ID %s has status %s.",
        job_id,
        job_status,
    )

    # Get job results if job is completed
    content = None
    silver_relative_path = None

    if job_status == JobStatus.COMPLETED and job.result is not None:
        content = job.result[0]
        silver_relative_path = str(job.result[1])

    # Compute job duration
    submitted_at = job.enqueued_at
    started_at = job.started_at
    finished_at = job.ended_at
    waiting_duration = None
    execution_duration = None
    if submitted_at and started_at:
        waiting_duration = (started_at - submitted_at).total_seconds()
    if started_at and finished_at:
        execution_duration = (finished_at - started_at).total_seconds()

    # Get worker error if the job failed
    error = None
    if job_status == JobStatus.FAILED:
        error = job.exc_info

    return JobResponse(
        job_id=job.id,
        document_id=job.meta.get("document_id"),
        filename=job.meta.get("filename"),
        document_path=str(job.args[0]),
        status=job_status,
        started_at=started_at,
        finished_at=finished_at,
        waiting_duration=waiting_duration,
        execution_duration=execution_duration,
        content=content,
        silver_relative_path=silver_relative_path,
        error=error,
    )
