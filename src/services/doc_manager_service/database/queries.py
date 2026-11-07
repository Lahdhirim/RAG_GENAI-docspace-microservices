from database.connection import connection, cursor
from models.document import Document
from utils.logger import create_logger

logger = create_logger("database", "logs/database.log")


def add_document_query(document: Document) -> tuple[bool, Exception | None]:
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
        return True, None
    except Exception as e:
        logger.error(f"[ADD DOCUMENT] Error adding document: {e}")
        connection.rollback()
        return False, e


def mark_document_as_present_query(document_id: str) -> tuple[bool, Exception | None]:
    try:
        cursor.execute(
            "UPDATE documents SET is_present = TRUE WHERE id = %s AND is_present = FALSE",
            (document_id,),
        )

        if cursor.rowcount == 0:
            connection.rollback()
            error = ValueError(f"No document updated for ID: {document_id}")
            logger.warning(f"[MARK DOCUMENT AS PRESENT] {error}")
            return False, error

        connection.commit()
        logger.info(
            f"[MARK DOCUMENT AS PRESENT] Document marked as present: {document_id}"
        )
        return True, None
    except Exception as e:
        logger.error(
            f"[MARK DOCUMENT AS PRESENT] Error: {e}, Document ID: {document_id}"
        )
        connection.rollback()
        return False, e


def mark_document_as_deleted_query(document_id: str) -> tuple[bool, Exception | None]:
    try:
        cursor.execute(
            "UPDATE documents SET is_present = FALSE WHERE id = %s AND is_present = TRUE",
            (document_id,),
        )

        if cursor.rowcount == 0:
            connection.rollback()
            error = ValueError(f"No document updated for ID: {document_id}")
            logger.warning(f"[MARK DOCUMENT AS DELETED] {error}")
            return False, error

        connection.commit()
        logger.info(
            f"[MARK DOCUMENT AS DELETED] Document marked as absent: {document_id}"
        )
        return True, None
    except Exception as e:
        logger.error(
            f"[MARK DOCUMENT AS DELETED] Error: {e}, Document ID: {document_id}"
        )
        connection.rollback()
        return False, e


def get_documents_query() -> list[Document]:
    try:
        connection.commit()
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
        raise
