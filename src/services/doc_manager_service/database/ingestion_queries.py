import os
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from database.connection import connection

cursor = connection.cursor(dictionary=True)
DATASET = os.getenv("GRAPH_RAG_DATASET", "docspace")

LATEST_MARKDOWN_JOB = """
    SELECT latest.job_id FROM jobs latest
    WHERE latest.document_id = d.id AND latest.status = 'COMPLETED'
      AND latest.content IS NOT NULL AND TRIM(latest.content) <> ''
      AND latest.silver_relative_path IS NOT NULL
    ORDER BY latest.submitted_at DESC, latest.job_id DESC LIMIT 1
"""

DOCUMENT_INGESTION_STATE = f"""
    EXISTS (
        SELECT 1 FROM ingestion_jobs ingestion
        WHERE ingestion.document_id = d.id
          AND ingestion.parser_job_id = ({LATEST_MARKDOWN_JOB})
          AND ingestion.dataset = %s AND ingestion.status = 'COMPLETED'
    ) AS is_ingested
"""

SOURCE_QUERY = f"""
    SELECT d.id AS document_id, d.file_name, d.extension,
           j.job_id AS parser_job_id, j.content
    FROM documents d JOIN jobs j ON j.document_id = d.id
    WHERE d.is_present = TRUE AND d.is_parsed = TRUE
      AND j.job_id = ({LATEST_MARKDOWN_JOB})
"""


def get_documents_to_ingest() -> list[dict]:
    """Find the next parsed document version with no ingestion attempt."""
    cursor.execute(
        SOURCE_QUERY + """
        AND NOT EXISTS (
            SELECT 1 FROM ingestion_jobs ingestion
            WHERE ingestion.document_id = d.id
              AND ingestion.parser_job_id = j.job_id AND ingestion.dataset = %s
        )
        ORDER BY j.submitted_at, j.job_id LIMIT 1
        """,
        (DATASET,),
    )
    return cursor.fetchall()


def get_active_ingestion_jobs() -> list[dict]:
    """Return unfinished ingestion jobs with their original Markdown content."""
    cursor.execute(
        """
        SELECT ingestion.*, d.file_name, d.extension, j.content
        FROM ingestion_jobs ingestion
        JOIN documents d ON d.id = ingestion.document_id
        JOIN jobs j ON j.job_id = ingestion.parser_job_id
        WHERE ingestion.dataset = %s
          AND ingestion.status IN ('PENDING', 'QUEUED', 'RUNNING')
        ORDER BY ingestion.submitted_at, ingestion.job_id
        """,
        (DATASET,),
    )
    return cursor.fetchall()


def reserve_ingestion_job(source: dict, attempt: int = 1) -> dict:
    """Record an ingestion attempt before contacting the graph service."""
    job_id = str(
        uuid5(
            NAMESPACE_URL,
            f"docspace-ingestion:{DATASET}:{source['document_id']}:{source['parser_job_id']}:{attempt}",
        )
    )
    # A duplicate reservation keeps the same remote job ID after a lost response.
    cursor.execute(
        """
        INSERT INTO ingestion_jobs
            (job_id, document_id, parser_job_id, dataset, attempt, status)
        VALUES (%s, %s, %s, %s, %s, 'PENDING')
        ON DUPLICATE KEY UPDATE job_id = job_id
        """,
        (job_id, source["document_id"], source["parser_job_id"], DATASET, attempt),
    )
    connection.commit()
    return {**source, "job_id": job_id, "dataset": DATASET, "status": "PENDING"}


def update_ingestion_job(job_id: str, job_data: dict) -> None:
    """Save a remote job status without overwriting an already finished attempt."""
    dates = {}
    for field in ("started_at", "finished_at"):
        value = job_data.get(field)
        if value:
            value = datetime.fromisoformat(value)
            if value.tzinfo is not None:
                value = value.astimezone(UTC).replace(tzinfo=None)
        dates[field] = value or None
    cursor.execute(
        """
        UPDATE ingestion_jobs
        SET status = %s, started_at = COALESCE(%s, started_at),
            finished_at = COALESCE(%s, finished_at), error = %s
        WHERE job_id = %s AND status IN ('PENDING', 'QUEUED', 'RUNNING')
        """,
        (
            job_data["status"],
            dates["started_at"],
            dates["finished_at"],
            job_data.get("error"),
            job_id,
        ),
    )
    connection.commit()


def record_ingestion_poll_error(job_id: str, message: str) -> None:
    """Keep an unfinished job pending while its service cannot be reached."""
    cursor.execute(
        """
        UPDATE ingestion_jobs SET error = %s
        WHERE job_id = %s AND status IN ('PENDING', 'QUEUED', 'RUNNING')
        """,
        (message, job_id),
    )
    connection.commit()


def get_ingestion_statuses_query() -> list[dict]:
    """Return ingestion attempts with their document names and current states."""
    cursor.execute(
        """
        SELECT ingestion.*, d.file_name AS filename
        FROM ingestion_jobs ingestion
        JOIN documents d ON d.id = ingestion.document_id
        WHERE ingestion.dataset = %s
        ORDER BY ingestion.submitted_at DESC, ingestion.attempt DESC
        """,
        (DATASET,),
    )
    return cursor.fetchall()


def retry_document_ingestion(document_id: str) -> dict:
    """Create a new ingestion attempt for a failed document version."""
    cursor.execute(SOURCE_QUERY + " AND d.id = %s", (document_id,))
    source = cursor.fetchone()
    if source is None:
        raise ValueError("This document has no completed Markdown output to ingest.")
    cursor.execute(
        """
        SELECT status, attempt FROM ingestion_jobs
        WHERE document_id = %s AND parser_job_id = %s AND dataset = %s
        ORDER BY attempt DESC LIMIT 1
        """,
        (document_id, source["parser_job_id"], DATASET),
    )
    previous = cursor.fetchone()
    if previous is None or previous["status"] != "FAILED":
        raise ValueError("Only a failed ingestion can be retried.")
    job = reserve_ingestion_job(source, previous["attempt"] + 1)
    return {
        "job_id": job["job_id"],
        "document_id": document_id,
        "parser_job_id": source["parser_job_id"],
        "dataset": DATASET,
        "status": job["status"],
    }
