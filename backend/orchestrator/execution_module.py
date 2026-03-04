"""
Execution Module — Stage 3: Tool Execution.
Extracted from HRAgent._stage_3_execute_tools and all related methods.

Handles:
- Single tool execution via MCP SSE client
- Planned tool execution with dependency resolution
- SQL fallback for failed DB tools
- Ollama native function calling fallback
"""
import json
import re
import traceback
import asyncio
import time
import os
from typing import Dict, List, Any, Optional, Callable

import ollama

from agent.core import TOOL_MODEL, MCP_SERVER_URL, MAX_TOOL_ITERATIONS
from agent.prompt_templates import get_tool_definitions
from orchestrator._utils import log_debug


# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS (extracted from HRAgent methods)
# ══════════════════════════════════════════════════════════════════════════════

def normalize_tool_arguments(tool_name: str, arguments: Dict) -> Dict:
    """Fix common LLM mistakes in tool argument structure before sending to MCP."""
    if tool_name == "update_employee_by_id":
        if "emp_id" in arguments and "updates" not in arguments:
            emp_id = arguments.get("emp_id")
            updates = {k: v for k, v in arguments.items() if k != "emp_id"}
            if updates:
                log_debug("[ARG NORMALIZE] update_employee_by_id: wrapping flat args into 'updates'", str(updates))
                return {"emp_id": emp_id, "updates": updates}
    return arguments


def normalize_result_keys(data: Any) -> Any:
    """Normalize all dictionary keys to uppercase for consistent placeholder resolution."""
    if isinstance(data, dict):
        return {k.upper(): normalize_result_keys(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [normalize_result_keys(item) for item in data]
    return data


def sanitize_arguments(args: Any) -> Any:
    """Recursively sanitize arguments by removing unresolved placeholders."""
    if isinstance(args, str):
        if re.match(r'^{{step_\d+\.result\..*}}$', args):
            return None
        return re.sub(r'{{step_\d+\.result\.[^}]+}}', '', args).strip()
    elif isinstance(args, dict):
        return {k: sanitize_arguments(v) for k, v in args.items()}
    elif isinstance(args, list):
        return [sanitize_arguments(item) for item in args]
    return args


def resolve_nested_path(data: Any, path_parts: List[str]) -> Any:
    """
    Resolve a nested dot-path from a tool result.
    Supports arbitrary depth with case-insensitive matching and deep-search fallback.
    """
    def _walk(node, parts):
        current = node
        for part in parts:
            if current is None:
                return None
            if isinstance(current, dict):
                matched = None
                for k, v in current.items():
                    if k.lower() == part.lower():
                        matched = v
                        break
                current = matched
            elif isinstance(current, list):
                if len(current) > 0:
                    current = current[0]
                    if isinstance(current, dict):
                        matched = None
                        for k, v in current.items():
                            if k.lower() == part.lower():
                                matched = v
                                break
                        current = matched
                    else:
                        current = None
                else:
                    return None
            else:
                return None
        return current

    def _deep_search(node, target_key):
        if isinstance(node, dict):
            for k, v in node.items():
                if k.lower() == target_key.lower() and not isinstance(v, (dict, list)):
                    return v
            for v in node.values():
                result = _deep_search(v, target_key)
                if result is not None:
                    return result
        elif isinstance(node, list):
            for item in node:
                result = _deep_search(item, target_key)
                if result is not None:
                    return result
        return None

    direct = _walk(data, path_parts)
    if direct is not None:
        return direct
    if path_parts:
        return _deep_search(data, path_parts[-1])
    return None


# ══════════════════════════════════════════════════════════════════════════════
# MCP TOOL CALL
# ══════════════════════════════════════════════════════════════════════════════

async def call_mcp_tool(tool_name: str, arguments: Dict) -> Dict[str, Any]:
    """Execute a tool via MCP SSE client. Extracted from HRAgent._call_mcp_tool."""
    arguments = normalize_tool_arguments(tool_name, arguments)
    try:
        from mcp import ClientSession
        from mcp.client.sse import sse_client

        async with sse_client(url=MCP_SERVER_URL, timeout=600.0) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)

        if not result.content:
            return {"success": False, "error": f"Tool '{tool_name}' returned empty response"}
        try:
            return json.loads(result.content[0].text)
        except Exception:
            raw = result.content[0].text if hasattr(result.content[0], 'text') else str(result.content[0])
            return {"success": True, "message": raw}

    except Exception as e:
        err_msg = str(e)
        if hasattr(e, "exceptions") and isinstance(e.exceptions, (list, tuple)):
            sub_errors = [str(se) for se in e.exceptions]
            err_msg = f"{err_msg} (Sub-errors: {', '.join(sub_errors)})"
        log_debug(f"[MCP SSE ERROR] Tool '{tool_name}'", f"{err_msg}\n{traceback.format_exc()}")
        return {"success": False, "error": f"MCP SSE call failed: {err_msg}"}


# ══════════════════════════════════════════════════════════════════════════════
# SINGLE TOOL EXECUTION WITH RETRY
# ══════════════════════════════════════════════════════════════════════════════

async def execute_single_tool(tool_name: str, arguments: Dict, ctx=None, max_retries: int = 3) -> Dict[str, Any]:
    """Execute a single tool via MCP SSE, with retry logic for recoverable errors."""
    last_error = None
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                if ctx:
                    ctx.update_status(f"Retry {attempt}/{max_retries-1}: {tool_name}...")
                print(f"[RETRY] Attempt {attempt + 1}/{max_retries} for tool '{tool_name}'")

            log_debug(f"DEBUG: Executing Tool '{tool_name}' via FastMCP (Attempt {attempt + 1})", arguments)
            result = await call_mcp_tool(tool_name, arguments)
            log_debug(f"DEBUG: Tool Result '{tool_name}'", result)

            if isinstance(result, dict) and result.get("success", True):
                return result
            elif isinstance(result, dict) and not result.get("success"):
                if tool_name == "generate_and_execute_sql" and attempt < max_retries - 1:
                    last_error = result.get("error", "Unknown error")
                    print(f"[RETRY] SQL tool failed: {last_error}, retrying...")
                    continue
                return result
            else:
                return result

        except Exception as e:
            last_error = str(e)
            err_msg = {"success": False, "error": last_error, "trace": traceback.format_exc()}
            log_debug(f"DEBUG: Tool Error '{tool_name}' (Attempt {attempt + 1})", err_msg)

            if attempt < max_retries - 1:
                recoverable = any(kw in last_error.lower() for kw in ['timeout', 'connection', 'serialize', 'ora-'])
                if recoverable:
                    time.sleep(0.5)
                    continue
            return err_msg

    return {"success": False, "error": f"Max retries ({max_retries}) exceeded. Last error: {last_error}"}


# ══════════════════════════════════════════════════════════════════════════════
# SQL FALLBACK
# ══════════════════════════════════════════════════════════════════════════════

async def retry_with_sql_fallback(tool_name, original_args, error_msg, state, max_retries=2):
    """Retry a failed tool by converting to SQL query. Extracted from HRAgent._retry_with_sql_fallback."""
    action_map = {
        'update_employee_by_id': 'UPDATE data karyawan',
        'create_employee': 'INSERT karyawan baru',
        'delete_employee_by_id': 'DELETE karyawan',
        'update_absensi': 'UPDATE data absensi',
        'update_leaves': 'UPDATE data cuti',
        'filter_employees_by_status': 'SELECT karyawan berdasarkan status',
        'filter_employees_by_position': 'SELECT karyawan berdasarkan posisi',
        'search_employees': 'SELECT cari data karyawan',
        'get_employee_by_id': 'SELECT detail lengkap karyawan spesifik',
        'get_all_employees': 'SELECT semua daftar karyawan',
        'get_today_attendance': 'SELECT data log absensi HARI INI',
        'get_today_late_employees': 'SELECT karyawan yang TERLAMBAT HARI INI',
        'get_today_remote_employees': 'SELECT karyawan yang bekerja REMOTE HARI INI',
        'get_today_onsite_employees': 'SELECT karyawan yang bekerja di KANTOR HARI INI',
        'get_employee_leave_by_id': 'SELECT data riwayat cuti karyawan spesifik',
        'get_all_employee_leaves': 'SELECT semua data cuti karyawan',
        'get_employee_cv': 'SELECT semua data riwayat profil pendidikan pengalaman skill CV karyawan',
    }
    action = action_map.get(tool_name, f"Execute {tool_name}")

    args_desc = []
    emp_id = original_args.get("emp_id") or original_args.get("employee_id")
    updates = original_args.get("updates") or {}

    if emp_id and isinstance(emp_id, str) and emp_id.startswith("{{"):
        emp_id = None

    employee_identifier = None
    if emp_id and isinstance(emp_id, (int, float)):
        employee_identifier = f"ID = {int(emp_id)}"
    else:
        if state.entities:
            for key in ['employee_name', 'name', 'nama', 'karyawan']:
                if key in state.entities:
                    employee_identifier = f"name LIKE '%{state.entities[key]}%'"
                    break
        if not employee_identifier and state.original_query:
            patterns = [
                r'karyawan\s+(\w+\s+\w+)', r'nama\s+(\w+\s+\w+)',
                r'kredensial\s+(\w+\s+\w+)', r'data\s+(\w+\s+\w+)',
            ]
            for pattern in patterns:
                match = re.search(pattern, state.original_query.lower())
                if match:
                    name = ' '.join(w.capitalize() for w in match.group(1).strip().split())
                    employee_identifier = f"name LIKE '%{name}%'"
                    break

    if employee_identifier:
        args_desc.append(f"WHERE {employee_identifier}")
    if isinstance(updates, dict) and updates:
        set_parts = [f"{k}='{v}'" for k, v in updates.items() if v is not None]
        if set_parts:
            args_desc.append(f"SET {', '.join(set_parts)}")

    raw_query = f"{action} {' '.join(args_desc)}"
    natural_query = re.sub(r'{{step_\d+\.result\.[^}]+}}', 'Unknown', raw_query)

    if not employee_identifier:
        natural_query = f"Berdasarkan permintaan: {state.original_query}. Gunakan subquery untuk menemukan karyawan berdasarkan nama lama jika diperlukan."
    elif state.original_query:
        natural_query += f". Konteks: {state.original_query}"

    log_debug("DEBUG: SQL Fallback Query", natural_query)

    for attempt in range(max_retries):
        try:
            result = await call_mcp_tool(
                "generate_and_execute_sql",
                {"natural_query": natural_query, "execute": True, "limit": 100},
            )
            if result.get("success"):
                print(f"[SQL FALLBACK] Success on attempt {attempt + 1}")
                return result
            else:
                print(f"[SQL FALLBACK] Attempt {attempt + 1} failed: {result.get('error')}")
                natural_query = f"Retry: {state.original_query}. Error sebelumnya: {result.get('error')}. Gunakan nama karyawan dalam WHERE clause untuk identifikasi."
        except Exception as e:
            print(f"[SQL FALLBACK ERROR] {e}")

    return {"success": False, "error": f"SQL fallback failed after {max_retries} attempts", "original_error": error_msg}


# ══════════════════════════════════════════════════════════════════════════════
# PLANNED TOOL EXECUTION (dependency resolution + SQL fallback)
# ══════════════════════════════════════════════════════════════════════════════

DB_TOOLS = [
    'update_employee_by_id', 'create_employee', 'delete_employee_by_id',
    'update_absensi', 'update_leaves', 'filter_employees_by_status',
    'filter_employees_by_position', 'filter_employees_salary_above',
    'filter_employees_salary_below', 'search_employees', 'get_employee_by_id',
    'get_all_employees', 'get_today_attendance', 'get_today_late_employees',
    'get_today_remote_employees', 'get_today_onsite_employees',
    'get_employee_leave_by_id', 'get_all_employee_leaves', 'get_employee_cv'
]

SKIP_FALLBACK_PHRASES = [
    "harus berupa dict", "tidak ada kolom valid",
    "NoneType", "'NoneType' object", "tidak ada kolom",
]


async def execute_planned_tools(state, ctx):
    """Execute tools based on the plan from Stage 2. Extracted from HRAgent._execute_planned_tools."""
    results_by_step = {}

    for step in state.tool_plan:
        step_num = step.get("step", len(state.tool_results) + 1)
        tool_name = step.get("name") or step.get("tool")
        arguments = (step.get("args") or step.get("arguments") or {}).copy()
        depends_on = step.get("depends_on")
        has_unresolved_dependency = False
        dependency_failed_empty = False

        # ── Resolve dependencies ──────────────────────────────────────────
        if depends_on and depends_on in results_by_step:
            prev_result = results_by_step[depends_on]
            normalized_result = normalize_result_keys(prev_result)

            if isinstance(normalized_result, dict) and "DATA" in normalized_result:
                prev_data = normalized_result["DATA"]
                if isinstance(prev_data, list) and len(prev_data) == 0:
                    dependency_failed_empty = True
                    print(f"[DEPENDENCY] Step {depends_on} returned empty data - will use SQL fallback")

            for key, value in list(arguments.items()):
                if isinstance(value, str) and "{{step_" in value:
                    has_unresolved_dependency = _resolve_placeholder(
                        key, value, arguments, results_by_step, depends_on, state
                    )
                elif isinstance(value, dict):
                    for sub_key, sub_val in list(value.items()):
                        if isinstance(sub_val, str) and "{{step_" in sub_val:
                            if sub_key.lower() in ['salary', 'basic_salary'] and state.entities:
                                multiplier = state.entities.get('salary_multiplier')
                                if multiplier and depends_on in results_by_step:
                                    dep_result = normalize_result_keys(results_by_step[depends_on])
                                    if "DATA" in dep_result and isinstance(dep_result["DATA"], list) and len(dep_result["DATA"]) > 0:
                                        base_salary = dep_result["DATA"][0].get("BASIC_SALARY")
                                        if base_salary:
                                            value[sub_key] = int(base_salary * float(multiplier))
                                            print(f"[PLACEHOLDER] Calculated {sub_key}={value[sub_key]} using multiplier {multiplier}")
                                            continue
                            has_unresolved_dependency = True
                            print(f"[PLACEHOLDER] Unresolved nested placeholder: {sub_val}")
                elif isinstance(value, str) and "{{user_provided" in value:
                    if key == "updates" and state.entities:
                        arguments[key] = {
                            k: v for k, v in state.entities.items()
                            if k.upper() in ['NAME', 'EMAIL', 'PHONE', 'POSITION', 'DEPARTMENT', 'STATUS', 'ADDRESS', 'BASIC_SALARY']
                        }
                    else:
                        arguments[key] = None

        # ── SQL fallback guard ────────────────────────────────────────────
        emp_id_val = arguments.get("emp_id")
        emp_id_still_placeholder = isinstance(emp_id_val, str) and "{{" in emp_id_val

        should_sql_fallback = tool_name in DB_TOOLS and (
            dependency_failed_empty or emp_id_still_placeholder
        )

        if should_sql_fallback:
            reason = "empty data from dependency" if dependency_failed_empty else f"emp_id unresolved: {emp_id_val}"
            ctx.update_status("Dependensi tidak terpenuhi, langsung ke SQL fallback...")
            ctx.emit_sub_status({"type": "tool_start", "tool": f"{tool_name} (SQL fallback)", "step": step_num})
            print(f"[SQL FALLBACK] Skipping {tool_name} due to: {reason}")
            result = await retry_with_sql_fallback(
                tool_name=tool_name, original_args=arguments,
                error_msg="Unresolved dependency from previous step (empty search result)",
                state=state,
            )
            if result.get("success"):
                result["fallback_used"] = "generate_and_execute_sql"
            else:
                result = {"success": False, "error": "Could not resolve employee ID and SQL fallback failed"}
        else:
            ctx.update_status(f"Menjalankan {tool_name}...")
            ctx.emit_sub_status({"type": "tool_start", "tool": tool_name, "step": step_num})
            sanitized_args = sanitize_arguments(arguments)
            result = await execute_single_tool(tool_name, sanitized_args, ctx)

            if isinstance(result, dict) and not result.get("success") and tool_name in DB_TOOLS:
                error_msg = result.get("error", "")
                is_logic_error = any(p.lower() in error_msg.lower() for p in SKIP_FALLBACK_PHRASES)
                if is_logic_error:
                    print(f"[SQL FALLBACK] Skipping fallback for '{tool_name}' — logic/data error: {error_msg}")
                else:
                    ctx.update_status("Tool gagal, mencoba SQL fallback...")
                    print(f"[SQL FALLBACK] Tool '{tool_name}' failed. Attempting SQL fallback...")
                    fallback_result = await retry_with_sql_fallback(
                        tool_name=tool_name, original_args=arguments,
                        error_msg=error_msg, state=state,
                    )
                    if fallback_result.get("success"):
                        result = fallback_result
                        result["fallback_used"] = "generate_and_execute_sql"

        results_by_step[step_num] = result
        tool_success = isinstance(result, dict) and result.get("success", False)
        ctx.emit_sub_status({"type": "tool_done", "tool": tool_name, "step": step_num, "success": tool_success})
        state.tool_results.append({
            "step": step_num, "name": tool_name, "tool": tool_name,
            "args": arguments, "arguments": arguments, "result": result,
        })
        state.total_tool_calls += 1

    state.stages_completed.append("execution_planned")

    if state.tool_results:
        tools_executed = [f"- {r['tool']}: {'Berhasil' if r['result'].get('success') else 'Error'}" for r in state.tool_results]
        stage_content = f"**{len(state.tool_results)} tools dieksekusi:**\n" + "\n".join(tools_executed)
    else:
        stage_content = "Tidak ada tools yang dieksekusi."
    ctx.emit_stage(3, "Eksekusi Tools", stage_content, "complete")

    return state


def _resolve_placeholder(key, value, arguments, results_by_step, depends_on, state):
    """Resolve a single {{step_N.result.field}} placeholder. Returns True if unresolved."""
    # Simple placeholder
    simple_match = re.match(r'{{step_(\d+)\.result\.(\w+)}}$', value)
    if simple_match:
        dep_step = int(simple_match.group(1))
        dep_field = simple_match.group(2).upper()
        if dep_step in results_by_step:
            dep_result = normalize_result_keys(results_by_step[dep_step])
            resolved_value = None
            if isinstance(dep_result, dict):
                if "DATA" in dep_result:
                    data = dep_result["DATA"]
                    if isinstance(data, list) and len(data) > 0:
                        resolved_value = data[0].get(dep_field)
                    elif isinstance(data, dict):
                        resolved_value = data.get(dep_field)
                else:
                    resolved_value = dep_result.get(dep_field)
                    if resolved_value is None:
                        resolved_value = dep_result.get(dep_field.lower())
            if resolved_value is not None:
                arguments[key] = resolved_value
                print(f"[PLACEHOLDER] Resolved {value} -> {resolved_value}")
                return False
            else:
                raw_dep = results_by_step[dep_step]
                resolved_value = resolve_nested_path(raw_dep, [dep_field.lower()])
                if resolved_value is not None:
                    arguments[key] = resolved_value
                    print(f"[PLACEHOLDER] Resolved (fallback search) {value} -> {resolved_value}")
                    return False
                print(f"[PLACEHOLDER] Could not resolve {value} - field {dep_field} not found")
                return True
        return True

    # Math expression
    math_match = re.match(r'{{step_(\d+)\.result\.(\w+)\s*([*+\-/])\s*([\d.]+)}}', value)
    if math_match:
        dep_step = int(math_match.group(1))
        dep_field = math_match.group(2).upper()
        operator = math_match.group(3)
        operand = float(math_match.group(4))
        if dep_step in results_by_step:
            dep_result = normalize_result_keys(results_by_step[dep_step])
            base_value = None
            if isinstance(dep_result, dict) and "DATA" in dep_result:
                data = dep_result["DATA"]
                if isinstance(data, list) and len(data) > 0:
                    field_aliases = {'SALARY': ['BASIC_SALARY', 'SALARY', 'GAJI']}
                    for alias in field_aliases.get(dep_field, [dep_field]):
                        if alias in data[0]:
                            base_value = data[0][alias]
                            break
            if base_value is not None and isinstance(base_value, (int, float)):
                ops = {'*': lambda a, b: a * b, '+': lambda a, b: a + b,
                       '-': lambda a, b: a - b, '/': lambda a, b: a / b if b != 0 else 0}
                arguments[key] = ops[operator](base_value, operand)
                print(f"[PLACEHOLDER] Calculated {key}={arguments[key]} from {base_value} {operator} {operand}")
                return False
        print(f"[PLACEHOLDER] Could not resolve math expression {value}")
        return True

    # Nested path
    nested_match = re.match(r'{{step_(\d+)\.result\.([\w.]+)}}$', value)
    if nested_match:
        dep_step = int(nested_match.group(1))
        path_parts = nested_match.group(2).split('.')
        if dep_step in results_by_step:
            resolved_value = resolve_nested_path(results_by_step[dep_step], path_parts)
            if resolved_value is not None:
                arguments[key] = resolved_value
                print(f"[PLACEHOLDER] Resolved nested {value} -> {resolved_value}")
                return False
            print(f"[PLACEHOLDER] Could not resolve nested path {value}")
            return True
        print(f"[PLACEHOLDER] Step {dep_step} not in results yet")
        return True

    print(f"[PLACEHOLDER] Unrecognized placeholder format: {value}")
    return True


# ══════════════════════════════════════════════════════════════════════════════
# OLLAMA NATIVE FUNCTION CALLING FALLBACK
# ══════════════════════════════════════════════════════════════════════════════

async def execute_with_ollama_function_calling(state, ctx):
    """Execute tools using Ollama's native function calling. Extracted from HRAgent."""
    messages = ctx.prompt_builder.build(
        user_query=state.escalated_query or state.original_query,
        include_schema=True,
        include_tools=False,
    )
    tools = get_tool_definitions()
    iterations = 0

    while iterations < MAX_TOOL_ITERATIONS:
        iterations += 1
        try:
            response = await asyncio.to_thread(
                ollama.chat, model=TOOL_MODEL,
                messages=messages, tools=tools,
                options={"temperature": 0.3, "num_predict": 100000},
            )
            message = response.get("message", {})
            tool_calls = message.get("tool_calls", [])

            if not tool_calls:
                state.final_response = message.get("content", "")
                log_debug("DEBUG: Stage 3 (Ollama) Final Content", state.final_response)
                break

            for tool_call in tool_calls:
                func_name = tool_call.get("function", {}).get("name")
                func_args = tool_call.get("function", {}).get("arguments", {})
                ctx.update_status(f"Menjalankan {func_name}...")
                ctx.emit_sub_status({"type": "tool_start", "tool": func_name, "step": iterations})
                result = await execute_single_tool(func_name, func_args, ctx)
                tool_success = isinstance(result, dict) and result.get("success", False)
                ctx.emit_sub_status({"type": "tool_done", "tool": func_name, "step": iterations, "success": tool_success})

                state.tool_results.append({
                    "name": func_name, "tool": func_name,
                    "args": func_args, "arguments": func_args, "result": result,
                })
                state.total_tool_calls += 1
                messages.append({"role": "assistant", "content": "", "tool_calls": [tool_call]})
                messages.append({"role": "tool", "content": json.dumps(result, ensure_ascii=False)})

        except Exception as e:
            print(f"[STAGE 3 ERROR] {e}")
            state.error = str(e)
            break

    state.stages_completed.append("execution_ollama")
    stage3_content = state.final_response if state.final_response else "Tools dieksekusi, melanjutkan ke generasi jawaban."
    ctx.emit_stage(3, "Eksekusi Tools", stage3_content, "complete")
    return state


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT — Stage 3
# ══════════════════════════════════════════════════════════════════════════════

async def run_execution(state, ctx):
    """
    Stage 3: Execute tools.
    Routes to planned execution or Ollama function calling based on whether a plan exists.
    """
    ctx.update_status("Stage 3: Menjalankan tools...")

    if state.tool_plan:
        return await execute_planned_tools(state, ctx)
    return await execute_with_ollama_function_calling(state, ctx)
