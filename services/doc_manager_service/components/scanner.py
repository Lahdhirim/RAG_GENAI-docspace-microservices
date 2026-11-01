import os
import hashlib
from datetime import datetime
from models.document import Document

def timeConvert(atime):
  dt = atime
  newtime = datetime.fromtimestamp(dt)
  return newtime.date()

def scan_documents(directory) -> list[Document]:
    documents = []
    for root, _, files in os.walk(directory):
        for file in files:
            # Relative path
            relative_path = os.path.relpath(os.path.join(root, file), directory)
            relative_path_hash = hashlib.sha256(relative_path.encode()).hexdigest()

            # Metadatas
            stats = os.stat(os.path.join(root, file))

            # Content
            with open(os.path.join(root, file), "rb") as f:
                content_hash = hashlib.sha256(f.read()).hexdigest()

            # Append the document to the list
            documents.append(Document(
                id=relative_path_hash,
                relative_path=relative_path,
                content_hash=content_hash,
                size_bytes=stats.st_size,
                file_created_at=str(timeConvert(stats.st_atime)),
                file_modified_at=str(timeConvert(stats.st_mtime)),
                file_accessed_at=str(timeConvert(stats.st_atime))
            ))
    return documents
