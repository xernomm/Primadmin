import asyncio
import os
import sys
from dotenv import load_dotenv

# Add backend to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from MCP.tools.sql_generator import generate_and_execute_sql

def test_hallucination_fix():
    load_dotenv()
    print("Testing hallucination fix with a query about leave history...")
    
    # This query usually triggers the 'leaves' table hallucination
    natural_query = "Tampilkan riwayat cuti (tanggal dan alasan) karyawan bernama Rafael Richie"
    
    result = generate_and_execute_sql(natural_query, execute=True)
    
    print("\n--- Result ---")
    print(f"Success: {result.get('success')}")
    if result.get('success'):
        print(f"SQL Generated: {result.get('generated_sql')}")
        print(f"Data Count: {len(result.get('data', []))}")
        if result.get('data'):
            print(f"Sample Data: {result.get('data')[0]}")
    else:
        print(f"Error: {result.get('error')}")
        if 'generated_sql' in result:
            print(f"Failed SQL: {result.get('generated_sql')}")

if __name__ == "__main__":
    test_hallucination_fix()
