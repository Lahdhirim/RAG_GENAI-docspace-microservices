import logging

from database.connection import connection, cursor
from models.document import Document

logger = logging.getLogger("database")


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
                    id=row[0],
                    relative_path=row[1],
                    filename=row[2],
                    extension=row[3],
                    content_hash=row[4],
                    size_bytes=row[5],
                    file_created_at=row[6],
                    file_modified_at=row[7],
                    file_accessed_at=row[8],
                    is_present=row[9],
                    submission_status=row[10],
                    is_parsed=row[11],
                    created_at=row[12],
                    updated_at=row[13],
                )
            )
        logger.info(f"[GET DOCUMENTS] Fetched {len(documents)} documents.")
        return documents
    except Exception as e:
        logger.error(f"[GET DOCUMENTS] Error fetching documents: {e}")
        connection.rollback()
        raise


def get_document_query(document_id: str) -> Document:
    try:
        cursor.execute("SELECT * FROM documents WHERE id = %s", (document_id,))
        row = cursor.fetchone()
        if row:
            logger.info(f"[GET DOCUMENT] Document found with ID: {document_id}")
            return Document(
                id=row[0],
                relative_path=row[1],
                filename=row[2],
                extension=row[3],
                content_hash=row[4],
                size_bytes=row[5],
                file_created_at=row[6],
                file_modified_at=row[7],
                file_accessed_at=row[8],
                is_present=row[9],
                submission_status=row[10],
                is_parsed=row[11],
                created_at=row[12],
                updated_at=row[13],
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
                    "job_id": row[0],
                    "document_id": row[1],
                    "status": row[2],
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
    try:
        cursor.execute(
            """
            UPDATE jobs
            SET
                status = %s,
                started_at = COALESCE(%s, started_at),
                finished_at = COALESCE(%s, finished_at),
                waiting_duration = COALESCE(%s, waiting_duration),
                execution_duration = COALESCE(%s, execution_duration)
            WHERE job_id = %s
              AND status IN ('QUEUED', 'RUNNING', 'UNKNOWN')
            """,
            (
                job_data["status"],
                job_data.get("started_at"),
                job_data.get("finished_at"),
                job_data.get("waiting_duration"),
                job_data.get("execution_duration"),
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
                    id=row[0],
                    relative_path=row[1],
                    filename=row[2],
                    extension=row[3],
                    content_hash=row[4],
                    size_bytes=row[5],
                    file_created_at=row[6],
                    file_modified_at=row[7],
                    file_accessed_at=row[8],
                    is_present=row[9],
                    submission_status=row[10],
                    is_parsed=row[11],
                    created_at=row[12],
                    updated_at=row[13],
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
                status
            )
            VALUES (%s, %s, %s, %s)
            """,
            (
                job_data["job_id"],
                job_data["document_id"],
                job_data["submitted_at"],
                job_data["status"],
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
) -> None:
    try:
        cursor.execute(
            """
            UPDATE documents
            SET submission_status = %s
            WHERE id = %s
            """,
            (submission_status, document_id),
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


def get_parsing_jobs_query(document_id: str | None = None) -> list[dict]:
    """Read SQL job history with document metadata; never contact the parser."""
    columns = (
        "job_id",
        "document_id",
        "submitted_at",
        "status",
        "started_at",
        "finished_at",
        "waiting_duration",
        "execution_duration",
        "error",
        "filename",
        "relative_path",
    )
    sql = """
        SELECT j.job_id, j.document_id, j.submitted_at, j.status,
               j.started_at, j.finished_at, j.waiting_duration,
               j.execution_duration, j.error,
               d.file_name AS filename, d.relative_path
        FROM jobs AS j
        LEFT JOIN documents AS d ON d.id = j.document_id
    """
    parameters = ()
    if document_id is not None:
        sql += " WHERE j.document_id = %s"
        parameters = (document_id,)
    sql += " ORDER BY j.submitted_at DESC, j.job_id DESC"
    try:
        cursor.execute(sql, parameters)
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except Exception:
        logger.exception("[GET PARSING JOBS] Failed to read job history")
        connection.rollback()
        raise
