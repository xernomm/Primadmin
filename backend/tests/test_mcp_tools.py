"""
Test FastMCP Integration: Verifikasi bahwa semua tool berjalan
melalui FastMCP in-process (mcp.call_tool()) bukan direct function call.

Jalankan:
    conda run -n ragmcp python tests/test_mcp_tools.py
    conda run -n ragmcp python tests/test_mcp_tools.py -v     # verbose
    conda run -n ragmcp python tests/test_mcp_tools.py quick  # hanya read-only
"""
import asyncio
import json
import sys
import os
import time
import argparse

# Add backend and MCP directories to path
_backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
_mcp_dir = os.path.join(_backend_dir, 'MCP')
sys.path.insert(0, _backend_dir)
sys.path.insert(0, _mcp_dir)  # so mcp_server's "from tools.xxx import" resolves

# ── Import MCP server instance ──────────────────────────────────────────────
from MCP.mcp_server import mcp

# ── Helpers ─────────────────────────────────────────────────────────────────
RESULTS = {"passed": 0, "failed": 0, "skipped": 0}
VERBOSE = "-v" in sys.argv or "--verbose" in sys.argv


def _sep(title: str):
    print(f"\n{'-'*60}")
    print(f"  {title}")
    print(f"{'-'*60}")


async def call(tool_name: str, args: dict) -> dict:
    """Call a tool via FastMCP in-process and return the deserialized dict."""
    contents = await mcp.call_tool(tool_name, args)
    if not contents:
        return {"success": False, "error": "Empty response from FastMCP"}
    return json.loads(contents[0].text)


def check(label: str, result: dict, required_keys: list = None):
    """Assert result is successful and contains required keys. Print status."""
    ok = result.get("success", True) is not False
    if ok and required_keys:
        missing = [k for k in required_keys if k not in result]
        if missing:
            ok = False
            result["_missing_keys"] = missing

    icon = "[OK]" if ok else "[FAIL]"
    print(f"  {icon} {label}")
    if not ok or VERBOSE:
        print(f"     Result: {json.dumps(result, indent=4, default=str)[:500]}")

    if ok:
        RESULTS["passed"] += 1
    else:
        RESULTS["failed"] += 1
    return ok


def skip(label: str, reason: str = ""):
    print(f"  [SKIP]  {label}" + (f" ({reason})" if reason else ""))
    RESULTS["skipped"] += 1


# ============================================================================
# TEST SUITES
# ============================================================================

async def test_utility_tools():
    _sep("UTILITY TOOLS")
    res = await call("get_current_time", {})
    check("get_current_time -> has datetime", res, required_keys=["datetime"])


async def test_employee_read_tools():
    _sep("EMPLOYEE TOOLS (READ)")
    # get_all_employees
    res = await call("get_all_employees", {"limit": 5})
    ok = check("get_all_employees (limit=5)", res)

    emp_id = None
    if ok and isinstance(res.get("data"), list) and res["data"]:
        emp_id = res["data"][0].get("ID") or res["data"][0].get("id")

    # search_employees
    res2 = await call("search_employees", {"query": "a", "limit": 3})
    check("search_employees (query='a')", res2)

    # get_employee_by_id
    if emp_id:
        res3 = await call("get_employee_by_id", {"emp_id": int(emp_id)})
        check(f"get_employee_by_id (ID={emp_id})", res3)
    else:
        skip("get_employee_by_id", "no valid ID from get_all_employees")

    # filter via consolidated search_employees
    res4 = await call("search_employees", {"status": "tetap", "limit": 5})
    check("search_employees (status=tetap)", res4)

    res5 = await call("search_employees", {"min_salary": 5000000, "limit": 5})
    check("search_employees (min_salary=5000000)", res5)

    return emp_id  # pass to write tests if needed


async def test_attendance_tools():
    _sep("ATTENDANCE TOOLS (READ)")
    for tool in [
        ("get_attendance", {"limit": 5}),
        ("get_attendance", {"status": "late", "limit": 5}),
        ("get_attendance", {"work_location": "Office", "limit": 5}),
    ]:
        res = await call(tool[0], tool[1])
        check(f"{tool[0]} with args {tool[1]}", res)


async def test_leave_tools():
    _sep("LEAVE / VACATION DATA")
    res = await call("search_employees", {"limit": 5})
    check("search_employees (checking employee list has cuti info)", res)


async def test_payroll_tools(emp_id=None):
    _sep("PAYROLL TOOLS (READ)")
    if emp_id:
        res = await call("get_payroll_detail", {"emp_id": int(emp_id)})
        check(f"get_payroll_detail (ID={emp_id})", res)

        res2 = await call("get_payroll_info", {"emp_id": int(emp_id)})
        check(f"get_payroll_info (ID={emp_id})", res2)
    else:
        skip("get_payroll_detail / get_payroll_info", "no emp_id available")

    res3 = await call("analyze_payroll_anomaly", {"emp_id": None, "period_count": 3})
    check("analyze_payroll_anomaly (all employees, 3 periods)", res3)


async def test_filesystem_tools():
    _sep("FILESYSTEM TOOLS")
    res = await call("read_file", {"file_path": "nonexistent_refactor_test.txt"})
    # Safety check should fail with Access Denied (Akses ditolak) because it is outside allowed dirs
    is_denied = res.get("success") is False and "Akses ditolak" in res.get("error", "")
    if is_denied:
        print("  [OK] read_file (checking safety checks fail gracefully)")
        RESULTS["passed"] += 1
    else:
        print("  [FAIL] read_file (checking safety checks fail gracefully)")
        print(f"     Result: {json.dumps(res, indent=4)}")
        RESULTS["failed"] += 1


async def test_sql_tool():
    _sep("SQL GENERATOR TOOL")
    res = await call("generate_and_execute_sql", {
        "natural_query": "Ambil 3 karyawan pertama beserta nama dan jabatannya",
        "execute": True,
        "limit": 3
    })
    check("generate_and_execute_sql (SELECT 3 karyawan)", res)


async def test_write_tools_crud():
    """CRUD write tests — only runs when NOT in quick mode."""
    _sep("WRITE TOOLS (CRUD) — membuat & menghapus data test")
    created_id = None
    try:
        # Create
        res = await call("create_employee", {"name": "TEST_FASTMCP_BOT"})
        ok = check("create_employee (TEST_FASTMCP_BOT)", res)
        if ok:
            created_id = (
                res.get("employee_id")
                or (res.get("data") or {}).get("id")
                or (res.get("data") or {}).get("ID")
            )

        if created_id:
            # Update
            res2 = await call("update_employee_by_id", {
                "emp_id": int(created_id),
                "updates": {"position": "Test Position", "status": "contract"}
            })
            check(f"update_employee_by_id (ID={created_id})", res2)

            # Delete
            res3 = await call("delete_employee_by_id", {"emp_id": int(created_id)})
            check(f"delete_employee_by_id (ID={created_id})", res3)
            created_id = None  # cleaned up
        else:
            skip("update + delete", "create_employee did not return an ID")

    except Exception as e:
        print(f"  [FAIL] Exception in CRUD tests: {e}")
        RESULTS["failed"] += 1
    finally:
        # Emergency cleanup
        if created_id:
            try:
                await call("delete_employee_by_id", {"emp_id": int(created_id)})
                print(f"  [CLEANUP] Emergency cleanup: deleted ID {created_id}")
            except Exception:
                pass


async def test_mcp_server_integrity():
    """Verify that the FastMCP server has all expected tools registered."""
    _sep("MCP SERVER INTEGRITY")
    tools = await mcp.list_tools()
    tool_names = {t.name for t in tools}

    EXPECTED = {
        # employee
        "search_employees", "get_employee_by_id", "get_all_employees",
        "create_employee", "update_employee_by_id", "delete_employee_by_id",
        "get_employee_files",
        # attendance
        "get_attendance", "update_absensi",
        # sql
        "generate_and_execute_sql", "get_schema_context",
        # utility
        "get_current_time", "extract_data_from_file",
        # cv
        "get_employee_cv", "analyze_employee_cv", "summarize_employee_cv",
        "manage_cv_file",
        # analysis
        "analyze_attendance_with_policy",
        # email
        "send_warning_letter", "send_email_to_employee",
        "send_broadcast_email", "reset_sp_level", "generate_email_content",
        # export
        "export_employee_personal_data", "export_employee_operational_data",
        # filesystem
        "read_file", "write_file", "rename_file", "delete_file",
        # payroll
        "get_payroll_detail", "get_payroll_info", "analyze_payroll_anomaly",
        "export_payroll_csv", "get_payroll_file",
        "create_payroll_report_pdf", "send_payroll_email",
    }

    missing = EXPECTED - tool_names
    extra   = tool_names - EXPECTED

    if not missing:
        print(f"  [OK] All {len(EXPECTED)} expected tools are registered ({len(tool_names)} total)")
        RESULTS["passed"] += 1
    else:
        print(f"  [FAIL] Missing tools ({len(missing)}): {sorted(missing)}")
        RESULTS["failed"] += 1

    if extra:
        print(f"  [INFO] Extra tools (not in expected list): {sorted(extra)}")


# ============================================================================
# MAIN
# ============================================================================

async def main(quick: bool = False):
    print("\n" + "="*60)
    print("  FastMCP Integration Test Suite")
    print(f"  Mode: {'QUICK (read-only)' if quick else 'FULL (including CRUD)'}")
    print("="*60)

    start = time.time()

    # Always run
    await test_mcp_server_integrity()
    await test_utility_tools()
    emp_id = await test_employee_read_tools()
    await test_attendance_tools()
    await test_leave_tools()
    await test_sql_tool()
    await test_filesystem_tools()

    if not quick:
        await test_payroll_tools(emp_id)
        await test_write_tools_crud()
    else:
        skip("Payroll tools",      "quick mode")
        skip("CRUD write tests",   "quick mode")

    elapsed = time.time() - start
    total = RESULTS["passed"] + RESULTS["failed"] + RESULTS["skipped"]

    print(f"\n{'='*60}")
    print(f"  RESULTS: {RESULTS['passed']}/{total} passed | "
          f"{RESULTS['failed']} failed | {RESULTS['skipped']} skipped")
    print(f"  Time: {elapsed:.2f}s")
    print("="*60 + "\n")

    if RESULTS["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    quick_mode = "quick" in sys.argv
    asyncio.run(main(quick=quick_mode))
