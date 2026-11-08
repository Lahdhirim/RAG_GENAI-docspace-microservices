import os

import requests
from database.queries import (
    get_active_parsing_jobs,
    get_documents_to_parse,
    update_jobs_status,
)
from dotenv import load_dotenv
from models.document import Document
from utils.logger import create_logger

load_dotenv()
logger = create_logger("parsing_jobs", "logs/parsing_jobs.log")

env = os.getenv("ENV", "development")
parser_service_host = "parsing_service" if env == "production" else "127.0.0.1"


def submit_parsing_jobs(documents: list[Document]) -> tuple[dict, dict]:
    submitted_documents = {}
    failed_documents = {}
    logger.info("[SUBMIT PARSING JOBS] Submitting parsing jobs")
    for document in documents:

        logger.info(
            "[SUBMIT PARSING JOBS] Submitting parsing job for document %s with ID %s and relative_path %s",
            document.filename,
            document.id,
            document.relative_path,
        )
        try:
            response = requests.post(
                f"http://{parser_service_host}:8001/submit",
                json={
                    "document_id": document.id,
                    "relative_path": document.relative_path,
                    "filename": document.filename,
                },
            )
            response.raise_for_status()
            logger.info(
                "[SUBMIT PARSING JOBS] Successfully submitted parsing job for document %s with ID %s and relative_path %s",
                document.filename,
                document.id,
                document.relative_path,
            )
            submitted_documents[document.id] = {
                "job_id": response.json().get("job_id"),
                "document_id": response.json().get("document_id"),
                "submitted_at": response.json().get("submitted_at"),
                "status": response.json().get("status"),
                "started_at": response.json().get("started_at"),
                "finished_at": response.json().get("finished_at"),
                "waiting_duration": response.json().get("waiting_duration"),
                "execution_duration": response.json().get("execution_duration"),
                "error": None,
            }

        except requests.RequestException as e:
            logger.error(
                "[SUBMIT PARSING JOBS] Failed to submit parsing job for document %s with ID %s and relative_path %s, error: %s",
                document.filename,
                document.id,
                document.relative_path,
                e,
            )
            failed_documents[document.id] = {
                "job_id": None,
                "document_id": document.id,
                "submitted_at": None,
                "status": "FAILED",
                "started_at": None,
                "finished_at": None,
                "waiting_duration": None,
                "execution_duration": None,
                "error": e,
            }

    return submitted_documents, failed_documents


def get_redis_jobs_status(db_jobs: list[dict]) -> dict[str, dict]:
    job_updates = {}
    for db_job in db_jobs:
        db_job_id = db_job.get("job_id")

        try:
            response = requests.get(
                f"http://{parser_service_host}:8001/job_status/{db_job_id}",
                json={"job_id": db_job_id},
            )
            response.raise_for_status()
            job_updates[db_job_id] = response.json()

        except requests.RequestException as e:
            logger.error(
                "[GET REDIS JOBS STATUS] Failed to get status for job with ID %s, error: %s",
                db_job_id,
                e,
            )
            job_updates[db_job_id] = {"status": "UNKNOWN", "error": str(e)}

    return job_updates


def manage_parsing_jobs(output_dir: str):
    logger.info("=" * 80)
    logger.info("[PARSING JOBS] Submitting parsing jobs.")
    os.makedirs(output_dir, exist_ok=True)

    # 1. Get active jobs from the database
    active_jobs = get_active_parsing_jobs()
    logger.info("[PARSING JOBS] Retrieved %d active parsing jobs.", len(active_jobs))

    # 2. Get jobs status from the parser service (Redis Queue)
    redis_jobs_status = get_redis_jobs_status(db_jobs=active_jobs)

    # 3. Update SQL jobs table
    update_jobs_status(redis_jobs_status)

    # 4. Retrieve the list of documents that need parsing
    documents_to_parse = get_documents_to_parse()
    logger.info(
        "[PARSING JOBS] Retrieved %d documents to parse.", len(documents_to_parse)
    )

    # 5. Submit parsing jobs to the parser service
    submitted_documents, failed_documents = submit_parsing_jobs(documents_to_parse)

    logger.info("[PARSING JOBS] Submitted documents: %s", submitted_documents)
    logger.info("[PARSING JOBS] Failed documents: %s", failed_documents)
    logger.info("[PARSING JOBS] Finished submitting parsing jobs.")
    logger.info("=" * 80)
    return None


manage_parsing_jobs("app/silver")
