import hashlib
import os
from datetime import datetime

from database.queries import (
    add_document_query,
    get_document_query,
    get_documents_query,
    mark_document_as_deleted_query,
    mark_document_as_present_query,
)
from models.document import Document
from utils.logger import create_logger

logger = create_logger("synchroniser", "logs/synchroniser.log")


def timeConvert(atime):
    return datetime.fromtimestamp(atime)


def scan_documents(directory) -> list[Document]:
    """Recursively collect metadata and identify files by path plus content hash.

    Moving or editing a file creates a different identity; synchronization keeps
    the previous record as absent rather than replacing its parsing history.
    """
    logger.info(
        f"[SCAN DOCUMENTS] Scanning documents in directory: {directory}. Time : {datetime.now()}"
    )
    if not os.path.isdir(directory):
        logger.error(f"[SCAN DOCUMENTS] Directory not found: {directory}")
        raise FileNotFoundError(f"Directory not found: {directory}")

    documents = []
    for root, _, files in os.walk(directory):
        for file in files:
            relative_path = os.path.relpath(
                os.path.join(root, file), directory
            ).replace("\\", "/")

            filename, extension = os.path.splitext(file)

            stats = os.stat(os.path.join(root, file))

            with open(os.path.join(root, file), "rb") as f:
                content_hash = hashlib.sha256(f.read()).hexdigest()

            id = hashlib.sha256(
                (relative_path + content_hash).encode("utf-8")
            ).hexdigest()

            documents.append(
                Document(
                    id=id,
                    relative_path=relative_path,
                    filename=filename,
                    extension=extension,
                    content_hash=content_hash,
                    size_bytes=stats.st_size,
                    file_created_at=timeConvert(stats.st_ctime),
                    file_modified_at=timeConvert(stats.st_mtime),
                    file_accessed_at=timeConvert(stats.st_atime),
                )
            )
    logger.info(
        f"[SCAN DOCUMENTS] Finished scanning documents. Total documents found: {len(documents)}"
    )
    return documents


def insert_new_documents(
    local_documents: list[Document], db_documents: list[Document]
) -> tuple[dict, dict]:
    added_documents = {}
    failed_documents = {}
    logger.info("[INSERT NEW DOCUMENTS] Inserting new documents...")
    for local_doc in local_documents:
        local_doc_id = local_doc.id
        if not any(db_doc.id == local_doc_id for db_doc in db_documents):
            logger.info(
                f"[INSERT NEW DOCUMENTS] Inserting new document {local_doc.filename} in {local_doc.relative_path} with ID: {local_doc_id}"
            )

            try:
                add_document_query(local_doc)
                added_documents[local_doc_id] = {
                    "filename": local_doc.filename,
                    "relative_path": local_doc.relative_path,
                    "error": None,
                }
                logger.info(
                    f"[INSERT NEW DOCUMENTS] Document {local_doc.filename} in {local_doc.relative_path} with ID: {local_doc_id} added successfully"
                )

            except Exception as e:
                logger.error(
                    f"[INSERT NEW DOCUMENTS] Failed to add document {local_doc.filename} in {local_doc.relative_path} with ID: {local_doc_id}, Error: {e}"
                )
                failed_documents[local_doc_id] = {
                    "filename": local_doc.filename,
                    "relative_path": local_doc.relative_path,
                    "error": e,
                }

    logger.info(
        f"[INSERT NEW DOCUMENTS] {len(added_documents)} Added documents: {added_documents}"
    )
    logger.info(
        f"[INSERT NEW DOCUMENTS] {len(failed_documents)} Failed documents: {failed_documents}"
    )
    return added_documents, failed_documents


def mark_deleted_documents(
    local_documents: list[Document], db_documents: list[Document]
) -> tuple[dict, dict]:
    marked_documents = {}
    failed_documents = {}
    logger.info("[MARK DOCUMENT AS DELETED] Updating absent documents...")
    for db_document in db_documents:
        db_document_id = db_document.id
        if db_document.is_present and not any(
            local_doc.id == db_document_id for local_doc in local_documents
        ):
            logger.info(
                f"[MARK DOCUMENT AS DELETED] Marking document {db_document.filename} in {db_document.relative_path} with ID: {db_document_id} as absent"
            )

            try:
                mark_document_as_deleted_query(document_id=db_document_id)

                new_doc = get_document_query(db_document_id)

                marked_documents[db_document_id] = {
                    "filename": db_document.filename,
                    "relative_path": db_document.relative_path,
                    "error": None,
                    "changes": {
                        "old_db_new_db": (db_document.is_present, new_doc.is_present)
                    },
                }
                logger.info(
                    f"[MARK DOCUMENT AS DELETED] Document {db_document.filename} in {db_document.relative_path} with ID: {db_document_id} marked as absent successfully"
                )

            except Exception as error:
                logger.error(
                    f"[MARK DOCUMENT AS DELETED] Failed to mark document {db_document.filename} in {db_document.relative_path} with ID: {db_document_id} as absent, Error: {error}"
                )
                failed_documents[db_document_id] = {
                    "filename": db_document.filename,
                    "relative_path": db_document.relative_path,
                    "error": error,
                }

    logger.info(
        f"[MARK DOCUMENT AS DELETED] {len(marked_documents)} Marked as absent documents: {marked_documents}"
    )
    logger.info(
        f"[MARK DOCUMENT AS DELETED] {len(failed_documents)} Failed documents: {failed_documents}"
    )
    return marked_documents, failed_documents


def mark_present_documents(
    local_documents: list[Document], db_documents: list[Document]
) -> tuple[dict, dict]:
    present_documents = {}
    failed_documents = {}

    logger.info("[MARK PRESENT DOCUMENTS] Checking returning documents...")

    for db_document in db_documents:
        db_document_id = db_document.id

        if not db_document.is_present and any(
            local_doc.id == db_document_id for local_doc in local_documents
        ):
            logger.info(
                f"[MARK PRESENT DOCUMENTS] Restoring document {db_document.filename} in {db_document.relative_path} with ID: {db_document_id}"
            )

            try:
                mark_document_as_present_query(document_id=db_document_id)

                new_doc = get_document_query(db_document_id)

                present_documents[db_document_id] = {
                    "filename": db_document.filename,
                    "relative_path": db_document.relative_path,
                    "error": None,
                    "changes": {
                        "old_db_new_db": (db_document.is_present, new_doc.is_present)
                    },
                }

                logger.info(
                    f"[MARK PRESENT DOCUMENTS] Document {db_document.filename} in {db_document.relative_path} with ID: {db_document_id} restored successfully"
                )

            except Exception as error:
                logger.error(
                    f"[MARK PRESENT DOCUMENTS] Failed to restore document {db_document.filename} in {db_document.relative_path} with ID: {db_document_id}, Error: {error}"
                )

                failed_documents[db_document_id] = {
                    "filename": db_document.filename,
                    "relative_path": db_document.relative_path,
                    "error": error,
                }

    logger.info(
        f"[MARK PRESENT DOCUMENTS] {len(present_documents)} Restored documents: {present_documents}"
    )
    logger.info(
        f"[MARK PRESENT DOCUMENTS] {len(failed_documents)} Failed documents: {failed_documents}"
    )

    return present_documents, failed_documents


def sync_documents(directory: str) -> None:
    """Reconcile one filesystem snapshot with SQL, retaining absent records.

    Insert new identities, mark missing ones absent, and restore returning ones.
    Each reconciliation helper reports successes and failures keyed by document ID
    so a database failure for one file does not stop the remaining files.
    """
    logger.info("=" * 80)
    logger.info(
        f"[SYNC DOCUMENTS] Starting document synchronization for directory: {directory}"
    )
    local_documents = scan_documents(directory)

    db_documents = get_documents_query()

    succ2a_documents, f2a_documents = insert_new_documents(
        local_documents=local_documents, db_documents=db_documents
    )

    succ2u_documents, f2u_documents = mark_deleted_documents(
        local_documents=local_documents, db_documents=db_documents
    )

    succ2p_documents, f2p_documents = mark_present_documents(
        local_documents=local_documents, db_documents=db_documents
    )

    logger.info(
        f"[SYNC DOCUMENTS] {len(succ2a_documents)} Successfully added documents: {succ2a_documents}"
    )
    logger.info(
        f"[SYNC DOCUMENTS] {len(f2a_documents)} Failed to add documents: {f2a_documents}"
    )
    logger.info(
        f"[SYNC DOCUMENTS] {len(succ2u_documents)} Successfully updated deleted documents: {succ2u_documents}"
    )
    logger.info(
        f"[SYNC DOCUMENTS] {len(f2u_documents)} Failed to update deleted documents: {f2u_documents}"
    )
    logger.info(
        f"[SYNC DOCUMENTS] {len(succ2p_documents)} Successfully restored present documents: {succ2p_documents}"
    )
    logger.info(
        f"[SYNC DOCUMENTS] {len(f2p_documents)} Failed to restore present documents: {f2p_documents}"
    )

    logger.info(
        f"[SYNC DOCUMENTS] Finished document synchronization for directory: {directory}"
    )
    logger.info("=" * 80)
    return None
