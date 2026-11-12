import os

import mysql.connector
from dotenv import load_dotenv
from utils.logger import create_logger

load_dotenv()

logger = create_logger("database", "logs/database.log")

env = os.getenv("ENV", "development")
host = "db" if env == "production" else "localhost"
logger.info("[CONNECTION] Connecting to database host: %s", host)
connection = mysql.connector.connect(
    host=host,
    user="root",
    password=os.getenv("MYSQL_ROOT_PASSWORD"),
    database=os.getenv("MYSQL_DATABASE"),
    autocommit=True,
)


if connection.is_connected():
    logger.info("[CONNECTION] Connection to the database was successful.")
    cursor = connection.cursor()
    cursor.execute("SELECT DATABASE()")
    record = cursor.fetchone()
    logger.info("[CONNECTION] You're connected to database: %s", record)
else:
    logger.error("[CONNECTION] Failed to connect to the database.")
    connection.close()
