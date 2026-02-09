"""
HR Agent Core Module - 4-Stage Pipeline.

This implements the multi-stage AI agent that can:
1. Escalate and expand user prompts
2. Plan which tools to use
3. Execute tools in a loop
4. Generate final response

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
ESCALATION_MODEL = "llama3:latest"  # Fast model for parsing
PLANNING_MODEL = "qwen3:latest"        # Good for reasoning
TOOL_MODEL = "qwen3:latest"            # Main model with function calling
RESPONSE_MODEL = "deepseek-r1:latest"        # Response generation
SQL_MODEL = "qwen2.5-coder:latest"    # SQL-specific model

# Maximum iterations for tool execution loop
MAX_TOOL_ITERATIONS = 15


@dataclass
class AgentState:
    """State container for agent execution."""
    original_query: str
    escalated_query: str = ""
    intent: str = ""
    entities: Dict = field(default_factory=dict)
    tool_plan: List[Dict] = field(default_factory=list)
    tool_results: List[Dict] = field(default_factory=list)
    final_response: str = ""
    error: Optional[str] = None
    
    # Metadata
    stages_completed: List[str] = field(default_factory=list)
    total_tool_calls: int = 0


class HRAgent:
    """
    HR Agent with 4-stage pipeline.
    
    Stage 1 (Escalation): Analyze and expand user query
    Stage 2 (Planning): Determine tools and execution order
    Stage 3 (Execution): Execute tools in a loop
    Stage 4 (Response): Generate final user-friendly response
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
        self._tool_functions = None
        self._stage_logs = []  # Store stage logs for Process tab
    
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
        
        # Store for Process tab
        self._stage_logs.append(stage_data)
        
        # Emit to frontend if callback registered
        if self.stage_callback:
            self.stage_callback(stage_data)
        
        print(f"[STAGE {stage_num}] {stage_name}: {status}")
    
    def _get_tool_definitions(self) -> List[Dict]:
        """Get cached tool definitions."""
        if self._tools_cache is None:
            self._tools_cache = get_tool_definitions()
        return self._tools_cache
    
    def _get_tool_functions(self) -> Dict[str, Callable]:
        """Get mapping of tool names to functions."""
        if self._tool_functions is not None:
            return self._tool_functions
        
        # Import all tool functions
        from MCP.tools.employee_tools import (
            search_employees, get_employee_by_id, get_all_employees,
            create_employee, update_employee_by_id, delete_employee_by_id,
            filter_employees_by_position, filter_employees_by_status,
            filter_employees_salary_above, filter_employees_salary_below
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
            "export_employee_operational_data": export_employee_operational_data
        }
        
        return self._tool_functions
    
    def _parse_json_response(self, content: str) -> Dict:
        """Parse JSON from LLM response, handling markdown code blocks."""
        # Try to extract JSON from markdown code block
        json_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', content)
        if json_match:
            content = json_match.group(1)
        
        # Clean up content
        content = content.strip()
        
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to find any JSON object in the content
            json_pattern = r'\{[\s\S]*\}'
            match = re.search(json_pattern, content)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
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
                options={"temperature": 0.3, "num_predict": 5000}
            )
            
            content = response.get("message", {}).get("content", "")
            self._log("DEBUG: Stage 1 Raw Response", content)
            
            parsed = self._parse_json_response(content)
            self._log("DEBUG: Stage 1 Parsed", parsed)
            
            state.intent = parsed.get("intent", state.original_query)
            state.entities = parsed.get("entities", {})
            state.escalated_query = parsed.get("expanded_query", state.original_query)
            state.stages_completed.append("escalation")
            
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
            messages = self.prompt_builder.build_for_planning(
                intent=state.intent,
                entities=state.entities,
                expanded_query=state.escalated_query
            )
            
            response = await asyncio.to_thread(
                ollama.chat,
                model=PLANNING_MODEL,
                messages=messages,
                options={"temperature": 0.3, "num_predict": 8000}
            )
            
            content = response.get("message", {}).get("content", "")
            self._log("DEBUG: Stage 2 Raw Response (Plan)", content)
            
            parsed = self._parse_json_response(content)
            
            state.tool_plan = parsed.get("plan", [])
            self._log("DEBUG: Stage 2 Tool Plan", state.tool_plan)
            
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
        """Execute a single tool with given arguments, with retry logic for recoverable errors."""
        tool_funcs = self._get_tool_functions()
        
        if tool_name not in tool_funcs:
            return {"success": False, "error": f"Tool '{tool_name}' not found"}
        
        last_error = None
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    self._update_status(f"Retry {attempt}/{max_retries-1}: {tool_name}...")
                    print(f"[RETRY] Attempt {attempt + 1}/{max_retries} for tool '{tool_name}'")
                
                self._log(f"DEBUG: Executing Tool '{tool_name}' (Attempt {attempt + 1})", arguments)
                func = tool_funcs[tool_name]
                # Run tool in thread to avoid blocking event loop
                result = await asyncio.to_thread(func, **arguments)
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
            tool_name = step.get("tool")
            arguments = step.get("arguments", {}).copy()  # Copy to avoid mutating original
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
                        
                        # First, try simple placeholder
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
                                
                                if resolved_value is not None:
                                    arguments[key] = resolved_value
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
            
            # If dependency was empty or has unresolved placeholders, skip direct tool and go to SQL fallback
            if (dependency_failed_empty or has_unresolved_dependency) and tool_name in DB_TOOLS:
                self._update_status(f"Dependensi tidak terpenuhi, langsung ke SQL fallback...")
                print(f"[SQL FALLBACK] Skipping {tool_name} due to unresolved dependency. Going to SQL fallback.")
                
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
                result = await self._execute_single_tool(tool_name, arguments)
                
                # Check if failed and eligible for SQL fallback
                if isinstance(result, dict) and not result.get("success") and tool_name in DB_TOOLS:
                    self._update_status(f"Tool gagal, mencoba SQL fallback...")
                    print(f"[SQL FALLBACK] Tool '{tool_name}' failed. Attempting SQL fallback...")
                    
                    # Build a natural language query from the original intent + arguments
                    fallback_result = await self._retry_with_sql_fallback(
                        tool_name=tool_name,
                        original_args=arguments,
                        error_msg=result.get("error", "Unknown error"),
                        state=state
                    )
                    
                    if fallback_result.get("success"):
                        result = fallback_result
                        result["fallback_used"] = "generate_and_execute_sql"
            
            results_by_step[step_num] = result
            state.tool_results.append({
                "step": step_num,
                "tool": tool_name,
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
        from MCP.tools.sql_generator import generate_and_execute_sql
        
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
        updates = original_args.get("updates", {})
        
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
                import re
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
        natural_query = f"{action} {' '.join(args_desc)}"
        
        # If no identifier found, use the full original query context
        if not employee_identifier:
            natural_query = f"Berdasarkan permintaan: {state.original_query}. Gunakan subquery untuk menemukan karyawan berdasarkan nama lama jika diperlukan."
        else:
            # Add original query for additional context
            if state.original_query:
                natural_query += f". Konteks: {state.original_query}"
        
        self._log("DEBUG: SQL Fallback Query", natural_query)
        
        # Execute with retries
        for attempt in range(max_retries):
            try:
                result = await asyncio.to_thread(
                    generate_and_execute_sql,
                    natural_query=natural_query,
                    execute=True,
                    limit=100
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
                    options={"temperature": 0.3, "num_predict": 10000}
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
                        "tool": func_name,
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
    # STAGE 4: RESPONSE GENERATION
    # =========================================================================
    async def _stage_4_generate_response(self, state: AgentState, conversation_id: int = None) -> AgentState:
        """
        Stage 4: Generate final user-friendly response.
        Synthesizes tool results into a coherent answer.
        Includes recent conversation history for context awareness.
        """
        # If we already have a response from Stage 3 (native function calling)
        if state.final_response:
            state.stages_completed.append("response_from_tools")
            return state
        
        self._update_status("Stage 4: Membuat jawaban...")
        
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
                options={"temperature": 0.5, "num_predict": 40000}  # Increased for longer responses
            )
            
            state.final_response = response.get("message", {}).get("content", "")
            self._log("DEBUG: Stage 4 Raw Response", state.final_response)
            
            state.stages_completed.append("response_generation")
            
            # Emit stage 4 completion with full LLM response
            self._emit_stage(4, "Generasi Jawaban", state.final_response, "complete")
            
        except Exception as e:
            print(f"[STAGE 4 ERROR] {e}")
            # Fallback: format raw results
            state.final_response = self._format_fallback_response(state)
            state.stages_completed.append("response_fallback")
            self._emit_stage(4, "Generasi Jawaban", f"Fallback: {str(e)}", "error")
        
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
        skip_planning: bool = False
    ) -> Dict[str, Any]:
        """
        Main entry point for chat interaction.
        
        Args:
            query: User query
            user_id: User ID for conversation management
            conversation_id: Optional existing conversation ID
            skip_escalation: Skip Stage 1 (for simple queries)
            skip_planning: Skip Stage 2 (use native function calling only)
            
        Returns:
            Dict with response and metadata
        """
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
        
        try:
            # Stage 1: Escalation (with conversation context for follow-ups)
            if not skip_escalation:
                state = await self._stage_1_escalate_prompt(state, conversation_id=conversation.id)
                
                # Early exit if clarification needed
                if "clarification_needed" in state.stages_completed:
                    return self._build_response(state, conversation.id)
            else:
                state.escalated_query = query
                state.intent = query
            
            # Stage 2: Planning
            if not skip_planning:
                state = await self._stage_2_plan_tools(state)
            
            # Stage 3: Tool Execution
            state = await self._stage_3_execute_tools(state)
            
            # Stage 4: Response Generation (with context window)
            state = await self._stage_4_generate_response(state, conversation_id=conversation.id)
            
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
