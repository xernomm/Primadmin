"""
Test script for Refactored and Consolidated MCP Tools.
Tests:
1. extract_data_from_file
2. update_employee_by_id (dual-table updates)
3. search_employees (consolidated fuzzy & parametric search)
4. get_attendance (consolidated attendance search)
"""
import asyncio
import json
import os
import sys

# Setup imports
_backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, _backend_dir)

from MCP.mcp_server import mcp

RESULTS = {"passed": 0, "failed": 0}

async def call(tool_name: str, args: dict) -> dict:
    print(f"Calling tool '{tool_name}' with args {args}...")
    contents = await mcp.call_tool(tool_name, args)
    if not contents:
        return {"success": False, "error": "Empty response"}
    return json.loads(contents[0].text)

def check(label: str, result: dict, success_expected: bool = True):
    ok = result.get("success", True) is not False
    if ok == success_expected:
        print(f"  [OK] {label} - PASSED")
        RESULTS["passed"] += 1
        return True
    else:
        print(f"  [FAIL] {label} - FAILED")
        print(f"     Result: {json.dumps(result, indent=2)}")
        RESULTS["failed"] += 1
        return False

async def main():
    print("=" * 60)
    print("  Testing Refactored MCP Tools  ")
    print("=" * 60)

    # 1. Test search_employees (with various consolidated parameters)
    print("\n--- 1. Testing search_employees ---")
    res1 = await call("search_employees", {"query": "a", "limit": 5})
    check("Search employees with query='a'", res1)

    res2 = await call("search_employees", {"position": "Software Engineer"})
    check("Search employees by position='Software Engineer'", res2)

    res3 = await call("search_employees", {"status": "tetap"})
    check("Search employees by status='tetap'", res3)

    res4 = await call("search_employees", {"min_salary": 5000000})
    check("Search employees by min_salary=5000000", res4)

    # Get a valid employee ID for subsequent tests
    emp_id = None
    if res1.get("success") and res1.get("data"):
        emp_id = res1["data"][0].get("ID") or res1["data"][0].get("id")
        print(f"Found sample employee ID: {emp_id}")

    # 2. Test get_attendance (consolidated attendance tools)
    print("\n--- 2. Testing get_attendance ---")
    res_att1 = await call("get_attendance", {"limit": 5})
    check("Get attendance list", res_att1)

    res_att2 = await call("get_attendance", {"status": "late"})
    check("Get attendance by status='late'", res_att2)

    res_att3 = await call("get_attendance", {"work_location": "Office"})
    check("Get attendance by work_location='Office'", res_att3)

    # 3. Test extract_data_from_file
    print("\n--- 3. Testing extract_data_from_file ---")
    # Let's create a temporary text file to extract from
    temp_file = os.path.join(_backend_dir, "scratch", "test_doc.txt")
    os.makedirs(os.path.dirname(temp_file), exist_ok=True)
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write("Nama: John Doe\nJabatan: Senior Dev\nNo HP: +628123456789\nEmail: john.doe@example.com\nKTP: 1234567890123456")
    
    res_ext = await call("extract_data_from_file", {
        "file_path": temp_file,
        "instruction": "Ekstrak nama, no HP, email, dan no KTP dari dokumen tersebut"
    })
    check("Extract data from text file using AI", res_ext)
    
    # Cleanup temp file
    if os.path.exists(temp_file):
        os.remove(temp_file)

    # 4. Test update_employee_by_id (dual-table updates)
    print("\n--- 4. Testing update_employee_by_id (dual-table) ---")
    if emp_id:
        # We will update a personal field (email) and a CV field (skills)
        # Let's first retrieve current employee CV so we can restore it later if needed
        restore_data = {}
        emp_cv = await call("get_employee_cv", {"emp_id": int(emp_id)})
        emp_personal = await call("get_employee_by_id", {"emp_id": int(emp_id)})
        
        orig_email = emp_personal.get("data", {}).get("EMAIL") or emp_personal.get("data", {}).get("email") or "test@example.com"
        orig_skills = emp_cv.get("qualifications", {}).get("skills") or "Python"
        
        print(f"Original email: {orig_email}, original skills: {orig_skills}")
        
        # Perform update
        updates = {
            "email": "temp_refactor_test@example.com",
            "skills": "Python, Go, Rust, MCP-Refactored"
        }
        res_upd = await call("update_employee_by_id", {
            "emp_id": int(emp_id),
            "updates": updates
        })
        ok_upd = check("Update employee with personal and CV fields simultaneously", res_upd)
        
        # Verify update worked
        if ok_upd:
            ver_cv = await call("get_employee_cv", {"emp_id": int(emp_id)})
            ver_personal = await call("get_employee_by_id", {"emp_id": int(emp_id)})
            
            new_email = ver_personal.get("data", {}).get("EMAIL") or ver_personal.get("data", {}).get("email")
            new_skills = ver_cv.get("qualifications", {}).get("skills")
            
            print(f"Updated email in employees table: {new_email}")
            print(f"Updated skills in employee_cv table: {new_skills}")
            
            if new_email == "temp_refactor_test@example.com" and "MCP-Refactored" in str(new_skills):
                print("  [OK] Verification of dual-table update - SUCCESS")
                RESULTS["passed"] += 1
            else:
                print("  [FAIL] Verification of dual-table update - FAILED")
                RESULTS["failed"] += 1
            
            # Restore original data
            await call("update_employee_by_id", {
                "emp_id": int(emp_id),
                "updates": {
                    "email": orig_email,
                    "skills": orig_skills
                }
            })
            print("Original employee data restored.")
    else:
        print("Skipped update_employee_by_id dual-table test because no valid employee ID was found.")

    print("\n" + "=" * 60)
    print(f"Test Summary: {RESULTS['passed']} passed | {RESULTS['failed']} failed")
    print("=" * 60)
    
    if RESULTS["failed"] > 0:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
