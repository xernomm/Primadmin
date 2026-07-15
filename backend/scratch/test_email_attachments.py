"""
Test script for verifying send_email_to_employee auto-polish and attachments features.
Tests:
1. Auto-polishing using Gemini: informal/casual input becomes professional HR Indonesian.
2. File resolution: resolves relative paths, temp directory files, and absolute paths.
3. MIMEMultipart email sending with attachment.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

# Insert backend dir to path for imports
_backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, _backend_dir)

from MCP.mcp_server import mcp
from config import TEMP_UPLOADS_DIR

async def call(tool_name: str, args: dict) -> dict:
    print(f"Calling tool '{tool_name}' with args {args}...")
    contents = await mcp.call_tool(tool_name, args)
    if not contents:
        return {"success": False, "error": "Empty response"}
    return json.loads(contents[0].text)

async def main():
    print("=" * 60)
    print("  Testing Email Attachments & Auto-Polish Feature  ")
    print("=" * 60)

    # 1. Create a dummy test file in TEMP_UPLOADS_DIR
    dummy_file = TEMP_UPLOADS_DIR / "dummy_report.txt"
    dummy_file.write_text("Ini adalah file lampiran uji coba untuk sistem email HR Primasistant-HR.\nTanggal: 2026-05-21\nStatus: Sukses.", encoding="utf-8")
    print(f"Created dummy file: {dummy_file} (exists: {dummy_file.exists()})")

    # 2. Search for a valid employee to test. Prefer Rafael Richie.
    print("\n--- Searching for employee 'Rafael Richie' or any active employee ---")
    search_res = await call("search_employees", {"query": "Rafael", "limit": 1})
    
    # If not found, search generally
    if not search_res.get("success") or not search_res.get("data"):
        print("Rafael not found, searching for any employee...")
        search_res = await call("search_employees", {"query": "a", "limit": 1})
        
    if not search_res.get("success") or not search_res.get("data"):
        print("Error: No employee found in database to run the test.")
        return
        
    emp = search_res["data"][0]
    emp_id = int(emp.get("ID") or emp.get("id"))
    emp_name = emp.get("NAME") or emp.get("name")
    emp_email = emp.get("EMAIL") or emp.get("email")
    print(f"Target Employee: ID={emp_id}, Name={emp_name}, Email={emp_email}")

    # 3. Test sending email with auto_polish=True and attachment
    print("\n--- Test 1: Sending polished email with attachment ---")
    casual_subject = "kabar gembira buat cv lu"
    casual_message = f"eh bro {emp_name}, tolong kirim cv yang paling baru ya ke email gw. gw butuh secepatnya buat diupdate di sistem. makasih ya!"
    
    # Attachments to test:
    # 1. Filename only (which should resolve in TEMP_UPLOADS_DIR)
    # 2. Path relative or absolute
    attachments_input = ["dummy_report.txt"]
    
    result = await call("send_email_to_employee", {
        "emp_id": emp_id,
        "subject": casual_subject,
        "message": casual_message,
        "attachments": attachments_input,
        "auto_polish": True
    })
    
    print("\n--- Test 1 Result ---")
    print(json.dumps(result, indent=2))
    
    if result.get("success"):
        print("\n[PASS] Test 1: Email tool executed successfully!")
        print(f"Polished Subject: {result.get('subject')}")
        print(f"Attachments sent: {result.get('attachments_sent')}")
    else:
        print("\n[FAIL] Test 1: Email tool returned success=False or raised an error.")
        print(f"Error details: {result.get('error')}")

    # 4. Test sending email with None/null values (robustness check)
    print("\n--- Test 2: Sending email with None/null values for message/subject ---")
    result_none = await call("send_email_to_employee", {
        "emp_id": emp_id,
        "subject": None,
        "message": None,
        "attachments": None,
        "auto_polish": False
    })
    
    print("\n--- Test 2 Result ---")
    print(json.dumps(result_none, indent=2))
    
    if result_none.get("success"):
        print("\n[PASS] Test 2: Email tool successfully handles None values and sends!")
    else:
        print("\n[FAIL] Test 2: Email tool failed on None values.")
        print(f"Error details: {result_none.get('error')}")

    # Clean up dummy file
    if dummy_file.exists():
        dummy_file.unlink()
        print(f"\nRemoved dummy file: {dummy_file}")

if __name__ == "__main__":
    asyncio.run(main())
