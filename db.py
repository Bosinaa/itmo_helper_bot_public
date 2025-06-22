# Подключение к бд в MySQL
import mysql.connector
import os
def connect_db():
    try:
        return mysql.connector.connect(
            host=os.getenv("db_host"),
            user=os.getenv("db_user"),
            password=os.getenv("db_password"),
            database=os.getenv("db_name"),
            #port = "3306"
        )
    except mysql.connector.Error as err:
        print(f"[DB ERROR] {err}")
        return None