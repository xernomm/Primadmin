import os
import sys
import json
import traceback

# Add backend to path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from MCP.tools import utility_tools
from MCP.tools import attendance_tools
from MCP.tools import employee_tools
from MCP.tools import leave_tools

def print_result(tool_name, result):
    print(f"\n{'='*60}")
    print(f"TESTING TOOL: {tool_name}")
    print(f"{'='*60}")
    if isinstance(result, dict):
        print(json.dumps(result, indent=2, default=str))
    else:
        print(result)
    
    if isinstance(result, dict) and result.get("success") is False:
        print("❌ FAILED")
    else:
        print("✅ SUCCESS")

def run_tests():
    print("STARTING TOOL TESTS...")
    
    # ==========================================
    # 1. Utility Tools
    # ==========================================
    try:
        res = utility_tools.get_current_time()
        print_result("get_current_time", res)
    except Exception as e:
        print(f"❌ Error running get_current_time: {e}")

    # ==========================================
    # 2. Employee Read Tools
    # ==========================================
    valid_emp_id = None
    
    try:
        # Get all employees
        res = employee_tools.get_all_employees(limit=5)
        print_result("get_all_employees", res)
        if res.get("success") and res.get("data"):
            valid_emp_id = res["data"][0]["ID"]
    except Exception as e:
        print(f"❌ Error running get_all_employees: {e}")

    try:
        # Search employees
        res = employee_tools.search_employees(query="a", limit=5) # 'a' is common
        print_result("search_employees", res)
    except Exception as e:
        print(f"❌ Error running search_employees: {e}")

    if valid_emp_id:
        try:
            # Get employee by ID
            res = employee_tools.get_employee_by_id(valid_emp_id)
            print_result(f"get_employee_by_id (ID={valid_emp_id})", res)
        except Exception as e:
            print(f"❌ Error running get_employee_by_id: {e}")

    try:
        # Filter filters
        print_result("filter_employees_salary_above", employee_tools.filter_employees_salary_above(10000000, 5))
    except Exception as e:
        print(f"❌ Error running filters: {e}")

    # ==========================================
    # 3. Attendance Tools
    # ==========================================
    try:
        print_result("get_today_attendance", attendance_tools.get_today_attendance(limit=5))
        print_result("get_today_late_employees", attendance_tools.get_today_late_employees(limit=5))
        print_result("get_today_remote_employees", attendance_tools.get_today_remote_employees(limit=5))
        print_result("get_today_onsite_employees", attendance_tools.get_today_onsite_employees(limit=5))
    except Exception as e:
        print(f"❌ Error running attendance tools: {e}")

    # ==========================================
    # 4. Leave Tools
    # ==========================================
    try:
        print_result("get_all_employee_leaves", leave_tools.get_all_employee_leaves(limit=5))
        if valid_emp_id:
            print_result(f"get_employee_leave_by_id (ID={valid_emp_id})", leave_tools.get_employee_leave_by_id(valid_emp_id))
    except Exception as e:
        print(f"❌ Error running leave tools: {e}")

    # ==========================================
    # 5. Write Tests (Create -> Update -> Delete)
    # ==========================================
    print("\n⚠️  STARTING WRITE TESTS (CRUD SEQUENCE) ⚠️")
    created_id = None
    
    try:
        # Create
        print("Creating dummy employee...")
        create_res = employee_tools.create_employee(name="TEST_AUTO_BOT")
        print_result("create_employee", create_res)
        
        if create_res.get("success"):
            created_id = create_res.get("employee_id") or create_res.get("data", {}).get("id")
            
            if created_id:
                # Update
                print(f"Updating dummy employee ID {created_id}...")
                update_res = employee_tools.update_employee_by_id(created_id, {"position": "Tester", "status": "contract"})
                print_result("update_employee_by_id", update_res)
                
                # Delete
                print(f"Deleting dummy employee ID {created_id}...")
                delete_res = employee_tools.delete_employee_by_id(created_id)
                print_result("delete_employee_by_id", delete_res)
            else:
                print("❌ Could not extract created ID, skipping update/delete.")
    except Exception as e:
        print(f"❌ Error running write tests: {e}")
        # Attempt cleanup if ID exists but delete failed
        if created_id:
             print(f"Attempting emergency cleanup for ID {created_id}...")
             try:
                 employee_tools.delete_employee_by_id(created_id)
             except:
                 pass

if __name__ == "__main__":
    run_tests()
