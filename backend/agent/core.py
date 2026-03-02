"""
HR Agent Core Module - 5-Stage Pipeline.

This implements the multi-stage AI agent that can:
1. Escalate and expand user prompts
2. Plan which tools to use
3. Execute tools in a loop
4. Verify results against user intent
5. Generate final response

Uses Ollama for LLM calls and MCP tools for data access.
"""
import json
import re
import traceback
import asyncio
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ollama

from context.history_manager import ConversationHistoryManager
from context.window_manager import ContextWindowManager
from chats.chat_service import get_recent_history
from .prompt_builder import PromptBuilder, get_prompt_builder
from .prompt_templates import (
    SYSTEM_PROMPT,
    get_tool_definitions,
    get_tool_descriptions
)

# Models configuration
ESCALATION_MODEL = "qwen3:latest"       # Fast model for JSON parsing/intent
PLANNING_MODEL = "qwen3:latest"          # Fast model for tool planning (JSON)
TOOL_MODEL = "qwen3:latest"              # Main model with function calling
VERIFICATION_MODEL = "qwen3:latest"      # Verification/reasoning
RESPONSE_MODEL = "llama3.2:latest"    # Reasoning model for final response
SQL_MODEL = "qwen2.5-coder:latest"       # SQL-specific model

# Maximum iterations for tool execution loop
MAX_TOOL_ITERATIONS = 50
MAX_VERIFICATION_RETRIES = 5

# MCP Server URL — runs as a separate SSE process on port 8000
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://localhost:8000/sse")

# ── Abort / Stop mechanism ────────────────────────────────────────────────────
# Maps socket session_id → True when the user pressed Stop.
# Checked between agent stages so abort takes effect without killing Ollama.
_abort_flags: Dict[str, bool] = {}

class AgentAbortedError(RuntimeError):
    """Raised when the user requests to stop the current agent run."""

def set_abort(session_id: str) -> None:
    """Signal that the agent for this socket session should stop."""
    _abort_flags[session_id] = True
    print(f"[ABORT] Abort flag set for session: {session_id}")

def clear_abort(session_id: str) -> None:
    """Clear abort flag for a session (call at the start of each new request)."""
    _abort_flags.pop(session_id, None)

def is_aborted(session_id: str) -> bool:
    return bool(_abort_flags.get(session_id))


@dataclass
class AgentState:
    """State container for agent execution."""
    original_query: str
    escalated_query: str = ""
    intent: str = ""
    entities: Dict = field(default_factory=dict)
    tool_plan: List[Dict] = field(default_factory=list)
    tool_results: List[Dict] = field(default_factory=list)
    completion_checklist: List[str] = field(default_factory=list)
    verification_passed: bool = False
    retry_count: int = 0
    final_response: str = ""
    error: Optional[str] = None
    
    # Metadata
    stages_completed: List[str] = field(default_factory=list)
    total_tool_calls: int = 0


class HRAgent:
    """
    HR Agent with 5-stage pipeline.
    
    Stage 1 (Escalation): Analyze and expand user query
    Stage 2 (Planning): Determine tools and execution order
    Stage 3 (Execution): Execute tools in a loop
    Stage 4 (Verification): Verify results satisfy user intent
    Stage 5 (Response): Generate final user-friendly response
    """
    
    def __init__(
        self,
        conversation_manager: Optional[ConversationHistoryManager] = None,
        prompt_builder: Optional[PromptBuilder] = None,
        status_callback: Optional[Callable[[str], None]] = None,
        stage_callback: Optional[Callable[[Dict], None]] = None
    ):
        """
        Initialize HR Agent.
        
        Args:
            conversation_manager: Manages conversation history
            prompt_builder: Builds prompts with context management
            status_callback: Optional callback for status updates (text only)
            stage_callback: Optional callback for stage content (dict with stage info)
        """
        self.conversation_manager = conversation_manager or ConversationHistoryManager()
        self.prompt_builder = prompt_builder or get_prompt_builder()
        self.status_callback = status_callback
        self.stage_callback = stage_callback
        self._tools_cache = None
        self._tool_functions = None  # kept for backward compat (Ollama function-calling schema)
        self._mcp_server = None       # no longer used (SSE transport)
        self._stage_logs = []  # Store stage logs for Process tab
        self._session_id: Optional[str] = None  # Socket session ID for abort checks
    
    def _update_status(self, message: str):
        """Send status update if callback is registered."""
        if self.status_callback:
            self.status_callback(message)
        print(f"[AGENT STATUS] {message}")
    
    def _emit_stage(self, stage_num: int, stage_name: str, content: str, status: str = "complete"):
        """
        Emit stage completion data for frontend processing block.
        
        Args:
            stage_num: Stage number (1-4)
            stage_name: Human-readable stage name
            content: Stage content/output
            status: 'processing', 'complete', or 'error'
        """
        stage_data = {
            "stage": stage_num,
            "name": stage_name,
            "content": content,
            "status": status
        }
        
        # Store for Process tab (upsert: replace if same stage number exists)
        existing_idx = next((i for i, s in enumerate(self._stage_logs) if s["stage"] == stage_num), None)
        if existing_idx is not None:
            self._stage_logs[existing_idx] = stage_data
        else:
            self._stage_logs.append(stage_data)
        
        # Emit to frontend if callback registered
        if self.stage_callback:
            self.stage_callback(stage_data)
        
        print(f"[STAGE {stage_num}] {stage_name}: {status}")
    
    def _emit_stage_reset(self, retry_attempt: int):
        """
        Emit a reset signal to the frontend when verification fails and
        the agent is about to retry from Stage 1.
        
        This causes the ProcessingBlock UI to clear completed stages
        and animate back to a fresh state before Stage 1 starts again.
        
        Args:
            retry_attempt: Which retry attempt this is (1-indexed)
        """
        reset_data = {
            "type": "reset",           # distinguishes this from a normal stage_complete
            "retry_attempt": retry_attempt,
            "message": f"Verifikasi gagal, mencoba ulang (percobaan {retry_attempt})..."
        }
        # Clear internal stage logs so fresh stages can accumulate
        self._stage_logs = []
        
        if self.stage_callback:
            self.stage_callback(reset_data)
        
        print(f"[STAGE RESET] Retry attempt {retry_attempt} — clearing stages for frontend")
    
    def _get_tool_definitions(self) -> List[Dict]:
        """Get cached tool definitions."""
        if self._tools_cache is None:
            self._tools_cache = get_tool_definitions()
        return self._tools_cache
    
    def _normalize_tool_arguments(self, tool_name: str, arguments: Dict) -> Dict:
        """
        Fix common LLM mistakes in tool argument structure before sending to MCP.
        E.g. update_employee_by_id requires {'emp_id': X, 'updates': {...}}
        but LLM often sends {'emp_id': X, 'field1': val1, 'field2': val2} (flat).
        """
        if tool_name == "update_employee_by_id":
            if "emp_id" in arguments and "updates" not in arguments:
                emp_id = arguments.get("emp_id")
                updates = {k: v for k, v in arguments.items() if k != "emp_id"}
                if updates:
                    self._log("[ARG NORMALIZE] update_employee_by_id: wrapping flat args into 'updates'", str(updates))
                    return {"emp_id": emp_id, "updates": updates}
        return arguments

    async def _call_mcp_tool(self, tool_name: str, arguments: Dict) -> Dict[str, Any]:
        """
        Execute a tool via MCP SSE client.
        Connects to the MCP server running on MCP_SERVER_URL (default: http://localhost:8000/sse).
        Returns the deserialized dict result from the tool.
        """
        # Normalize LLM argument mistakes before dispatching
        arguments = self._normalize_tool_arguments(tool_name, arguments)

        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client

            # Increase timeout for VERY slow tools (like CV extraction with large local LLMs)
            async with sse_client(url=MCP_SERVER_URL, timeout=600.0) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
            # result.content is list[TextContent]; each item.text is a JSON string
            if not result.content:
                return {"success": False, "error": f"Tool '{tool_name}' returned empty response"}
            try:
                return json.loads(result.content[0].text)
            except Exception:
                raw = result.content[0].text if hasattr(result.content[0], 'text') else str(result.content[0])
                return {"success": True, "message": raw}

        except Exception as e:
            err_msg = str(e)
            
            # Special handling for ExceptionGroup (TaskGroup errors)
            # Python 3.11+ uses BaseExceptionGroup for task groups
            if hasattr(e, "exceptions") and isinstance(e.exceptions, (list, tuple)):
                sub_errors = [str(se) for se in e.exceptions]
                err_msg = f"{err_msg} (Sub-errors: {', '.join(sub_errors)})"
            
            self._log(f"[MCP SSE ERROR] Tool '{tool_name}'", f"{err_msg}\n{traceback.format_exc()}")
            return {"success": False, "error": f"MCP SSE call failed: {err_msg}"}


    def _get_tool_functions(self) -> Dict[str, Callable]:
        """Get mapping of tool names to functions (used only for Ollama native function-calling schema)."""
        if self._tool_functions is not None:
            return self._tool_functions
        
        # Import all tool functions
        from MCP.tools.employee_tools import (
            search_employees, get_employee_by_id, get_all_employees,
            create_employee, update_employee_by_id, delete_employee_by_id,
            filter_employees_by_position, filter_employees_by_status,
            filter_employees_salary_above, filter_employees_salary_below,
        )
        from MCP.tools.attendance_tools import (
            get_today_attendance, get_today_late_employees,
            get_today_remote_employees, get_today_onsite_employees,
            update_absensi
        )
        from MCP.tools.leave_tools import (
            get_employee_leave_by_id, get_all_employee_leaves, update_leaves
        )
        from MCP.tools.sql_generator import generate_and_execute_sql
        from MCP.tools.utility_tools import get_current_time
        from MCP.tools.email_tools import (
            send_warning_letter, send_email_to_employee, send_broadcast_email
        )
        from MCP.tools.analysis_tools import analyze_attendance_with_policy
        from MCP.tools.export_tools import (
            export_employee_personal_data, export_employee_operational_data
        )
        from MCP.tools.payroll_tools import (
            get_payroll_detail, get_payroll_info, analyze_payroll_anomaly,
            export_payroll_csv, get_payroll_file, create_payroll_report_pdf,
            send_payroll_email
        )
        from MCP.tools.cv_tools import (
            get_employee_cv, analyze_employee_cv, summarize_employee_cv,
            manage_cv_file, extract_cv_from_file
        )
        
        self._tool_functions = {
            "search_employees": search_employees,
            "get_employee_by_id": get_employee_by_id,
            "get_all_employees": get_all_employees,
            "create_employee": create_employee,
            "update_employee_by_id": update_employee_by_id,
            "delete_employee_by_id": delete_employee_by_id,
            "filter_employees_by_position": filter_employees_by_position,
            "filter_employees_by_status": filter_employees_by_status,
            "filter_employees_salary_above": filter_employees_salary_above,
            "filter_employees_salary_below": filter_employees_salary_below,
            "get_today_attendance": get_today_attendance,
            "get_today_late_employees": get_today_late_employees,
            "get_today_remote_employees": get_today_remote_employees,
            "get_today_onsite_employees": get_today_onsite_employees,
            "update_absensi": update_absensi,
            "get_employee_leave_by_id": get_employee_leave_by_id,
            "get_all_employee_leaves": get_all_employee_leaves,
            "update_leaves": update_leaves,
            "generate_and_execute_sql": generate_and_execute_sql,
            "get_current_time": get_current_time,
            # Email tools
            "send_warning_letter": send_warning_letter,
            "send_email_to_employee": send_email_to_employee,
            "send_broadcast_email": send_broadcast_email,
            # Analysis tools
            "analyze_attendance_with_policy": analyze_attendance_with_policy,
            # Export tools
            "export_employee_personal_data": export_employee_personal_data,
            "export_employee_operational_data": export_employee_operational_data,
            # Payroll tools
            "get_payroll_detail": get_payroll_detail,
            "get_payroll_info": get_payroll_info,
            "analyze_payroll_anomaly": analyze_payroll_anomaly,
            "export_payroll_csv": export_payroll_csv,
            "get_payroll_file": get_payroll_file,
            "create_payroll_report_pdf": create_payroll_report_pdf,
            "send_payroll_email": send_payroll_email,
            # CV tools
            "get_employee_cv": get_employee_cv,
            "analyze_employee_cv": analyze_employee_cv,
            "summarize_employee_cv": summarize_employee_cv,
            "manage_cv_file": manage_cv_file,
            "extract_cv_from_file": extract_cv_from_file
        }
        
        return self._tool_functions
    
    def _parse_json_response(self, content: str) -> Dict:
        """Parse JSON from LLM response, handling markdown code blocks and LLM quirks."""
        original_content = content  # Keep for error logging
        
        # Step 1: Strip <think>...</think> tags (some models wrap responses in thinking tags)
        content = re.sub(r'<think>[\s\S]*?</think>', '', content, flags=re.IGNORECASE)
        # Also handle unclosed <think> tags
        content = re.sub(r'<think>[\s\S]*$', '', content, flags=re.IGNORECASE)

        # Step 2: Try to extract JSON from markdown code block
        json_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', content)
        if json_match:
            content = json_match.group(1)
        
        # Step 3: Clean up content
        content = content.strip()
        
        # Step 4: Fix common LLM JSON quirks
        def fix_json_quirks(text: str) -> str:
            # Remove trailing commas before } or ]
            text = re.sub(r',\s*([}\]])', r'\1', text)
            # Convert Python-style booleans to JSON
            text = re.sub(r'\bTrue\b', 'true', text)
            text = re.sub(r'\bFalse\b', 'false', text)
            text = re.sub(r'\bNone\b', 'null', text)
            return text
        
        # Step 5: Try parsing (with and without quirk fixes)
        for attempt_content in [content, fix_json_quirks(content)]:
            try:
                return json.loads(attempt_content)
            except json.JSONDecodeError:
                pass
        
        # Step 6: Try to find all JSON objects in the content (from most nested to least, or similar)
        # We'll use a more refined regex to find all blocks starting with { and ending with }
        # and try to parse each one.
        json_pattern = r'\{(?:[^{}]|(?R))*\}' # Recursive regex-like but we'll use a simpler version
        # Since standard re doesn't support recursive, we use a balance-counter or try all matches
        
        # Simple iterative search for any { ... }
        matches = re.finditer(r'\{', content)
        for m in matches:
            start_idx = m.start()
            # Find the matching closing brace (simple version)
            brace_count = 0
            for i in range(start_idx, len(content)):
                if content[i] == '{':
                    brace_count += 1
                elif content[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        # Potential JSON block
                        extracted = content[start_idx:i+1]
                        for attempt_content in [extracted, fix_json_quirks(extracted)]:
                            try:
                                return json.loads(attempt_content)
                            except json.JSONDecodeError:
                                pass
                        break
        
        # Step 7: Log the failure for debugging
        print(f"[JSON PARSE FAILED] Could not parse LLM response as JSON.")
        print(f"[JSON PARSE FAILED] Full content length: {len(original_content)}")
        return {}
    
    # =========================================================================
    # STAGE 1: PROMPT ESCALATION
    # =========================================================================
    def _log(self, title: str, content: Any):
        """Helper to log verbose output to terminal."""
        from datetime import datetime, date
        
        def json_serializer(obj):
            """Custom serializer for JSON to handle datetime and other non-serializable types."""
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
        
        print(f"\n{'='*20} {title} {'='*20}")
        if isinstance(content, (dict, list)):
            try:
                print(json.dumps(content, indent=2, ensure_ascii=False, default=json_serializer))
            except Exception as e:
                print(f"[LOG ERROR] Could not serialize: {e}")
                print(str(content))
        else:
            print(str(content))
        print(f"{'='*50}\n")

    # =========================================================================
    # STAGE 1: PROMPT ESCALATION
    # =========================================================================
    async def _stage_1_escalate_prompt(self, state: AgentState, conversation_id: int = None) -> AgentState:
        """
        Stage 1: Analyze user query and expand it.
        Handles: ambiguity resolution, entity extraction, intent classification.
        Includes conversation history for understanding follow-up messages.
        """
        self._update_status("Stage 1: Menganalisis pertanyaan...")
        
        # Fetch recent conversation history for context
        recent_history = []
        if conversation_id:
            try:
                recent_history = get_recent_history(conversation_id, limit=5)
            except Exception as e:
                print(f"[CONTEXT WINDOW] Failed to get history for Stage 1: {e}")
        
        try:
            messages = self.prompt_builder.build_for_escalation(
                state.original_query,
                conversation_history=recent_history
            )
            
            response = await asyncio.to_thread(
                ollama.chat,
                model=ESCALATION_MODEL,
                messages=messages,
                options={"temperature": 0.3, "num_predict": 50000}
            )
            
            content = response.get("message", {}).get("content", "")
            self._log("DEBUG: Stage 1 Raw Response", content)
            
            parsed = self._parse_json_response(content)
            self._log("DEBUG: Stage 1 Parsed", parsed)
            
            state.intent = parsed.get("intent", state.original_query)
            state.entities = parsed.get("entities", {})
            state.escalated_query = parsed.get("expanded_query", state.original_query)
            state.stages_completed.append("escalation")
            
            # Store recommended_tools from Stage 1 for use in Stage 2 planning.
            # Use a private key (_recommended_tools) to avoid polluting user entities.
            recommended = parsed.get("recommended_tools", [])
            if isinstance(recommended, list) and recommended:
                state.entities["_recommended_tools"] = recommended
                print(f"[STAGE 1] Recommended tools for Stage 2: {recommended}")
            
            # Emit stage 1 completion with full LLM content
            self._emit_stage(1, "Analisis Pertanyaan", content, "complete")
            
            # Check if clarification needed
            if parsed.get("needs_clarification"):
                state.final_response = parsed.get("clarification_question", "Mohon jelaskan lebih detail.")
                state.stages_completed.append("clarification_needed")
                
        except Exception as e:
            print(f"[STAGE 1 ERROR] {e}")
            # Fallback: use original query
            state.escalated_query = state.original_query
            state.intent = state.original_query
            state.stages_completed.append("escalation_fallback")
            self._emit_stage(1, "Analisis Pertanyaan", f"Fallback: {str(e)}", "error")
        
        return state
    
    # =========================================================================
    # STAGE 2: TOOL PLANNING
    # =========================================================================
    async def _stage_2_plan_tools(self, state: AgentState) -> AgentState:
        """
        Stage 2: Determine which tools to use and in what order.
        Creates an execution plan with dependencies.
        """
        self._update_status("Stage 2: Merencanakan tools yang dibutuhkan...")
        
        try:
            # Extract tool_hints from Stage 1's recommended_tools (if available)
            tool_hints = state.entities.pop("_recommended_tools", None)
            if tool_hints:
                print(f"[STAGE 2 DEBUG] Using Stage 1 tool hints: {tool_hints}")
            else:
                print(f"[STAGE 2 DEBUG] No tool hints from Stage 1 — using full tool catalog")
            
            messages = self.prompt_builder.build_for_planning(
                intent=state.intent,
                entities=state.entities,
                expanded_query=state.escalated_query,
                tool_hints=tool_hints
            )
            
            response = await asyncio.to_thread(
                ollama.chat,
                model=PLANNING_MODEL,
                messages=messages,
                options={"temperature": 0.3, "num_predict": 80000}
            )
            
            # Debug: log prompt length so we can detect context overflow
            prompt_len = sum(len(m.get("content", "")) for m in messages)
            print(f"[STAGE 2 DEBUG] Prompt length: {prompt_len} chars | Model: {PLANNING_MODEL}")
            
            content = response.get("message", {}).get("content", "")
            self._log("DEBUG: Stage 2 Raw Response (Plan)", content)
            
            parsed = self._parse_json_response(content)
            
            raw_plan = parsed.get("plan", [])
            # Fallback for LLMs that use "steps" key instead of "plan"
            if not raw_plan and "steps" in parsed:
                raw_plan = parsed.get("steps", [])
                
            # Normalize list of strings to list of objects
            state.tool_plan = []
            for i, p in enumerate(raw_plan):
                if isinstance(p, str):
                    # Attempt to find common arguments from entities
                    rec_args = {}
                    if "emp_id" in state.entities:
                        rec_args["emp_id"] = state.entities["emp_id"]
                    elif "employee_id" in state.entities:
                        rec_args["emp_id"] = state.entities["employee_id"]
                    
                    # If it's a CV tool, it might need file_path from entities
                    if "cv" in p.lower() and "attachment_file_path" in state.entities:
                        rec_args["file_path"] = state.entities["attachment_file_path"]

                    state.tool_plan.append({
                        "step": i + 1,
                        "name": p,
                        "tool": p,  # Keep tool for backward compatibility
                        "args": rec_args,
                        "arguments": rec_args,  # Keep arguments for backward compatibility
                        "reason": f"auto-recovered tool {p}",
                        "depends_on": i if i > 0 else None
                    })
                elif isinstance(p, dict):
                    state.tool_plan.append(p)

            state.completion_checklist = parsed.get("completion_checklist", [])
            self._log("DEBUG: Stage 2 Tool Plan", state.tool_plan)
            self._log("DEBUG: Stage 2 Completion Checklist", state.completion_checklist)
            
            state.stages_completed.append("planning")
            
            # Emit stage 2 completion with full LLM content
            self._emit_stage(2, "Perencanaan Tools", content, "complete")
            
        except Exception as e:
            print(f"[STAGE 2 ERROR] {e}")
            # Fallback: skip planning and go directly to Ollama function calling
            state.tool_plan = []
            state.stages_completed.append("planning_fallback")
            self._emit_stage(2, "Perencanaan Tools", f"Fallback mode: {str(e)}", "error")
        
        return state
    
    # =========================================================================
    # STAGE 3: TOOL EXECUTION
    # =========================================================================
    async def _execute_single_tool(self, tool_name: str, arguments: Dict, max_retries: int = 3) -> Dict[str, Any]:
        """Execute a single tool via FastMCP in-process, with retry logic for recoverable errors."""
        last_error = None
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    self._update_status(f"Retry {attempt}/{max_retries-1}: {tool_name}...")
                    print(f"[RETRY] Attempt {attempt + 1}/{max_retries} for tool '{tool_name}'")
                
                self._log(f"DEBUG: Executing Tool '{tool_name}' via FastMCP (Attempt {attempt + 1})", arguments)
                
                # ── FastMCP in-process call ──────────────────────────────────
                result = await self._call_mcp_tool(tool_name, arguments)
                # ─────────────────────────────────────────────────────────────
                
                self._log(f"DEBUG: Tool Result '{tool_name}'", result)
                
                # Check if tool returned success
                if isinstance(result, dict) and result.get("success", True):
                    return result
                elif isinstance(result, dict) and not result.get("success"):
                    # Tool returned failure, retry if SQL-related
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
                self._log(f"DEBUG: Tool Error '{tool_name}' (Attempt {attempt + 1})", err_msg)
                
                # Only retry on recoverable errors
                if attempt < max_retries - 1:
                    recoverable = any(kw in last_error.lower() for kw in ['timeout', 'connection', 'serialize', 'ora-'])
                    if recoverable:
                        import time
                        time.sleep(0.5)  # Brief pause before retry
                        continue
                
                return err_msg
        
        return {"success": False, "error": f"Max retries ({max_retries}) exceeded. Last error: {last_error}"}
    
    async def _stage_3_execute_tools(self, state: AgentState) -> AgentState:
        """
        Stage 3: Execute tools in a loop.
        Supports both planned execution and dynamic Ollama function calling.
        """
        self._update_status("Stage 3: Menjalankan tools...")
        
        # If we have a plan from Stage 2, execute it
        if state.tool_plan:
            return await self._execute_planned_tools(state)
        
        # Otherwise, use Ollama's native function calling
        return await self._execute_with_ollama_function_calling(state)
    
    async def _execute_planned_tools(self, state: AgentState) -> AgentState:
        """
        Execute tools based on the plan from Stage 2.
        Features:
        - Case-insensitive placeholder resolution (Oracle returns UPPERCASE)
        - Automatic SQL fallback if a tool fails
        - Smart handling of empty search results
        """
        results_by_step = {}
        
        # List of DB-related tools that can fallback to SQL
        DB_TOOLS = [
            'update_employee_by_id', 'create_employee', 'delete_employee_by_id',
            'update_absensi', 'update_leaves', 'filter_employees_by_status',
            'filter_employees_by_position', 'filter_employees_salary_above',
            'filter_employees_salary_below'
        ]
        
        for step in state.tool_plan:
            step_num = step.get("step", len(state.tool_results) + 1)
            tool_name = step.get("name") or step.get("tool")
            arguments = (step.get("args") or step.get("arguments") or {}).copy()  # Copy to avoid mutating original
            depends_on = step.get("depends_on")
            has_unresolved_dependency = False  # Track if we couldn't resolve a placeholder
            dependency_failed_empty = False  # Track if previous step returned empty
            
            # Resolve dependencies with CASE-INSENSITIVE matching
            if depends_on and depends_on in results_by_step:
                prev_result = results_by_step[depends_on]
                # Normalize the result for case-insensitive access
                normalized_result = self._normalize_result_keys(prev_result)
                
                # Check if previous step returned empty data
                if isinstance(normalized_result, dict) and "DATA" in normalized_result:
                    prev_data = normalized_result["DATA"]
                    if isinstance(prev_data, list) and len(prev_data) == 0:
                        dependency_failed_empty = True
                        print(f"[DEPENDENCY] Step {depends_on} returned empty data - will use SQL fallback")
                
                for key, value in list(arguments.items()):
                    if isinstance(value, str) and "{{step_" in value:
                        # Handle complex placeholders including math expressions
                        # Pattern: {{step_N.result.field}} or {{step_N.result.field * X}}
                        
                        # First, try simple placeholder (single field, no nesting)
                        simple_match = re.match(r'{{step_(\d+)\.result\.(\w+)}}$', value)
                        if simple_match:
                            dep_step = int(simple_match.group(1))
                            dep_field = simple_match.group(2).upper()
                            
                            if dep_step in results_by_step:
                                dep_result = self._normalize_result_keys(results_by_step[dep_step])
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
                                            # Try lowercase too
                                            resolved_value = dep_result.get(dep_field.lower())
                                
                                if resolved_value is not None:
                                    arguments[key] = resolved_value
                                    print(f"[PLACEHOLDER] Resolved {value} → {resolved_value}")
                                else:
                                    # Before giving up, try full nested resolver for single-word paths
                                    raw_dep = results_by_step[dep_step]
                                    resolved_value = self._resolve_nested_path(raw_dep, [dep_field.lower()])
                                    if resolved_value is not None:
                                        arguments[key] = resolved_value
                                        print(f"[PLACEHOLDER] Resolved (fallback search) {value} → {resolved_value}")
                                    else:
                                        has_unresolved_dependency = True
                                        print(f"[PLACEHOLDER] Could not resolve {value} - field {dep_field} not found")
                        else:
                            # Handle math expression like {{step_1.result.salary * 0.85}}
                            math_match = re.match(r'{{step_(\d+)\.result\.(\w+)\s*([*+\-/])\s*([\d.]+)}}', value)
                            if math_match:
                                dep_step = int(math_match.group(1))
                                dep_field = math_match.group(2).upper()
                                operator = math_match.group(3)
                                operand = float(math_match.group(4))
                                
                                if dep_step in results_by_step:
                                    dep_result = self._normalize_result_keys(results_by_step[dep_step])
                                    base_value = None
                                    
                                    if isinstance(dep_result, dict):
                                        if "DATA" in dep_result:
                                            data = dep_result["DATA"]
                                            if isinstance(data, list) and len(data) > 0:
                                                # Map common field aliases
                                                field_aliases = {
                                                    'SALARY': ['BASIC_SALARY', 'SALARY', 'GAJI'],
                                                }
                                                for alias in field_aliases.get(dep_field, [dep_field]):
                                                    if alias in data[0]:
                                                        base_value = data[0][alias]
                                                        break
                                    
                                    if base_value is not None and isinstance(base_value, (int, float)):
                                        if operator == '*':
                                            arguments[key] = base_value * operand
                                        elif operator == '+':
                                            arguments[key] = base_value + operand
                                        elif operator == '-':
                                            arguments[key] = base_value - operand
                                        elif operator == '/':
                                            arguments[key] = base_value / operand if operand != 0 else 0
                                        print(f"[PLACEHOLDER] Calculated {key}={arguments[key]} from {base_value} {operator} {operand}")
                                    else:
                                        has_unresolved_dependency = True
                                        print(f"[PLACEHOLDER] Could not resolve math expression {value}")
                            else:
                                # ── NESTED PATH RESOLVER ─────────────────────────────────────────
                                # Handle {{step_N.result.key1.key2.key3}} (arbitrary depth)
                                nested_match = re.match(r'{{step_(\d+)\.result\.([\w.]+)}}$', value)
                                if nested_match:
                                    dep_step = int(nested_match.group(1))
                                    path_parts = nested_match.group(2).split('.')

                                    if dep_step in results_by_step:
                                        raw_dep_result = results_by_step[dep_step]
                                        resolved_value = self._resolve_nested_path(raw_dep_result, path_parts)
                                        
                                        if resolved_value is not None:
                                            arguments[key] = resolved_value
                                            print(f"[PLACEHOLDER] Resolved nested {value} → {resolved_value}")
                                        else:
                                            has_unresolved_dependency = True
                                            print(f"[PLACEHOLDER] Could not resolve nested path {value}")
                                    else:
                                        has_unresolved_dependency = True
                                        print(f"[PLACEHOLDER] Step {dep_step} not in results yet")
                                else:
                                    # Completely unrecognized placeholder
                                    has_unresolved_dependency = True
                                    print(f"[PLACEHOLDER] Unrecognized placeholder format: {value}")
                    
                    # Handle dict values with placeholders (like updates dict)
                    elif isinstance(value, dict):
                        for sub_key, sub_val in list(value.items()):
                            if isinstance(sub_val, str) and "{{step_" in sub_val:
                                # Try to resolve using salary_multiplier from entities
                                if sub_key.lower() in ['salary', 'basic_salary'] and state.entities:
                                    multiplier = state.entities.get('salary_multiplier')
                                    if multiplier:
                                        # Get base salary from previous step
                                        if depends_on in results_by_step:
                                            dep_result = self._normalize_result_keys(results_by_step[depends_on])
                                            if "DATA" in dep_result and isinstance(dep_result["DATA"], list) and len(dep_result["DATA"]) > 0:
                                                base_salary = dep_result["DATA"][0].get("BASIC_SALARY")
                                                if base_salary:
                                                    value[sub_key] = int(base_salary * float(multiplier))
                                                    print(f"[PLACEHOLDER] Calculated {sub_key}={value[sub_key]} using multiplier {multiplier}")
                                                    continue
                                # Mark as unresolved
                                has_unresolved_dependency = True
                                print(f"[PLACEHOLDER] Unresolved nested placeholder: {sub_val}")
                    
                    # Handle unresolved user_provided placeholders
                    elif isinstance(value, str) and "{{user_provided" in value:
                        if key == "updates" and state.entities:
                            arguments[key] = {
                                k: v for k, v in state.entities.items()
                                if k.upper() in ['NAME', 'EMAIL', 'PHONE', 'POSITION', 'DEPARTMENT', 'STATUS', 'ADDRESS', 'BASIC_SALARY']
                            }
                        else:
                            arguments[key] = None
            
            # ── SMARTER SQL FALLBACK GUARD ────────────────────────────────────────
            # Only fall back to SQL when:
            #   (a) previous step returned genuinely empty data (no ID to chain), OR
            #   (b) emp_id is still an unresolved placeholder string after all resolution attempts
            # Do NOT fall back just because some optional field couldn't be resolved.
            emp_id_val = arguments.get("emp_id")
            emp_id_still_placeholder = isinstance(emp_id_val, str) and "{{" in emp_id_val
            
            should_sql_fallback = tool_name in DB_TOOLS and (
                dependency_failed_empty or emp_id_still_placeholder
            )
            
            if should_sql_fallback:
                reason = "empty data from dependency" if dependency_failed_empty else f"emp_id unresolved: {emp_id_val}"
                self._update_status(f"Dependensi tidak terpenuhi, langsung ke SQL fallback...")
                print(f"[SQL FALLBACK] Skipping {tool_name} due to: {reason}")
                
                result = await self._retry_with_sql_fallback(
                    tool_name=tool_name,
                    original_args=arguments,
                    error_msg="Unresolved dependency from previous step (empty search result)",
                    state=state
                )
                
                if result.get("success"):
                    result["fallback_used"] = "generate_and_execute_sql"
                else:
                    result = {"success": False, "error": "Could not resolve employee ID and SQL fallback failed"}
            else:
                self._update_status(f"Menjalankan {tool_name}...")
                
                # Sanitize arguments before execution to remove any remaining placeholders
                sanitized_args = self._sanitize_arguments(arguments)
                
                result = await self._execute_single_tool(tool_name, sanitized_args)
                
                # Check if failed and eligible for SQL fallback
                if isinstance(result, dict) and not result.get("success") and tool_name in DB_TOOLS:
                    error_msg = result.get("error", "")
                    
                    # Do NOT use SQL fallback for logic/data errors (e.g. updates=None,
                    # invalid field names). These are planning errors, not DB errors.
                    # Only fallback for genuine DB/connection/permission errors.
                    SKIP_FALLBACK_PHRASES = [
                        "harus berupa dict",
                        "tidak ada kolom valid",
                        "NoneType",
                        "'NoneType' object",
                        "tidak ada kolom"
                    ]
                    is_logic_error = any(p.lower() in error_msg.lower() for p in SKIP_FALLBACK_PHRASES)
                    
                    if is_logic_error:
                        print(f"[SQL FALLBACK] Skipping fallback for '{tool_name}' — logic/data error: {error_msg}")
                        # Keep result as-is (the error message is already informative)
                    else:
                        self._update_status(f"Tool gagal, mencoba SQL fallback...")
                        print(f"[SQL FALLBACK] Tool '{tool_name}' failed. Attempting SQL fallback...")
                        
                        # Build a natural language query from the original intent + arguments
                        fallback_result = await self._retry_with_sql_fallback(
                            tool_name=tool_name,
                            original_args=arguments,
                            error_msg=error_msg,
                            state=state
                        )
                        
                        if fallback_result.get("success"):
                            result = fallback_result
                            result["fallback_used"] = "generate_and_execute_sql"
            
            results_by_step[step_num] = result
            state.tool_results.append({
                "step": step_num,
                "name": tool_name,
                "tool": tool_name,
                "args": arguments,
                "arguments": arguments,
                "result": result
            })
            state.total_tool_calls += 1
        
        state.stages_completed.append("execution_planned")
        
        # Emit stage 3 completion
        if state.tool_results:
            tools_executed = [f"- {r['tool']}: {'Berhasil' if r['result'].get('success') else 'Error'}" for r in state.tool_results]
            stage_content = f"**{len(state.tool_results)} tools dieksekusi:**\n" + "\n".join(tools_executed)
        else:
            stage_content = "Tidak ada tools yang dieksekusi."
        self._emit_stage(3, "Eksekusi Tools", stage_content, "complete")
        
        return state
    
    async def _retry_with_sql_fallback(
        self,
        tool_name: str,
        original_args: Dict,
        error_msg: str,
        state: AgentState,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        Retry a failed tool by converting to SQL query.
        Uses generate_and_execute_sql with proper employee identification.
        """
        # SQL fallback uses FastMCP in-process call (no direct import needed)
        
        # Build natural language from tool name and arguments
        action_map = {
            'update_employee_by_id': 'UPDATE data karyawan',
            'create_employee': 'INSERT karyawan baru',
            'delete_employee_by_id': 'DELETE karyawan',
            'update_absensi': 'UPDATE data absensi',
            'update_leaves': 'UPDATE data cuti',
            'filter_employees_by_status': 'SELECT karyawan berdasarkan status',
            'filter_employees_by_position': 'SELECT karyawan berdasarkan posisi',
        }
        
        action = action_map.get(tool_name, f"Execute {tool_name}")
        
        # Build query from arguments
        args_desc = []
        emp_id = original_args.get("emp_id") or original_args.get("employee_id")
        updates = original_args.get("updates") or {}  # Guard: treat None as empty dict
        
        # Check if emp_id is valid (not a placeholder string)
        if emp_id and isinstance(emp_id, str) and emp_id.startswith("{{"):
            emp_id = None  # Invalid placeholder, ignore it
        
        # Extract employee identifier
        employee_identifier = None
        
        if emp_id and isinstance(emp_id, (int, float)):
            # We have a valid numeric ID
            employee_identifier = f"ID = {int(emp_id)}"
        else:
            # Try to get employee name from entities (Stage 1 parsed)
            if state.entities:
                # Try different entity keys that might contain employee name
                for key in ['employee_name', 'name', 'nama', 'karyawan']:
                    if key in state.entities:
                        employee_identifier = f"name LIKE '%{state.entities[key]}%'"
                        break
            
            # If still no identifier, extract from original query
            if not employee_identifier and state.original_query:
                # Look for common patterns like "karyawan X" or "nama X"
                # Note: do NOT put `import re` here — re is already in global scope,
                # and a local import inside a conditional makes Python treat re as unbound
                # anywhere in the function before the import line is reached.
                patterns = [
                    r'karyawan\s+(\w+\s+\w+)',
                    r'nama\s+(\w+\s+\w+)',
                    r'kredensial\s+(\w+\s+\w+)',
                    r'data\s+(\w+\s+\w+)',
                ]
                for pattern in patterns:
                    match = re.search(pattern, state.original_query.lower())
                    if match:
                        name = match.group(1).strip()
                        # Capitalize properly
                        name = ' '.join(word.capitalize() for word in name.split())
                        employee_identifier = f"name LIKE '%{name}%'"
                        break
        
        if employee_identifier:
            args_desc.append(f"WHERE {employee_identifier}")
        
        # Add updates
        if isinstance(updates, dict) and updates:
            set_parts = []
            for k, v in updates.items():
                if v is not None:
                    set_parts.append(f"{k}='{v}'")
            if set_parts:
                args_desc.append(f"SET {', '.join(set_parts)}")
        
        # Construct the natural language query
        # Sanitize natural query to remove any leaked {{placeholder}} strings
        raw_query = f"{action} {' '.join(args_desc)}"
        natural_query = re.sub(r'{{step_\d+\.result\.[^}]+}}', 'Unknown', raw_query)
        
        # If no identifier found, use the full original query context
        if not employee_identifier:
            natural_query = f"Berdasarkan permintaan: {state.original_query}. Gunakan subquery untuk menemukan karyawan berdasarkan nama lama jika diperlukan."
        else:
            # Add original query for additional context
            if state.original_query:
                natural_query += f". Konteks: {state.original_query}"
        
        self._log("DEBUG: SQL Fallback Query", natural_query)
        
        # Execute with retries — via FastMCP in-process
        for attempt in range(max_retries):
            try:
                result = await self._call_mcp_tool(
                    "generate_and_execute_sql",
                    {"natural_query": natural_query, "execute": True, "limit": 100}
                )
                
                if result.get("success"):
                    print(f"[SQL FALLBACK] Success on attempt {attempt + 1}")
                    return result
                else:
                    print(f"[SQL FALLBACK] Attempt {attempt + 1} failed: {result.get('error')}")
                    # Add more context for retry including the error
                    natural_query = f"Retry: {state.original_query}. Error sebelumnya: {result.get('error')}. Gunakan nama karyawan dalam WHERE clause untuk identifikasi."
                    
            except Exception as e:
                print(f"[SQL FALLBACK ERROR] {e}")
        
        return {"success": False, "error": f"SQL fallback failed after {max_retries} attempts", "original_error": error_msg}
    
    async def _execute_with_ollama_function_calling(self, state: AgentState) -> AgentState:
        """Execute tools using Ollama's native function calling."""
        # Build messages with context
        messages = self.prompt_builder.build(
            user_query=state.escalated_query or state.original_query,
            include_schema=True,
            include_tools=False
        )
        
        tools = self._get_tool_definitions()
        iterations = 0
        
        while iterations < MAX_TOOL_ITERATIONS:
            iterations += 1
            
            try:
                response = await asyncio.to_thread(
                    ollama.chat,
                    model=TOOL_MODEL,
                    messages=messages,
                    tools=tools,
                    options={"temperature": 0.3, "num_predict": 100000}
                )
                
                message = response.get("message", {})
                tool_calls = message.get("tool_calls", [])
                
                if not tool_calls:
                    # No more tools to call, we have the final response
                    state.final_response = message.get("content", "")
                    self._log("DEBUG: Stage 3 (Ollama) Final Content", state.final_response)
                    break
                
                # Execute each tool call
                for tool_call in tool_calls:
                    func_name = tool_call.get("function", {}).get("name")
                    func_args = tool_call.get("function", {}).get("arguments", {})
                    
                    self._update_status(f"Menjalankan {func_name}...")
                    result = await self._execute_single_tool(func_name, func_args)
                    
                    state.tool_results.append({
                        "name": func_name,
                        "tool": func_name,
                        "args": func_args,
                        "arguments": func_args,
                        "result": result
                    })
                    state.total_tool_calls += 1
                    
                    # Add assistant message with tool call
                    messages.append({
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [tool_call]
                    })
                    
                    # Add tool response
                    messages.append({
                        "role": "tool",
                        "content": json.dumps(result, ensure_ascii=False)
                    })
                
            except Exception as e:
                print(f"[STAGE 3 ERROR] {e}")
                state.error = str(e)
                break
        
        state.stages_completed.append("execution_ollama")
        
        # Emit stage 3 completion with full LLM content (if final response exists)
        stage3_content = state.final_response if state.final_response else "Tools dieksekusi, melanjutkan ke generasi jawaban."
        self._emit_stage(3, "Eksekusi Tools", stage3_content, "complete")
        
        return state
    
    # =========================================================================
    # STAGE 4: VERIFICATION
    # =========================================================================
    async def _stage_4_verify_results(self, state: AgentState) -> AgentState:
        """
        Stage 4: Verify that tool results satisfy the user's intent.
        Checks each item in the completion checklist against tool results.
        Returns verification_passed = True/False on state.
        """
        self._update_status("Stage 4: Memverifikasi hasil...")
        self._emit_stage(4, "Verifikasi Hasil", "", "processing")
        
        # If no checklist, auto-pass
        if not state.completion_checklist:
            print("[STAGE 4] No completion checklist, auto-passing verification.")
            state.verification_passed = True
            self._emit_stage(4, "Verifikasi Hasil", "Auto-pass: tidak ada checklist dari planning stage.", "complete")
            state.stages_completed.append("verification_auto_pass")
            return state
        
        # If no tool results at all, fail
        if not state.tool_results:
            print("[STAGE 4] No tool results, verification failed.")
            state.verification_passed = False
            self._emit_stage(4, "Verifikasi Hasil", "Gagal: tidak ada hasil tools untuk diverifikasi.", "error")
            state.stages_completed.append("verification_no_results")
            return state
        
        try:
            messages = self.prompt_builder.build_for_verification(
                original_query=state.original_query,
                intent=state.intent,
                tool_results=state.tool_results,
                retry_count=state.retry_count
            )
            
            response = await asyncio.to_thread(
                ollama.chat,
                model=VERIFICATION_MODEL,
                messages=messages,
                options={"temperature": 0.2, "num_predict": 50000}
            )
            
            content = response.get("message", {}).get("content", "")
            self._log("DEBUG: Stage 4 Verification Raw", content)
            
            parsed = self._parse_json_response(content)
            self._log("DEBUG: Stage 4 Verification Parsed", parsed)
            
            all_satisfied = parsed.get("all_satisfied", True)
            state.verification_passed = all_satisfied
            
            # Build stage content for frontend
            stage_lines = []
            
            analysis = parsed.get("analysis", "")
            if analysis:
                stage_lines.append(f"**Analisis:** {analysis}")
            
            if not all_satisfied:
                missing = parsed.get("missing_info", "")
                retry_instructions = parsed.get("retry_instructions", "")
                if missing:
                    stage_lines.append(f"\n⚠️ **Informasi Kurang:** {missing}")
                if retry_instructions:
                    stage_lines.append(f"💡 **Instruksi Perbaikan:** {retry_instructions}")
                    # Store retry hint for next iteration
                    state._retry_hint = retry_instructions
            
            stage_content = "\n".join(stage_lines)
            status = "complete" if all_satisfied else "error"
            self._emit_stage(4, "Verifikasi Hasil", stage_content, status)
            
            state.stages_completed.append(f"verification_{'passed' if all_satisfied else 'failed'}")
            
        except Exception as e:
            print(f"[STAGE 4 ERROR] {e}")
            # On error, auto-pass to avoid blocking the pipeline
            state.verification_passed = True
            state.stages_completed.append("verification_error_auto_pass")
            self._emit_stage(4, "Verifikasi Hasil", f"Error (auto-pass): {str(e)}", "error")
        
        return state
    
    # =========================================================================
    # STAGE 5: RESPONSE GENERATION
    # =========================================================================
    async def _stage_5_generate_response(self, state: AgentState, conversation_id: int = None) -> AgentState:
        """
        Stage 5: Generate final user-friendly response.
        Synthesizes tool results into a coherent answer.
        Includes recent conversation history for context awareness.
        """
        # If we already have a response from Stage 3 (native function calling)
        if state.final_response:
            state.stages_completed.append("response_from_tools")
            return state
        
        self._update_status("Stage 5: Membuat jawaban...")
        self._emit_stage(5, "Generasi Jawaban", "", "processing")
        
        # Fetch recent conversation history for context window
        recent_history = []
        if conversation_id:
            try:
                recent_history = get_recent_history(conversation_id, limit=3)
            except Exception as e:
                print(f"[CONTEXT WINDOW] Failed to get history: {e}")
        
        try:
            messages = self.prompt_builder.build_for_response(
                original_query=state.original_query,
                tool_results=state.tool_results,
                conversation_history=recent_history
            )
            
            response = await asyncio.to_thread(
                ollama.chat,
                model=RESPONSE_MODEL,
                messages=messages,
                options={"temperature": 0.5, "num_predict": 40000000}  # Increased 10x for longer responses
            )
            
            state.final_response = response.get("message", {}).get("content", "")
            self._log("DEBUG: Stage 5 Raw Response", state.final_response)
            
            state.stages_completed.append("response_generation")
            
            # Emit stage 5 completion with full LLM response
            self._emit_stage(5, "Generasi Jawaban", state.final_response, "complete")
            
        except Exception as e:
            print(f"[STAGE 5 ERROR] {e}")
            # Fallback: format raw results
            state.final_response = self._format_fallback_response(state)
            state.stages_completed.append("response_fallback")
            self._emit_stage(5, "Generasi Jawaban", f"Fallback: {str(e)}", "error")
        
        return state
    
    def _get_widget_from_results(self, state: AgentState) -> Optional[Dict]:
        """Extract widget data from tool results if available."""
        if not state.tool_results:
            return None
        
        # Look for widget in tool results (take from the most recent tool execution that has a widget)
        for result in reversed(state.tool_results):
            res_data = result.get("result", {})
            if isinstance(res_data, dict) and res_data.get("widget"):
                return res_data["widget"]
        return None
    
    def _normalize_result_keys(self, data: Any) -> Any:
        """
        Normalize all dictionary keys to uppercase for consistent placeholder resolution.
        Oracle returns uppercase column names, this ensures placeholders work regardless of case.
        """
        if isinstance(data, dict):
            return {k.upper(): self._normalize_result_keys(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._normalize_result_keys(item) for item in data]
        return data

    def _sanitize_arguments(self, args: Any) -> Any:
        """
        recursively sanitize arguments by removing unresolved placeholders.
        """
        if isinstance(args, str):
            # If string is JUST a placeholder, return None
            if re.match(r'^{{step_\d+\.result\..*}}$', args):
                return None
            # If string CONTAINS placeholder, strip it
            return re.sub(r'{{step_\d+\.result\.[^}]+}}', '', args).strip()
        elif isinstance(args, dict):
            return {k: self._sanitize_arguments(v) for k, v in args.items()}
        elif isinstance(args, list):
            return [self._sanitize_arguments(item) for item in args]
        return args
    
    def _resolve_nested_path(self, data: Any, path_parts: List[str]) -> Any:
        """
        Resolve a nested dot-path from a tool result.
        
        Supports arbitrary depth, e.g. ['employee', 'id'] resolves:
          {"employee": {"id": 10, ...}}  →  10
        
        Also does a deep-search fallback: if the direct path fails, it
        recursively searches ALL dict nodes for a key matching the LAST
        segment of the path (case-insensitive). This handles cases where
        the LLM references a field by name but the exact nesting differs.
        
        Args:
            data: The tool result dict/list/scalar to search
            path_parts: List of key segments to traverse (lowercase)
            
        Returns:
            Resolved value, or None if not found
        """
        def _walk(node: Any, parts: List[str]) -> Any:
            """Iterative walk following path_parts."""
            current = node
            for part in parts:
                if current is None:
                    return None
                if isinstance(current, dict):
                    # Case-insensitive key lookup
                    matched = None
                    for k, v in current.items():
                        if k.lower() == part.lower():
                            matched = v
                            break
                    current = matched
                elif isinstance(current, list):
                    # If list, try the first element
                    if len(current) > 0:
                        current = current[0]
                        # Retry the same part on the first element
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

        def _deep_search(node: Any, target_key: str) -> Any:
            """Depth-first search for any node with matching key name."""
            if isinstance(node, dict):
                for k, v in node.items():
                    if k.lower() == target_key.lower() and not isinstance(v, (dict, list)):
                        return v
                # Recurse into children
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

        # First: try direct path traversal
        direct = _walk(data, path_parts)
        if direct is not None:
            return direct

        # Fallback: deep-search by last path segment (e.g. 'id' from 'employee.id')
        if path_parts:
            return _deep_search(data, path_parts[-1])

        return None
    

    def _format_fallback_response(self, state: AgentState) -> str:
        """Format a fallback response from raw tool results."""
        if not state.tool_results:
            return "Maaf, saya tidak dapat menemukan informasi yang diminta."
        
        response = "Berikut hasil pencarian:\n\n"
        for result in state.tool_results:
            tool = result.get("tool", "unknown")
            data = result.get("result", {})
            
            if isinstance(data, dict) and data.get("success"):
                if "data" in data:
                    response += f"**{tool}**:\n```json\n{json.dumps(data['data'], indent=2, ensure_ascii=False)[:1000]}\n```\n\n"
                else:
                    response += f"**{tool}**: {data.get('message', 'Berhasil')}\n\n"
            elif isinstance(data, dict) and data.get("error"):
                response += f"**{tool}**: Error - {data['error']}\n\n"
        
        return response
    
    # =========================================================================
    # MAIN ENTRY POINT
    # =========================================================================
    async def chat(
        self,
        query: str,
        user_id: int = 1,
        conversation_id: Optional[int] = None,
        skip_escalation: bool = False,
        skip_planning: bool = False,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main entry point for chat interaction.
        
        Args:
            query: User query
            user_id: User ID for conversation management
            conversation_id: Optional existing conversation ID
            skip_escalation: Skip Stage 1 (for simple queries)
            skip_planning: Skip Stage 2 (use native function calling only)
            session_id: Socket session ID for abort support
            
        Returns:
            Dict with response and metadata
        """
        self._session_id = session_id
        if session_id:
            clear_abort(session_id)  # Start fresh on every new request

        self._update_status("Memulai proses...")
        
        # Initialize state
        state = AgentState(original_query=query)
        
        # Get or create conversation
        conversation = self.conversation_manager.get_or_create_conversation(
            user_id=user_id,
            conversation_id=conversation_id
        )
        
        # Add user message to history
        self.conversation_manager.add_message(
            conversation_id=conversation.id,
            role="user",
            content=query
        )
        
        def _check_abort():
            if session_id and is_aborted(session_id):
                raise AgentAbortedError("Proses dihentikan oleh pengguna.")

        try:
            for attempt in range(MAX_VERIFICATION_RETRIES + 1):
                _check_abort()  # Before Stage 1

                # Stage 1: Escalation (with conversation context for follow-ups)
                if not skip_escalation:
                    state = await self._stage_1_escalate_prompt(state, conversation_id=conversation.id)
                    
                    # Early exit if clarification needed
                    if "clarification_needed" in state.stages_completed:
                        return self._build_response(state, conversation.id)
                else:
                    state.escalated_query = query
                    state.intent = query

                _check_abort()  # After Stage 1, before Stage 2
                
                # Stage 2: Planning
                if not skip_planning:
                    state = await self._stage_2_plan_tools(state)

                _check_abort()  # After Stage 2, before Stage 3
                
                # Stage 3: Tool Execution
                state = await self._stage_3_execute_tools(state)

                _check_abort()  # After Stage 3, before Stage 4
                
                # Stage 4: Verification
                state = await self._stage_4_verify_results(state)
                
                if state.verification_passed or attempt >= MAX_VERIFICATION_RETRIES:
                    if not state.verification_passed:
                        print(f"[VERIFICATION] Max retries ({MAX_VERIFICATION_RETRIES}) reached. Proceeding with available data.")
                    break
                
                # Retry: reset state for new attempt but keep context
                print(f"[VERIFICATION] Retry {attempt + 1}/{MAX_VERIFICATION_RETRIES} - Resetting for re-execution...")
                
                # ── NOTIFY FRONTEND: clear stages and start over ──────────────
                self._emit_stage_reset(retry_attempt=attempt + 1)
                
                retry_hint = getattr(state, '_retry_hint', '')
                original_query = state.original_query
                if retry_hint:
                    executed_tools = [r.get('tool') for r in state.tool_results]
                    executed_str = ", ".join(executed_tools) if executed_tools else "Tidak ada"
                    original_query = f"{state.original_query}\n\n[INFO EVALUASI RETRY: Tools yang sudah dieksekusi: {executed_str}.\nInstruksi Perbaikan: {retry_hint}.\nFokuskan plan HANYA untuk mengambil informasi yang kurang sesuai instruksi perbaikan. JANGAN ulangi tool yang sudah berhasil.]"
                
                state.tool_plan = []
                # We KEEP state.tool_results so accumulated data across retries is passed to Stage 4 & 5
                # state.tool_results = []  
                state.completion_checklist = []
                state.verification_passed = False
                state.final_response = ""
                state.retry_count = attempt + 1
                state.original_query = original_query

            _check_abort()  # Before Stage 5
            
            # Stage 5: Response Generation (with context window)
            state = await self._stage_5_generate_response(state, conversation_id=conversation.id)
            
        except AgentAbortedError as e:
            print(f"[ABORT] Agent stopped: {e}")
            state.error = "aborted"
            state.final_response = "⏹ Proses dihentikan."
        except Exception as e:
            state.error = str(e)
            state.final_response = f"Maaf, terjadi kesalahan: {str(e)}"
        
        # Add assistant response to history
        if state.final_response:
            self.conversation_manager.add_message(
                conversation_id=conversation.id,
                role="assistant",
                content=state.final_response,
                metadata={
                    "tool_calls": len(state.tool_results),
                    "widget": self._get_widget_from_results(state)
                }
            )
        
        return self._build_response(state, conversation.id)
    
    def _build_response(self, state: AgentState, conversation_id: int) -> Dict[str, Any]:
        """Build the final response dict."""
        return {
            "response": state.final_response,
            "conversation_id": conversation_id,
            "metadata": {
                "stages_completed": state.stages_completed,
                "total_tool_calls": state.total_tool_calls,
                "intent": state.intent,
                "intent": state.intent,
                "has_error": state.error is not None,
                "widget": self._get_widget_from_results(state)
            },
            "tool_results": state.tool_results if state.tool_results else None,
            "stage_logs": self._stage_logs,  # For Process tab
            "error": state.error
        }
    
    def chat_simple(self, query: str) -> str:
        """
        Simplified chat that only returns the response string.
        Useful for quick testing.
        """
        result = self.chat(query, skip_escalation=True, skip_planning=True)
        return result.get("response", "")


# Singleton instance
_agent: Optional[HRAgent] = None


def get_agent() -> HRAgent:
    """Get or create HRAgent singleton."""
    global _agent
    if _agent is None:
        _agent = HRAgent()
    return _agent
