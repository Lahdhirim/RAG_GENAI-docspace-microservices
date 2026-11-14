import logging

from database.connection import connection, cursor

logger = logging.getLogger("database")

# Create the documents table
documents_creation_query = """
CREATE TABLE IF NOT EXISTS documents (
    id CHAR(64) PRIMARY KEY,
    relative_path VARCHAR(1024) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    extension VARCHAR(10) NOT NULL,
    content_hash CHAR(64) NOT NULL,

    size_bytes BIGINT UNSIGNED NOT NULL,
    file_created_at DATETIME NULL,
    file_modified_at DATETIME NULL,
    file_accessed_at DATETIME NULL,

    is_present BOOLEAN NOT NULL DEFAULT TRUE,
    submission_status ENUM('NOT_SUBMITTED', 'SUBMITTED', 'FAILED')
        NOT NULL DEFAULT 'NOT_SUBMITTED',
    submission_error TEXT NULL,
    is_parsed BOOLEAN NOT NULL DEFAULT FALSE,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_documents_to_parse (submission_status, is_parsed, is_present)
);
"""
try:
    cursor.execute(documents_creation_query)
    logger.info("[TABLES DOCUMENTS] Table created successfully.")
except Exception as e:
    logger.error("[TABLES DOCUMENTS] Error creating table: %s", e)
    raise e

# Create the jobs table
jobs_creation_query = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id VARCHAR(64) PRIMARY KEY,
    document_id CHAR(64) NOT NULL,
    relative_path VARCHAR(1024) NOT NULL,

    submitted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status ENUM('QUEUED', 'NOT_FOUND', 'RUNNING', 'COMPLETED', 'FAILED', 'NOT_STARTED', 'UNKNOWN')
        NOT NULL DEFAULT 'NOT_STARTED',

    started_at DATETIME NULL,
    finished_at DATETIME NULL,

    waiting_duration FLOAT NULL,
    execution_duration FLOAT NULL,

    content LONGTEXT NULL,
    silver_relative_path VARCHAR(1024) NULL,
    error TEXT NULL,

    INDEX idx_jobs_status (status),
    INDEX idx_jobs_document_status (document_id, status),
    FOREIGN KEY (document_id) REFERENCES documents(id)
);
"""

try:
    cursor.execute(jobs_creation_query)
    logger.info("[TABLES JOBS] Table created successfully.")
except Exception as e:
    logger.error("[TABLES JOBS] Error creating table: %s", e)
    raise e

ingestion_jobs_creation_query = """
CREATE TABLE IF NOT EXISTS ingestion_jobs (
    job_id CHAR(36) PRIMARY KEY,
    document_id CHAR(64) NOT NULL,
    parser_job_id VARCHAR(64) NOT NULL,
    dataset VARCHAR(128) NOT NULL,
    attempt INT UNSIGNED NOT NULL DEFAULT 1,
    status ENUM('PENDING', 'QUEUED', 'RUNNING', 'COMPLETED', 'FAILED')
        NOT NULL DEFAULT 'PENDING',
    submitted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME NULL,
    finished_at DATETIME NULL,
    error TEXT NULL,
    UNIQUE KEY idx_ingestion_version (document_id, parser_job_id, dataset, attempt),
    INDEX idx_ingestion_status (dataset, status),
    FOREIGN KEY (document_id) REFERENCES documents(id),
    FOREIGN KEY (parser_job_id) REFERENCES jobs(job_id)
);
"""

try:
    cursor.execute(ingestion_jobs_creation_query)
    logger.info("[TABLES INGESTION JOBS] Table created successfully.")
except Exception:
    logger.exception("[TABLES INGESTION JOBS] Could not create the table.")
    raise

# Close the cursor and connection to the database
cursor.close()
connection.close()
