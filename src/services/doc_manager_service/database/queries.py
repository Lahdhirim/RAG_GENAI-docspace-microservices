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
                    is_parsed=row[10],
                    created_at=row[11],
                    updated_at=row[12],
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
                is_parsed=row[10],
                created_at=row[11],
                updated_at=row[12],
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
            "SELECT job_id, document_id, status FROM jobs WHERE status IN ('QUEUED', 'RUNNING')"
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


def update_jobs_status(job_updates: dict[str, dict]) -> None:
    try:
        updated_count = 0

        for job_id, job_data in job_updates.items():
            status = job_data.get("status")
            if status not in {"QUEUED", "RUNNING", "COMPLETED", "FAILED"}:
                logger.warning(
                    "[UPDATE JOBS STATUS] Skipping job %s with status %s",
                    job_id,
                    status,
                )
                continue

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
                  AND status IN ('QUEUED', 'RUNNING')
                """,
                (
                    status,
                    job_data.get("started_at"),
                    job_data.get("finished_at"),
                    job_data.get("waiting_duration"),
                    job_data.get("execution_duration"),
                    job_id,
                ),
            )

            if cursor.rowcount > 0:
                updated_count += 1

        connection.commit()

        logger.info(
            "[UPDATE JOBS STATUS] Successfully updated %d jobs.",
            updated_count,
        )

    except Exception as e:
        logger.error(f"[UPDATE JOBS STATUS] Error updating jobs status: {e}")
        connection.rollback()
        raise


def get_documents_to_parse() -> list[Document]:
    try:
        cursor.execute("""
                SELECT *
                FROM documents
                WHERE is_parsed = FALSE
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
                    is_parsed=row[10],
                    created_at=row[11],
                    updated_at=row[12],
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
