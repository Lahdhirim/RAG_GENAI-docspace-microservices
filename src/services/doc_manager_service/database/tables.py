import logging

from database.connection import connection, cursor

logger = logging.getLogger("database")

# Create the documents table
my_table_creation_query = """
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
    is_parsed BOOLEAN NOT NULL DEFAULT FALSE,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP
);
"""
try:
    cursor.execute(my_table_creation_query)
    logger.info("[TABLES DOCUMENTS] Table created successfully.")
except Exception as e:
    logger.error("[TABLES DOCUMENTS] Error creating table: %s", e)

# Create the jobs table
my_jobs_creation_query = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id VARCHAR(64) PRIMARY KEY,
    document_id CHAR(64) NOT NULL,

    submitted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status ENUM('QUEUED', 'NOT_FOUND', 'RUNNING', 'COMPLETED', 'FAILED', 'NOT_STARTED')
        NOT NULL DEFAULT 'NOT_STARTED',

    started_at DATETIME NULL,
    finished_at DATETIME NULL,

    waiting_duration FLOAT NULL,
    execution_duration FLOAT NULL,

    error TEXT NULL,

    FOREIGN KEY (document_id) REFERENCES documents(id)
);
"""

try:
    cursor.execute(my_jobs_creation_query)
    logger.info("[TABLES JOBS] Table created successfully.")
except Exception as e:
    logger.error("[TABLES JOBS] Error creating table: %s", e)

# Close the cursor and connection to the database
cursor.close()
connection.close()
