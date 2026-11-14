import logging
import os
from datetime import UTC, datetime

import requests
from database.ingestion_queries import (
    get_active_ingestion_jobs,
    get_documents_to_ingest,
    record_ingestion_poll_error,
    reserve_ingestion_job,
    update_ingestion_job,
)

logger = logging.getLogger("ingestion_jobs")
service_host = (
    "host.docker.internal" if os.getenv("ENV") == "production" else "127.0.0.1"
)
service_url = os.getenv("GRAPH_RAG_SERVICE_URL", f"http://{service_host}:8002").rstrip(
    "/"
)
REMOTE_STATUSES = {"QUEUED", "RUNNING", "COMPLETED", "FAILED"}


def _save_response(job: dict, response: requests.Response) -> None:
    """Validate that the graph service answered for the expected ingestion job."""
    response.raise_for_status()
    data = response.json()
    if (
        data.get("job_id") != job["job_id"]
        or data.get("document_ids") != [job["document_id"]]
        or data.get("status") not in REMOTE_STATUSES
    ):
        raise ValueError("The graph service returned an unexpected ingestion job.")
    update_ingestion_job(job["job_id"], data)


def _fail_job(job: dict, message: str) -> None:
    """Finish an ingestion attempt that cannot be resumed safely."""
    update_ingestion_job(
        job["job_id"],
        {
            "status": "FAILED",
            "finished_at": datetime.now(UTC).isoformat(),
            "error": message,
        },
    )


def _submit_job(job: dict) -> None:
    """Submit a reserved job using the Markdown already stored by Document Manager."""
    response = requests.post(
        f"{service_url}/ingest",
        json={
            "job_id": job["job_id"],
            "dataset": job["dataset"],
            "documents": [
                {
                    "document_id": job["document_id"],
                    "content": job["content"],
                    "filename": f"{job['file_name']}{job['extension']}",
                    "version": job["parser_job_id"],
                }
            ],
        },
        timeout=10,
    )
    if 400 <= response.status_code < 500 and response.status_code not in {408, 429}:
        _fail_job(job, f"The graph service rejected this ingestion: {response.text}")
        return
    _save_response(job, response)


def _refresh_job(job: dict) -> None:
    """Recover pending submissions or refresh the status of an accepted job."""
    try:
        response = requests.get(f"{service_url}/job_status/{job['job_id']}", timeout=10)
        if response.status_code == 404:
            if job["status"] == "PENDING":
                # Reuse the reserved ID when a submission response was lost.
                _submit_job(job)
            else:
                _fail_job(job, "The graph service no longer has this ingestion job.")
            return
        _save_response(job, response)
    except (requests.RequestException, ValueError, TypeError, AttributeError) as error:
        record_ingestion_poll_error(job["job_id"], str(error))
        logger.warning("Cannot refresh ingestion job %s: %s", job["job_id"], error)


def manage_ingestion_jobs() -> None:
    """Refresh ingestion jobs and submit one parsed document when the queue is free."""
    try:
        active_jobs = get_active_ingestion_jobs()
        try:
            response = requests.get(f"{service_url}/health", timeout=3)
            response.raise_for_status()
        except requests.RequestException as error:
            for job in active_jobs:
                record_ingestion_poll_error(job["job_id"], str(error))
            logger.warning("The graph service is unavailable: %s", error)
            return

        for job in active_jobs:
            _refresh_job(job)
        if get_active_ingestion_jobs():
            return

        for document in get_documents_to_ingest():
            # Commit the reservation before the service can start expensive work.
            job = reserve_ingestion_job(document)
            _refresh_job(job)
    except Exception:
        logger.exception("Could not complete this ingestion cycle.")
