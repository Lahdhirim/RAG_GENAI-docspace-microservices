from database.connection import connection, cursor

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
    print("Table created successfully.")
except Exception as e:
    print("Error creating table:", e)

# Close the cursor and connection to the database
cursor.close()
connection.close()
