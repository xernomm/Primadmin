"""
Response Module — Stage 5: Final Response Generation.
Extracted from HRAgent._stage_5_generate_response and _format_fallback_response.
"""
import json
import asyncio
from agent.gemini_client import gemini_chat

from agent.core import RESPONSE_MODEL
from orchestrator._utils import log_debug


async def run_response(state, ctx, conversation_id=None):
    """
    Stage 5: Generate final user-friendly response.
    Synthesizes tool results into a coherent answer.
    """
    # If we already have a response from Stage 3 (native function calling)
    if state.final_response:
        state.stages_completed.append("response_from_tools")
        return state

    ctx.update_status("Stage 5: Membuat jawaban...")
    ctx.emit_stage(5, "Generasi Jawaban", "", "processing")

    # Fetch recent conversation history for context window
    from chats.chat_service import get_recent_history

    recent_history = []
    if conversation_id:
        try:
            recent_history = get_recent_history(conversation_id, limit=3)
        except Exception as e:
            print(f"[CONTEXT WINDOW] Failed to get history: {e}")

    try:
        messages = ctx.prompt_builder.build_for_response(
            original_query=state.original_query,
            tool_results=state.tool_results,
            conversation_history=recent_history,
        )

        content = await asyncio.to_thread(
            gemini_chat,
            messages=messages,
            model=RESPONSE_MODEL,
            temperature=0.5,
        )

        state.final_response = content
        log_debug("DEBUG: Stage 5 Raw Response", state.final_response)

        state.stages_completed.append("response_generation")
        ctx.emit_stage(5, "Generasi Jawaban", state.final_response, "complete")

    except Exception as e:
        print(f"[STAGE 5 ERROR] {e}")
        state.final_response = _format_fallback_response(state)
        state.stages_completed.append("response_fallback")
        ctx.emit_stage(5, "Generasi Jawaban", f"Fallback: {str(e)}", "error")

    return state


def _format_fallback_response(state) -> str:
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
