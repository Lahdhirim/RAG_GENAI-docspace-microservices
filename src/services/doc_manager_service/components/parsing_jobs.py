import os

import requests
from database.queries import get_documents_to_parse
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
                "filename": document.filename,
                "relative_path": document.relative_path,
                "status": "SUBMITTED",
                "error": None,
                "job_id": response.json().get("job_id"),
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
                "filename": document.filename,
                "relative_path": document.relative_path,
                "status": "FAILED",
                "error": str(e),
                "job_id": None,
            }

    return submitted_documents, failed_documents


def parse_documents(output_dir: str):
    logger.info("=" * 80)
    logger.info("[PARSING JOBS] Submitting parsing jobs.")
    os.makedirs(output_dir, exist_ok=True)

    # 1. Retrieve the list of documents that need parsing
    documents_to_parse = get_documents_to_parse()
    logger.info(
        "[PARSING JOBS] Retrieved %d documents to parse.", len(documents_to_parse)
    )

    # 2. Submit parsing jobs to the parser service
    submitted_documents, failed_documents = submit_parsing_jobs(documents_to_parse)

    logger.info("[PARSING JOBS] Submitted documents: %s", submitted_documents)
    logger.info("[PARSING JOBS] Failed documents: %s", failed_documents)
    logger.info("[PARSING JOBS] Finished submitting parsing jobs.")
    logger.info("=" * 80)
    return None


parse_documents("app/silver")
