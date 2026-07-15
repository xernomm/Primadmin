"""
Plan Module — Stage 2: Tool Planning.
Extracted from HRAgent._stage_2_plan_tools.
"""
import asyncio
from agent.gemini_client import gemini_chat

from agent.core import PLANNING_MODEL
from orchestrator._utils import parse_json_response, log_debug


async def run_planning(state, ctx):
    """
    Stage 2: Determine which tools to use and in what order.
    Creates an execution plan with dependencies.
    """
    ctx.update_status("Stage 2: Merencanakan tools yang dibutuhkan...")

    try:
        # Extract tool_hints from Stage 1's recommended_tools
        tool_hints = state.entities.pop("_recommended_tools", None)
        if tool_hints:
            print(f"[STAGE 2 DEBUG] Using Stage 1 tool hints: {tool_hints}")
        else:
            print(f"[STAGE 2 DEBUG] No tool hints from Stage 1 — using full tool catalog")

        messages = ctx.prompt_builder.build_for_planning(
            intent=state.intent,
            entities=state.entities,
            expanded_query=state.escalated_query,
            tool_hints=tool_hints,
        )

        content = await asyncio.to_thread(
            gemini_chat,
            messages=messages,
            model=PLANNING_MODEL,
            temperature=0.3,
        )

        prompt_len = sum(len(m.get("content", "")) for m in messages)
        print(f"[STAGE 2 DEBUG] Prompt length: {prompt_len} chars | Model: {PLANNING_MODEL}")
        log_debug("DEBUG: Stage 2 Raw Response (Plan)", content)

        parsed = parse_json_response(content)

        raw_plan = parsed.get("plan", [])
        # Fallback for LLMs that use "steps" key
        if not raw_plan and "steps" in parsed:
            raw_plan = parsed.get("steps", [])

        # Normalize list of strings to list of objects
        normalized_plan = []
        for i, p in enumerate(raw_plan):
            if isinstance(p, str):
                rec_args = {}
                if "emp_id" in state.entities:
                    rec_args["emp_id"] = state.entities["emp_id"]
                elif "employee_id" in state.entities:
                    rec_args["emp_id"] = state.entities["employee_id"]
                if "cv" in p.lower() and "attachment_file_path" in state.entities:
                    rec_args["file_path"] = state.entities["attachment_file_path"]

                normalized_plan.append({
                    "step": i + 1,
                    "name": p,
                    "tool": p,
                    "args": rec_args,
                    "arguments": rec_args,
                    "reason": f"auto-recovered tool {p}",
                    "depends_on": i if i > 0 else None,
                })
            elif isinstance(p, dict):
                normalized_plan.append(p)

        state.tool_plan = normalized_plan
        state.completion_checklist = parsed.get("completion_checklist", [])
        log_debug("DEBUG: Stage 2 Tool Plan", state.tool_plan)
        log_debug("DEBUG: Stage 2 Completion Checklist", state.completion_checklist)

        state.stages_completed.append("planning")
        
        # Format the parsed plan into user-friendly markdown
        md_plan = ""
        reasoning = parsed.get("reasoning", "")
        if reasoning:
            md_plan += f"**Analisis:** {reasoning}\n\n"
            
        if state.tool_plan:
            md_plan += "**Langkah Eksekusi:**\n"
            for step in state.tool_plan:
                name = step.get("name", step.get("tool", "unknown"))
                reason = step.get("reason", "menjalankan tool")
                md_plan += f"{step.get('step', '-')}. **`{name}`** - {reason}\n"
                
        if state.completion_checklist:
            md_plan += "\n**Target Selesai:**\n"
            for item in state.completion_checklist:
                md_plan += f"- [ ] {item}\n"
                
        # If somehow parsing failed entirely, fallback to raw content wrapped in code block
        if not md_plan.strip():
            md_plan = f"```json\n{content}\n```"

        ctx.emit_stage(2, "Perencanaan Tools", md_plan.strip(), "complete")

    except Exception as e:
        print(f"[STAGE 2 ERROR] {e}")
        state.tool_plan = []
        state.stages_completed.append("planning_fallback")
        ctx.emit_stage(2, "Perencanaan Tools", f"Fallback mode: {str(e)}", "error")

    return state
