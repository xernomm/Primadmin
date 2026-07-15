"""
Test script for verifying update_employee_by_id robustness improvements.
Tests:
1. Stringified updates: "{'phone_number': '08122334455'}"
2. Nested updates: {"success": True, "data": {"skills": "Python, MCP-Robust-Testing"}}
3. Key variations: "phone_number" -> "phone", "keahlian" -> "skills"
4. Verification of cross-mappings: "position" -> "current_position"
"""
import asyncio
import json
import os
import sys

_backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, _backend_dir)

from MCP.mcp_server import mcp

async def call(tool_name: str, args: dict) -> dict:
    print(f"Calling tool '{tool_name}' with args {args}...")
    contents = await mcp.call_tool(tool_name, args)
    if not contents:
        return {"success": False, "error": "Empty response"}
    return json.loads(contents[0].text)

async def main():
    print("=" * 60)
    print("  Testing update_employee_by_id Robustness Improvements  ")
    print("=" * 60)

    # 1. Search for a valid employee to test
    search_res = await call("search_employees", {"query": "a", "limit": 1})
    if not search_res.get("success") or not search_res.get("data"):
        print("Error: No employee found to test.")
        return
        
    emp = search_res["data"][0]
    emp_id = int(emp.get("ID") or emp.get("id"))
    print(f"Testing with Employee ID: {emp_id} ({emp.get('NAME')})")

    # Fetch original state
    orig_personal = await call("get_employee_by_id", {"emp_id": emp_id})
    orig_cv = await call("get_employee_cv", {"emp_id": emp_id})
    
    orig_phone = orig_personal.get("data", {}).get("PHONE") or orig_personal.get("data", {}).get("phone")
    orig_skills = orig_cv.get("qualifications", {}).get("skills")
    orig_position = orig_personal.get("data", {}).get("POSITION") or orig_personal.get("data", {}).get("position")
    
    print(f"Original Phone: {orig_phone}")
    print(f"Original Skills: {orig_skills}")
    print(f"Original Position: {orig_position}")

    passed_tests = 0
    failed_tests = 0

    try:
        # --- TEST 1: Stringified updates dict ---
        print("\n--- Test 1: Stringified updates dict ---")
        str_updates = "{'phone_number': '08999999999'}"
        res1 = await call("update_employee_by_id", {"emp_id": emp_id, "updates": str_updates})
        print(f"Result: {res1.get('success')}, updated_fields: {res1.get('updated_fields')}")
        
        # Verify
        verify1 = await call("get_employee_by_id", {"emp_id": emp_id})
        new_phone = verify1.get("data", {}).get("PHONE") or verify1.get("data", {}).get("phone")
        if new_phone == "08999999999":
            print("[PASS] Test 1: Stringified updates successfully parsed and updated!")
            passed_tests += 1
        else:
            print(f"[FAIL] Test 1: Expected phone '08999999999', got '{new_phone}'")
            failed_tests += 1

        # --- TEST 2: Nested data dictionary & key mappings & cross-mappings ---
        print("\n--- Test 2: Nested data dict from extraction result ---")
        nested_updates = {
            "success": True,
            "data": {
                "phone_no": "08111111111",
                "keahlian": "Python, Go, MCP-Robust-Testing",
                "position": "Lead AI Architect",
                "education": {
                    "univ": "Universitas Indonesia",
                    "major": "Computer Science",
                    "year": 2022
                }
            },
            "file_path": "dummy_cv_path.pdf"
        }
        res2 = await call("update_employee_by_id", {"emp_id": emp_id, "updates": nested_updates})
        print(f"Result: {res2.get('success')}, updated_fields: {res2.get('updated_fields')}")
        
        # Verify
        verify2_p = await call("get_employee_by_id", {"emp_id": emp_id})
        verify2_c = await call("get_employee_cv", {"emp_id": emp_id})
        
        new_phone2 = verify2_p.get("data", {}).get("PHONE") or verify2_p.get("data", {}).get("phone")
        new_skills2 = verify2_c.get("qualifications", {}).get("skills")
        new_pos2 = verify2_p.get("data", {}).get("POSITION") or verify2_p.get("data", {}).get("position")
        new_curr_pos2 = verify2_c.get("current_info", {}).get("position")
        new_univ = verify2_c.get("education", {}).get("institution")
        new_major = verify2_c.get("education", {}).get("major")
        new_year = verify2_c.get("education", {}).get("graduation_year")
        
        success2 = True
        if new_phone2 != "08111111111":
            print(f"  [FAIL] Phone mapping failed. Expected '08111111111', got '{new_phone2}'")
            success2 = False
        if "MCP-Robust-Testing" not in str(new_skills2):
            print(f"  [FAIL] Skills mapping failed. Expected 'MCP-Robust-Testing' in '{new_skills2}'")
            success2 = False
        if new_pos2 != "Lead AI Architect" or new_curr_pos2 != "Lead AI Architect":
            print(f"  [FAIL] Cross-mapping/position sync failed. Expected 'Lead AI Architect', got positions: '{new_pos2}' / '{new_curr_pos2}'")
            success2 = False
        if new_univ != "Universitas Indonesia" or new_major != "Computer Science" or int(new_year or 0) != 2022:
            print(f"  [FAIL] Nested education mapping failed. Got: {new_univ}, {new_major}, {new_year}")
            success2 = False
            
        if success2:
            print("[PASS] Test 2: Nested extraction result successfully unwrapped, mapped and synchronized!")
            passed_tests += 1
        else:
            failed_tests += 1

    finally:
        # Restore original state
        print("\nRestoring original employee state...")
        restore_res = await call("update_employee_by_id", {
            "emp_id": emp_id,
            "updates": {
                "phone": orig_phone,
                "skills": orig_skills,
                "position": orig_position
            }
        })
        print(f"Restore result: {restore_res.get('success')}")

    print("\n" + "=" * 60)
    print(f"Robustness Test Summary: {passed_tests} passed | {failed_tests} failed")
    print("=" * 60)
    
    if failed_tests > 0:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
