from database.connection import cursor, connection
from models.document import Document

def add_document_query(document : Document):
    try:
        cursor.execute(
            "INSERT INTO documents (id, relative_path, file_name, extension, content_hash, size_bytes, file_created_at, file_modified_at, file_accessed_at) VALUES (%s, %s, %s,%s, %s, %s, %s, %s, %s)",
            (document.id, document.relative_path, document.filename, document.extension, document.content_hash, document.size_bytes, document.file_created_at, document.file_modified_at, document.file_accessed_at)
        )
        connection.commit()
        print("Document added successfully.")
    except Exception as e:
        print("Error adding document:", e)

def get_documents_query() -> list[Document]:
    try:
        connection.commit()
        cursor.execute("SELECT * FROM documents")
        rows = cursor.fetchall()
        documents = []
        for row in rows:
            documents.append(Document(
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
                updated_at=row[12]
            ))
        return documents
    except Exception as e:
        print("Error fetching documents:", e)
        return []

def get_document_query(document_id: str) -> Document:
    try:
        cursor.execute(
            "SELECT * FROM documents WHERE id = %s",
            (document_id,)
        )
        row = cursor.fetchone()
        if row:
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
                updated_at=row[12]
            )
        return None
    except Exception as e:
        print("Error fetching document:", e)
        return None