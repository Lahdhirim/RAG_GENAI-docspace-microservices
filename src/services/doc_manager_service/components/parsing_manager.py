import os
from datetime import datetime

import requests
from database.queries import (
    get_active_parsing_jobs,
    get_documents_to_parse,
    insert_parsing_job,
    update_document_submission_status,
    update_job_status,
)
from dotenv import load_dotenv
from models.document import Document
from utils.job_status import JobStatus
from utils.logger import create_logger

load_dotenv()
logger = create_logger("parsing_jobs", "logs/parsing_jobs.log")

env = os.getenv("ENV", "development")
parser_service_host = "parsing_api" if env == "production" else "127.0.0.1"


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
                timeout=10,
            )
            response.raise_for_status()
            reponse_data = response.json()
            job_status = reponse_data.get("status")

            if job_status == JobStatus.QUEUED:
                logger.info(
                    "[SUBMIT PARSING JOBS] Successfully submitted parsing job for document %s with ID %s and relative_path %s",
                    document.filename,
                    document.id,
                    document.relative_path,
                )
                submitted_documents[document.id] = {
                    "job_id": reponse_data.get("job_id"),
                    "document_id": reponse_data.get("document_id"),
                    "submitted_at": datetime.fromisoformat(
                        reponse_data.get("submitted_at")
                    ),
                    "status": job_status,
                    "error": None,
                }

            else:
                logger.error(
                    "[SUBMIT PARSING JOBS] Failed to submit parsing job for document %s with ID %s and relative_path %s, status: %s",
                    document.filename,
                    document.id,
                    document.relative_path,
                    job_status,
                )
                failed_documents[document.id] = {
                    "job_id": None,
                    "document_id": reponse_data.get("document_id"),
                    "status": JobStatus.FAILED,
                    "error": reponse_data.get("error"),
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
                "status": JobStatus.FAILED,
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
                timeout=10,
            )
            response.raise_for_status()
            job_updates[db_job_id] = response.json()

        except requests.RequestException as e:
            logger.error(
                "[GET REDIS JOBS STATUS] Failed to get status for job with ID %s, error: %s",
                db_job_id,
                e,
            )
            job_updates[db_job_id] = {"status": JobStatus.UNKNOWN, "error": str(e)}

    return job_updates


def update_jobs_status(job_updates: dict[str, dict]) -> None:
    updated_count = 0

    valid_statuses = {
        JobStatus.QUEUED,
        JobStatus.RUNNING,
        JobStatus.COMPLETED,
        JobStatus.FAILED,
        JobStatus.UNKNOWN,
        JobStatus.NOT_FOUND,
    }

    for job_id, job_data in job_updates.items():
        status = job_data.get("status")
        logger.info(
            "[UPDATE JOBS STATUS] Processing job %s with status %s",
            job_id,
            status,
        )

        if status not in valid_statuses:
            logger.warning(
                "[UPDATE JOBS STATUS] Skipping job %s with status %s",
                job_id,
                status,
            )
            continue

        for field in ("started_at", "finished_at"):
            if job_data.get(field):
                job_data[field] = datetime.fromisoformat(
                    job_data[field].replace("Z", "+00:00")
                ).replace(tzinfo=None)
        updated = update_job_status(job_id, job_data)
        if updated:
            updated_count += 1

    logger.info(
        "[UPDATE JOBS STATUS] Successfully updated %d jobs.",
        updated_count,
    )


def update_documents_status(
    submitted_documents: dict[str, dict], failed_documents: dict[str, dict]
) -> None:

    for document_id, job_data in submitted_documents.items():
        insert_parsing_job(job_data)
        update_document_submission_status(document_id, "SUBMITTED")

    for document_id in failed_documents:
        update_document_submission_status(document_id, "FAILED")


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

    # 6. Update SQL documents tables
    update_documents_status(submitted_documents, failed_documents)

    logger.info("[PARSING JOBS] Submitted documents: %s", submitted_documents)
    logger.info("[PARSING JOBS] Failed documents: %s", failed_documents)
    logger.info("[PARSING JOBS] Finished submitting parsing jobs.")
    logger.info("=" * 80)
    return None
