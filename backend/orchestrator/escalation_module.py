"""
Escalation Module — Stage 1: Analyze and expand user query.
Extracted from HRAgent._stage_1_escalate_prompt.
"""
import asyncio
import ollama

from agent.core import ESCALATION_MODEL
from orchestrator._utils import parse_json_response, log_debug


async def run_escalation(state, ctx, conversation_id=None):
    """
    Stage 1: Analyze user query → intent, entities, expanded_query.
    Uses conversation history for follow-up context.
    """
    from chats.chat_service import get_recent_history

    ctx.update_status("Stage 1: Menganalisis pertanyaan...")

    # Fetch recent conversation history for context
    recent_history = []
    if conversation_id:
        try:
            recent_history = get_recent_history(conversation_id, limit=5)
        except Exception as e:
            print(f"[CONTEXT WINDOW] Failed to get history for Stage 1: {e}")

    try:
        messages = ctx.prompt_builder.build_for_escalation(
            state.original_query,
            conversation_history=recent_history,
        )

        response = await asyncio.to_thread(
            ollama.chat,
            model=ESCALATION_MODEL,
            messages=messages,
            options={"temperature": 0.3, "num_predict": 50000},
        )

        content = response.get("message", {}).get("content", "")
        log_debug("DEBUG: Stage 1 Raw Response", content)

        parsed = parse_json_response(content)
        log_debug("DEBUG: Stage 1 Parsed", parsed)

        state.intent = parsed.get("intent", state.original_query)
        state.entities = parsed.get("entities", {})
        state.escalated_query = parsed.get("expanded_query", state.original_query)
        state.stages_completed.append("escalation")

        # Store recommended_tools for Stage 2
        recommended = parsed.get("recommended_tools", [])
        if isinstance(recommended, list) and recommended:
            state.entities["_recommended_tools"] = recommended
            print(f"[STAGE 1] Recommended tools for Stage 2: {recommended}")

        ctx.emit_stage(1, "Analisis Pertanyaan", content, "complete")

        # Check if clarification needed
        if parsed.get("needs_clarification"):
            state.final_response = parsed.get(
                "clarification_question", "Mohon jelaskan lebih detail."
            )
            state.stages_completed.append("clarification_needed")

    except Exception as e:
        print(f"[STAGE 1 ERROR] {e}")
        state.escalated_query = state.original_query
        state.intent = state.original_query
        state.stages_completed.append("escalation_fallback")
        ctx.emit_stage(1, "Analisis Pertanyaan", f"Fallback: {str(e)}", "error")

    return state
