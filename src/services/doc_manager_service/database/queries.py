import logging

from database.connection import connection
from models.document import Document

logger = logging.getLogger("database")
cursor = connection.cursor(dictionary=True)


##################################################### Document Queries ###############################################
def add_document_query(document: Document) -> None:
    try:
        cursor.execute(
            "INSERT INTO documents (id, relative_path, file_name, extension, content_hash, size_bytes, file_created_at, file_modified_at, file_accessed_at) VALUES (%s, %s, %s,%s, %s, %s, %s, %s, %s)",
            (
                document.id,
                document.relative_path,
                document.filename,
                document.extension,
                document.content_hash,
                document.size_bytes,
                document.file_created_at,
                document.file_modified_at,
                document.file_accessed_at,
            ),
        )
        connection.commit()
        logger.info("[ADD DOCUMENT] Document added successfully.")

    except Exception as e:
        logger.error(f"[ADD DOCUMENT] Error adding document: {e}")
        connection.rollback()
        raise


def mark_document_as_present_query(document_id: str) -> None:
    try:
        cursor.execute(
            "UPDATE documents SET is_present = TRUE WHERE id = %s AND is_present = FALSE",
            (document_id,),
        )

        if cursor.rowcount == 0:
            error = ValueError(f"No document updated for ID: {document_id}")
            logger.warning(f"[MARK DOCUMENT AS PRESENT] {error}")
            raise error

        connection.commit()
        logger.info(
            f"[MARK DOCUMENT AS PRESENT] Document marked as present: {document_id}"
        )

    except Exception as e:
        logger.error(
            f"[MARK DOCUMENT AS PRESENT] Error: {e}, Document ID: {document_id}"
        )
        connection.rollback()
        raise


def mark_document_as_deleted_query(document_id: str) -> None:
    try:
        cursor.execute(
            "UPDATE documents SET is_present = FALSE WHERE id = %s AND is_present = TRUE",
            (document_id,),
        )

        if cursor.rowcount == 0:
            error = ValueError(f"No document updated for ID: {document_id}")
            logger.warning(f"[MARK DOCUMENT AS DELETED] {error}")
            raise error

        connection.commit()
        logger.info(
            f"[MARK DOCUMENT AS DELETED] Document marked as absent: {document_id}"
        )

    except Exception as e:
        logger.error(
            f"[MARK DOCUMENT AS DELETED] Error: {e}, Document ID: {document_id}"
        )
        connection.rollback()
        raise


def get_documents_query() -> list[Document]:
    try:
        cursor.execute("SELECT * FROM documents")
        rows = cursor.fetchall()
        documents = []
        for row in rows:
            documents.append(
                Document(
                    id=row["id"],
                    relative_path=row["relative_path"],
                    filename=row["file_name"],
                    extension=row["extension"],
                    content_hash=row["content_hash"],
                    size_bytes=row["size_bytes"],
                    file_created_at=row["file_created_at"],
                    file_modified_at=row["file_modified_at"],
                    file_accessed_at=row["file_accessed_at"],
                    is_present=row["is_present"],
                    submission_status=row["submission_status"],
                    submission_error=row["submission_error"],
                    is_parsed=row["is_parsed"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
            )
        logger.info(f"[GET DOCUMENTS] Fetched {len(documents)} documents.")
        return documents
    except Exception as e:
        logger.error(f"[GET DOCUMENTS] Error fetching documents: {e}")
        connection.rollback()
        raise


def get_document_query(document_id: str) -> Document | None:
    try:
        cursor.execute("SELECT * FROM documents WHERE id = %s", (document_id,))
        row = cursor.fetchone()
        if row:
            logger.info(f"[GET DOCUMENT] Document found with ID: {document_id}")
            return Document(
                id=row["id"],
                relative_path=row["relative_path"],
                filename=row["file_name"],
                extension=row["extension"],
                content_hash=row["content_hash"],
                size_bytes=row["size_bytes"],
                file_created_at=row["file_created_at"],
                file_modified_at=row["file_modified_at"],
                file_accessed_at=row["file_accessed_at"],
                is_present=row["is_present"],
                submission_status=row["submission_status"],
                submission_error=row["submission_error"],
                is_parsed=row["is_parsed"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

        logger.info(f"[GET DOCUMENT] No document found with ID: {document_id}")
        return None

    except Exception as e:
        logger.error(
            f"[GET DOCUMENT] Error fetching document: {e}, Document ID: {document_id}"
        )
        connection.rollback()
        raise


##################################################### Jobs Queries ###############################################
def get_active_parsing_jobs() -> list[dict]:
    try:
        cursor.execute(
            "SELECT job_id, document_id, status FROM jobs WHERE status IN ('QUEUED', 'RUNNING', 'UNKNOWN')"
        )
        rows = cursor.fetchall()
        jobs = []
        for row in rows:
            jobs.append(
                {
                    "job_id": row["job_id"],
                    "document_id": row["document_id"],
                    "status": row["status"],
                }
            )
        logger.info(
            f"[GET ACTIVE PARSING JOBS] Fetched {len(jobs)} active parsing jobs."
        )
        return jobs

    except Exception as e:
        logger.error(
            f"[GET ACTIVE PARSING JOBS] Error fetching active parsing jobs: {e}"
        )
        connection.rollback()
        raise


def update_job_status(job_id: str, job_data: dict) -> bool:
    """Apply partial polling data only while a job is still active.

    COALESCE preserves known metadata when a response omits it or supplies null;
    the status guard prevents later polls from overwriting terminal job states.
    """
    try:
        cursor.execute(
            """
            UPDATE jobs
            SET
                status = %s,
                started_at = COALESCE(%s, started_at),
                finished_at = COALESCE(%s, finished_at),
                waiting_duration = COALESCE(%s, waiting_duration),
                execution_duration = COALESCE(%s, execution_duration),
                content = COALESCE(%s, content),
                silver_relative_path = COALESCE(%s, silver_relative_path),
                error = COALESCE(%s, error)
            WHERE job_id = %s
              AND status IN ('QUEUED', 'RUNNING', 'UNKNOWN')
            """,
            (
                job_data["status"],
                job_data.get("started_at"),
                job_data.get("finished_at"),
                job_data.get("waiting_duration"),
                job_data.get("execution_duration"),
                job_data.get("content"),
                job_data.get("silver_relative_path"),
                job_data.get("error"),
                job_id,
            ),
        )

        updated = cursor.rowcount > 0
        connection.commit()
        return updated

    except Exception:
        logger.exception(
            "[UPDATE JOB STATUS] Error updating job %s",
            job_id,
        )
        connection.rollback()
        raise


def get_documents_to_parse() -> list[Document]:
    """Select present, nonempty documents with no previous submission or job.

    Failed submissions and documents with any job history are excluded; this
    query does not automatically retry them.
    """
    try:
        cursor.execute("""
                SELECT *
                FROM documents
                WHERE is_parsed = FALSE
                AND submission_status = 'NOT_SUBMITTED'
                AND is_present = TRUE
                AND content_hash IS NOT NULL
                AND size_bytes > 0
                AND NOT EXISTS (
                    SELECT 1
                    FROM jobs
                    WHERE jobs.document_id = documents.id
                )
                """)
        rows = cursor.fetchall()
        documents = []
        for row in rows:
            documents.append(
                Document(
                    id=row["id"],
                    relative_path=row["relative_path"],
                    filename=row["file_name"],
                    extension=row["extension"],
                    content_hash=row["content_hash"],
                    size_bytes=row["size_bytes"],
                    file_created_at=row["file_created_at"],
                    file_modified_at=row["file_modified_at"],
                    file_accessed_at=row["file_accessed_at"],
                    is_present=row["is_present"],
                    submission_status=row["submission_status"],
                    submission_error=row["submission_error"],
                    is_parsed=row["is_parsed"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
            )
        logger.info(
            f"[GET DOCUMENTS TO PARSE] Fetched {len(documents)} documents to parse."
        )
        return documents

    except Exception as e:
        logger.error(f"[GET DOCUMENTS TO PARSE] Error fetching documents to parse: {e}")
        connection.rollback()
        raise


def insert_parsing_job(job_data: dict) -> None:
    try:
        cursor.execute(
            """
            INSERT INTO jobs (
                job_id,
                document_id,
                submitted_at,
                status,
                relative_path
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                job_data["job_id"],
                job_data["document_id"],
                job_data["submitted_at"],
                job_data["status"],
                job_data["relative_path"],
            ),
        )
        connection.commit()
        logger.info(
            f"[INSERT PARSING JOB] Successfully inserted parsing job: {job_data}"
        )

    except Exception:
        logger.error(f"[INSERT PARSING JOB] Error inserting parsing job: {job_data}")
        connection.rollback()
        raise


def update_document_submission_status(
    document_id: str,
    submission_status: str,
    submission_error: str | None,
) -> None:
    try:
        cursor.execute(
            """
            UPDATE documents
            SET submission_status = %s,
                submission_error = %s
            WHERE id = %s
            """,
            (submission_status, submission_error, document_id),
        )
        connection.commit()
        logger.info(
            f"[UPDATE DOCUMENT SUBMISSION STATUS] Successfully updated submission status for document: {document_id}"
        )

    except Exception:
        logger.error(
            f"[UPDATE DOCUMENT SUBMISSION STATUS] Error updating submission status for document: {document_id}"
        )
        connection.rollback()
        raise


def get_parsing_statuses_query() -> list[tuple]:
    try:
        cursor.execute("""
            SELECT
                j.job_id,
                j.document_id,
                d.file_name,
                j.status,
                j.submitted_at,
                j.started_at,
                j.finished_at,
                j.waiting_duration,
                j.execution_duration,
                j.error,
                j.silver_relative_path
            FROM jobs j
            JOIN documents d ON d.id = j.document_id
            ORDER BY j.submitted_at DESC
        """)

        rows = cursor.fetchall()
        logger.info(f"[GET PARSING STATUSES] Fetched {len(rows)} parsing jobs.")
        # SELECT column order is the /parsing_statuses tuple contract consumed
        # by the frontend's parseStatusesResponse mapper.
        return [tuple(row[column] for column in cursor.column_names) for row in rows]

    except Exception as e:
        logger.error(f"[GET PARSING STATUSES] Error: {e}")
        connection.rollback()
        raise


def update_is_parsed_status() -> None:
    """Mark parsed only after a completed job has both content and a saved path."""
    try:
        cursor.execute("""
            UPDATE documents d
            SET d.is_parsed = TRUE
            WHERE d.is_parsed = FALSE
              AND EXISTS (
                  SELECT 1
                  FROM jobs j
                  WHERE j.document_id = d.id
                    AND j.status = 'COMPLETED'
                    AND j.content IS NOT NULL
                    AND j.silver_relative_path IS NOT NULL
              )
            """)
        connection.commit()
        logger.info(
            f"[UPDATE IS PARSED STATUS] Successfully updated {cursor.rowcount} documents."
        )

    except Exception as e:
        logger.error(f"[UPDATE IS PARSED STATUS] Error updating documents: {e}")
        connection.rollback()
        raise


def get_markdown_path_query(document_id: str, job_id: str | None = None) -> str | None:
    """Find a completed job's saved path, scoped to its document.

    A job ID selects that exact run; otherwise use the most recently submitted
    completed run that has a path. File availability is checked by the API.
    """
    sql = """
        SELECT silver_relative_path FROM jobs
        WHERE document_id = %s AND status = 'COMPLETED'
          AND silver_relative_path IS NOT NULL
    """
    parameters = [document_id]
    if job_id is not None:
        sql += " AND job_id = %s"
        parameters.append(job_id)
    sql += " ORDER BY submitted_at DESC, job_id DESC LIMIT 1"
    try:
        cursor.execute(sql, tuple(parameters))
        row = cursor.fetchone()
        return row["silver_relative_path"] if row else None
    except Exception:
        logger.exception("[PREVIEW] Could not read Markdown path")
        connection.rollback()
        raise
