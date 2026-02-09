import sys
import os
import cx_Oracle
import traceback
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
load_dotenv()

ORACLE_USER = os.getenv("ORACLE_USER")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD")
ORACLE_HOST = os.getenv("ORACLE_HOST")
ORACLE_PORT = os.getenv("ORACLE_PORT")
ORACLE_SERVICE = os.getenv("ORACLE_SERVICE_NAME")

print(f"Connecting as {ORACLE_USER}...")

dsn = cx_Oracle.makedsn(ORACLE_HOST, ORACLE_PORT, service_name=ORACLE_SERVICE)
db_url = f"oracle+cx_oracle://{ORACLE_USER}:{ORACLE_PASSWORD}@{dsn}"
engine = create_engine(db_url)

def test_query(query):
    print(f"\nEXECUTING: {query}")
    try:
        with engine.connect() as conn:
            result = conn.execute(text(query))
            rows = result.fetchall()
            print(f"✅ SUCCESS. Row count: {len(rows)}")
            if rows:
                print("First row:", rows[0])
    except Exception as e:
        print(f"❌ FAILED: {str(e)}")

# Test 1: No prefix
test_query("SELECT * FROM attendance FETCH FIRST 1 ROWS ONLY")

# Test 2: With SMARTBOT prefix
test_query("SELECT * FROM SMARTBOT.attendance FETCH FIRST 1 ROWS ONLY")

# Test 3: Test JOIN (which failed in tool)
test_query("""
    SELECT a.id, e.name 
    FROM SMARTBOT.attendance a 
    JOIN SMARTBOT.employees e ON a.employee_id = e.id 
    FETCH FIRST 1 ROWS ONLY
""")
