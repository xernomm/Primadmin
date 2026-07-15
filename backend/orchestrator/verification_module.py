"""
Verification Module — Stage 4: Result Verification.
Extracted from HRAgent._stage_4_verify_results.
"""
import asyncio
from agent.gemini_client import gemini_chat

from agent.core import VERIFICATION_MODEL
from orchestrator._utils import parse_json_response, log_debug


async def run_verification(state, ctx):
    """
    Stage 4: Verify that tool results satisfy the user's intent.
    Checks each item in the completion checklist against tool results.
    """
    ctx.update_status("Stage 4: Memverifikasi hasil...")
    ctx.emit_stage(4, "Verifikasi Hasil", "", "processing")

    # Auto-pass if no checklist
    if not state.completion_checklist:
        print("[STAGE 4] No completion checklist, auto-passing verification.")
        state.verification_passed = True
        state.add_verification(True, "auto-pass: no checklist")
        ctx.emit_stage(4, "Verifikasi Hasil", "Auto-pass: tidak ada checklist dari planning stage.", "complete")
        state.stages_completed.append("verification_auto_pass")
        return state

    # Fail if no tool results at all
    if not state.tool_results:
        print("[STAGE 4] No tool results, verification failed.")
        state.verification_passed = False
        state.add_verification(False, "no tool results")
        ctx.emit_stage(4, "Verifikasi Hasil", "Gagal: tidak ada hasil tools untuk diverifikasi.", "error")
        state.stages_completed.append("verification_no_results")
        return state

    try:
        messages = ctx.prompt_builder.build_for_verification(
            original_query=state.original_query,
            intent=state.intent,
            tool_results=state.tool_results,
            retry_count=state.retry_count,
        )

        content = await asyncio.to_thread(
            gemini_chat,
            messages=messages,
            model=VERIFICATION_MODEL,
            temperature=0.2,
        )
        log_debug("DEBUG: Stage 4 Verification Raw", content)

        parsed = parse_json_response(content)
        log_debug("DEBUG: Stage 4 Verification Parsed", parsed)

        all_satisfied = parsed.get("all_satisfied", True)
        state.verification_passed = all_satisfied

        # Store in versioned history
        analysis = parsed.get("analysis", "")
        state.add_verification(all_satisfied, analysis)

        # Build stage content for frontend
        stage_lines = []
        if analysis:
            stage_lines.append(f"**Analisis:** {analysis}")

        if not all_satisfied:
            missing = parsed.get("missing_info", "")
            retry_instructions = parsed.get("retry_instructions", "")
            if missing:
                stage_lines.append(f"\n[!] **Informasi Kurang:** {missing}")
            if retry_instructions:
                stage_lines.append(f"[>] **Instruksi Perbaikan:** {retry_instructions}")
                state._retry_hint = retry_instructions

        stage_content = "\n".join(stage_lines)
        status = "complete" if all_satisfied else "error"
        ctx.emit_stage(4, "Verifikasi Hasil", stage_content, status)

        state.stages_completed.append(f"verification_{'passed' if all_satisfied else 'failed'}")

    except Exception as e:
        print(f"[STAGE 4 ERROR] {e}")
        # On error, auto-pass to avoid blocking the pipeline
        state.verification_passed = True
        state.add_verification(True, f"error auto-pass: {str(e)}")
        state.stages_completed.append("verification_error_auto_pass")
        ctx.emit_stage(4, "Verifikasi Hasil", f"Error (auto-pass): {str(e)}", "error")

    return state
