import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()
connection = mysql.connector.connect(
    host="db",
    user="root",
    password=os.getenv("MYSQL_ROOT_PASSWORD"),
    database=os.getenv("MYSQL_DATABASE"),
    autocommit=True
)


if connection.is_connected():
    print("Connection to the database was successful.")
    cursor = connection.cursor()
    cursor.execute("SELECT DATABASE()")
    record = cursor.fetchone()
    print("You're connected to database: ", record)
else:
    print("Failed to connect to the database.")
    connection.close()