import sys
import os
import cx_Oracle
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Add path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

load_dotenv()

ORACLE_USER = os.getenv("ORACLE_USER")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD")
ORACLE_HOST = os.getenv("ORACLE_HOST")
ORACLE_PORT = os.getenv("ORACLE_PORT")
ORACLE_SERVICE = os.getenv("ORACLE_SERVICE_NAME")
ORACLE_SCHEMA = os.getenv("ORACLE_SCHEMA", "SMARTBOT")

dsn = cx_Oracle.makedsn(ORACLE_HOST, ORACLE_PORT, service_name=ORACLE_SERVICE)
db_url = f"oracle+cx_oracle://{ORACLE_USER}:{ORACLE_PASSWORD}@{dsn}"
engine = create_engine(db_url)

print(f"Connecting to {ORACLE_HOST} service={ORACLE_SERVICE} as {ORACLE_USER}")
print(f"Target Schema: {ORACLE_SCHEMA}")

try:
    with engine.connect() as conn:
        # 1. Check ALL tables in target schema
        print(f"\n--- TABLES IN {ORACLE_SCHEMA} ---")
        result = conn.execute(text(f"SELECT table_name FROM all_tables WHERE owner = '{ORACLE_SCHEMA}'"))
        tables = [row[0] for row in result]
        print(tables)

        # 2. Check tabels owned by current user (if different)
        if ORACLE_USER.upper() != ORACLE_SCHEMA.upper():
            print(f"\n--- TABLES IN {ORACLE_USER.upper()} (Current User) ---")
            result = conn.execute(text(f"SELECT table_name FROM user_tables"))
            tables = [row[0] for row in result]
            print(tables)

        # 3. Check for 'attendance' specifically in ANY schema
        print("\n--- SEARCHING FOR 'ATTENDANCE' IN ALL SCHEMAS ---")
        result = conn.execute(text("SELECT owner, table_name FROM all_tables WHERE table_name LIKE '%ATTENDANCE%' OR table_name LIKE '%ABSENSI%'"))
        for row in result:
             print(f"{row[0]}.{row[1]}")

except Exception as e:
    print(f"ERROR: {e}")
