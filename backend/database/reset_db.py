import os
import cx_Oracle
from dotenv import load_dotenv

load_dotenv()

ORACLE_USER = os.getenv("ORACLE_USER")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD")
ORACLE_HOST = os.getenv("ORACLE_HOST")
ORACLE_PORT = os.getenv("ORACLE_PORT")
ORACLE_SERVICE = os.getenv("ORACLE_SERVICE_NAME")

dsn = cx_Oracle.makedsn(ORACLE_HOST, ORACLE_PORT, service_name=ORACLE_SERVICE)

def get_connection():
    return cx_Oracle.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=dsn)

def drop_tables():
    conn = get_connection()
    cur = conn.cursor()
    
    tables = [
        "messages", "conversations", "warnings", "attendance", "documents", # New tables dependent on others
        "employee_details", "absensi", "leaves", "chat_history", # Old tables dependent on others
        "employees", "hr_users", "users" # Base tables
    ]
    
    for table in tables:
        try:
            print(f"Dropping table {table}...")
            cur.execute(f"DROP TABLE {table} CASCADE CONSTRAINTS")
            print(f"  Dropped {table}.")
        except cx_Oracle.DatabaseError as e:
            error, = e.args
            if error.code == 942: # Table or view does not exist
                print(f"  Table {table} does not exist.")
            else:
                print(f"  Error dropping {table}: {e}")
                
    conn.commit()
    cur.close()
    conn.close()
    print("Reset complete.")

if __name__ == "__main__":
    drop_tables()
