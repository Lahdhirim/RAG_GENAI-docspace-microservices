import os
from datetime import UTC, datetime

import requests
from database.queries import (
    get_active_ingestion_jobs,
    get_documents_to_ingest,
    reserve_ingestion_job,
    update_ingestion_job,
)
from utils.logger import create_logger

logger = create_logger("ingestion_jobs", "logs/ingestion_jobs.log")
service_url = os.getenv("GRAPH_RAG_SERVICE_URL", "http://localhost:8002").rstrip("/")


def submit_ingestion_job(job: dict) -> dict:
    """Submit a reserved document to the graph service for ingestion."""
    response = requests.post(
        f"{service_url}/ingest",
        json={
            "job_id": job["job_id"],
            "document_id": job["document_id"],
            "version": job["parser_job_id"],
            "filename": f"{job['file_name']}{job['extension']}",
            "content": job["content"],
            "dataset": job["dataset"],
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def get_ingestion_jobs_status(jobs: list[dict]) -> dict[str, dict]:
    """Fetch ingestion statuses and recover submissions whose responses were lost."""
    updates = {}
    for job in jobs:
        job_id = job["job_id"]
        try:
            response = requests.get(f"{service_url}/job_status/{job_id}", timeout=10)
            if response.status_code == 404 and job["status"] == "PENDING":
                # Resubmit the reserved ID so a lost response cannot create another job.
                data = submit_ingestion_job(job)
            elif response.status_code == 404:
                data = {
                    "job_id": job_id,
                    "document_id": job["document_id"],
                    "status": "FAILED",
                    "error": "The graph service no longer has this ingestion job.",
                    "finished_at": datetime.now(UTC).isoformat(),
                }
            else:
                response.raise_for_status()
                data = response.json()
            if data.get("status") not in {"QUEUED", "RUNNING", "COMPLETED", "FAILED"}:
                raise ValueError("The graph service returned an invalid job status.")
            if (
                data.get("job_id") != job_id
                or data.get("document_id") != job["document_id"]
            ):
                raise ValueError(
                    "The graph service returned a different ingestion job."
                )
            updates[job_id] = data
        except (requests.RequestException, ValueError) as error:
            status = job["status"]
            if (
                isinstance(error, requests.HTTPError)
                and 400 <= error.response.status_code < 500
                and error.response.status_code not in {408, 429}
            ):
                status = "FAILED"
            updates[job_id] = {"status": status, "error": str(error)}
            if status == "FAILED":
                updates[job_id]["finished_at"] = datetime.now(UTC).isoformat()
            logger.warning("Cannot refresh ingestion job %s: %s", job_id, error)
    return updates


def manage_ingestion_jobs() -> None:
    """Refresh the active ingestion or submit the next parsed document."""
    try:
        jobs = get_active_ingestion_jobs()
        if not jobs:
            documents = get_documents_to_ingest()
            if documents:
                # Save the job before the graph service starts processing its content.
                jobs = [reserve_ingestion_job(documents[0])]
        for job_id, data in get_ingestion_jobs_status(jobs[:1]).items():
            update_ingestion_job(job_id, data)
    except Exception:
        logger.exception("Could not complete this ingestion cycle.")
