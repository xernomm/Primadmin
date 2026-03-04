"""
Agent Orchestrator — Lifecycle Supervisor.

Controls the entire 5-stage agent pipeline:
  Escalation → Planning → Validation → Execution → Verification → Response

Guard constants:
  MAX_PLAN_RETRY         = 3   (plan invalid → regenerate)
  MAX_MCP_RETRY          = 2   (MCP error → retry, handled in execution_module)
  MAX_VERIFICATION_LOOP  = 3   (verification fails → re-plan + re-execute)
"""
import asyncio
from typing import Optional, Callable, Dict, Any, List

from agent.core import AgentAbortedError, is_aborted
from orchestrator.agent_state import AgentState
from orchestrator._utils import ModuleContext
from orchestrator.plan_validator import validate_plan
from orchestrator import (
    escalation_module,
    plan_module,
    execution_module,
    verification_module,
    response_module,
)


# ── Guard constants ──────────────────────────────────────────────────────────
MAX_PLAN_RETRY = 3
MAX_MCP_RETRY = 2           # handled inside execution_module per-tool
MAX_VERIFICATION_LOOP = 3


class AgentOrchestrator:
    """
    Lifecycle Supervisor for the HR Agent.

    Responsibilities:
      - Control flow across all stages
      - Validate plans before sending to MCP
      - Handle retry loops (plan, MCP, verification)
      - Maintain append-only state
      - Logging lifecycle events

    NOT responsibilities:
      - Executing tools (→ execution_module)
      - Resolving dependencies (→ execution_module)
      - Modifying plan content (→ never)
    """

    def __init__(
        self,
        prompt_builder,
        conversation_manager=None,
        status_callback: Optional[Callable[[str], None]] = None,
        stage_callback: Optional[Callable[[Dict], None]] = None,
        sub_status_callback: Optional[Callable[[Dict], None]] = None,
        session_id: Optional[str] = None,
    ):
        self.prompt_builder = prompt_builder
        self.conversation_manager = conversation_manager
        self.status_callback = status_callback
        self.stage_callback = stage_callback
        self.sub_status_callback = sub_status_callback
        self.session_id = session_id

    def _check_abort(self):
        """Raise AgentAbortedError if user pressed Stop."""
        if self.session_id and is_aborted(self.session_id):
            raise AgentAbortedError("Proses dihentikan oleh pengguna.")

    async def run(
        self,
        query: str,
        user_id: int = 1,
        conversation_id: Optional[int] = None,
        skip_escalation: bool = False,
        skip_planning: bool = False,
    ) -> Dict[str, Any]:
        """
        Main entry point — orchestrate the full lifecycle.

        Returns dict with: response, conversation_id, metadata, tool_results, stage_logs, error.
        """
        print(f"\n[ORCHESTRATOR] === Starting lifecycle for: {query[:80]}... ===")

        # ── Initialize state & context ────────────────────────────────────
        state = AgentState(original_query=query)
        ctx = ModuleContext(
            prompt_builder=self.prompt_builder,
            conversation_id=conversation_id,
            status_callback=self.status_callback,
            stage_callback=self.stage_callback,
            sub_status_callback=self.sub_status_callback,
            session_id=self.session_id,
        )
        ctx.update_status("Memulai proses...")

        # ── Conversation management ───────────────────────────────────────
        conversation = None
        if self.conversation_manager:
            conversation = self.conversation_manager.get_or_create_conversation(
                user_id=user_id,
                conversation_id=conversation_id,
            )
            self.conversation_manager.add_message(
                conversation_id=conversation.id,
                role="user",
                content=query,
            )
            conversation_id = conversation.id

        try:
            for loop in range(MAX_VERIFICATION_LOOP):
                self._check_abort()

                # ── Stage 1: Escalation ───────────────────────────────────
                if not skip_escalation:
                    state = await escalation_module.run_escalation(
                        state, ctx, conversation_id=conversation_id
                    )
                    if "clarification_needed" in state.stages_completed:
                        break  # early exit → response
                else:
                    state.escalated_query = query
                    state.intent = query

                self._check_abort()

                # ── Stage 2 + Validation Loop ─────────────────────────────
                if not skip_planning:
                    state = await self._plan_with_validation(state, ctx)
                    if state.error:
                        break  # plan generation exhausted

                self._check_abort()

                # ── Stage 3: Execution ────────────────────────────────────
                state = await execution_module.run_execution(state, ctx)

                self._check_abort()

                # ── Stage 4: Verification ─────────────────────────────────
                state = await verification_module.run_verification(state, ctx)

                if state.verification_passed:
                    print(f"[ORCHESTRATOR] Verification PASSED on loop {loop + 1}")
                    break

                if loop >= MAX_VERIFICATION_LOOP - 1:
                    print(f"[ORCHESTRATOR] Max verification loops ({MAX_VERIFICATION_LOOP}) exhausted")
                    break

                # ── Retry: reset for next loop ────────────────────────────
                print(f"[ORCHESTRATOR] Verification FAILED — retrying (loop {loop + 2}/{MAX_VERIFICATION_LOOP})")
                ctx.emit_stage_reset(retry_attempt=loop + 1)

                retry_hint = state._retry_hint
                original_query = state.original_query
                if retry_hint:
                    executed_tools = [r.get('tool') for r in state.tool_results]
                    executed_str = ", ".join(executed_tools) if executed_tools else "Tidak ada"
                    original_query = (
                        f"{state.original_query}\n\n"
                        f"[INFO EVALUASI RETRY: Tools yang sudah dieksekusi: {executed_str}.\n"
                        f"Instruksi Perbaikan: {retry_hint}.\n"
                        f"Fokuskan plan HANYA untuk mengambil informasi yang kurang sesuai instruksi perbaikan. "
                        f"JANGAN ulangi tool yang sudah berhasil.]"
                    )

                state.tool_plan = []
                state.completion_checklist = []
                state.verification_passed = False
                state.final_response = ""
                state.retry_count = loop + 1
                state.original_query = original_query

            self._check_abort()

            # ── Stage 5: Response ─────────────────────────────────────────
            state = await response_module.run_response(state, ctx, conversation_id=conversation_id)

        except AgentAbortedError as e:
            print(f"[ORCHESTRATOR] Agent stopped: {e}")
            state.error = "aborted"
            state.final_response = "Proses dihentikan."
        except Exception as e:
            print(f"[ORCHESTRATOR] Unexpected error: {e}")
            state.error = str(e)
            state.final_response = f"Maaf, terjadi kesalahan: {str(e)}"

        # ── Save assistant response ───────────────────────────────────────
        if state.final_response and self.conversation_manager and conversation:
            self.conversation_manager.add_message(
                conversation_id=conversation.id,
                role="assistant",
                content=state.final_response,
                metadata={
                    "tool_calls": len(state.tool_results),
                    "widget": self._get_widget_from_results(state),
                },
            )

        print(f"[ORCHESTRATOR] === Lifecycle complete — State: {state.get_summary()} ===\n")

        return self._build_response(state, conversation_id or 0, ctx)

    # ── Plan + Validation Loop ────────────────────────────────────────────────

    async def _plan_with_validation(self, state, ctx):
        """Generate plan with validation loop. Retries up to MAX_PLAN_RETRY if invalid."""
        for attempt in range(1, MAX_PLAN_RETRY + 1):
            state = await plan_module.run_planning(state, ctx)

            if not state.tool_plan:
                print(f"[ORCHESTRATOR] Empty plan on attempt {attempt}")
                if attempt >= MAX_PLAN_RETRY:
                    state.error = f"Failed to generate plan after {MAX_PLAN_RETRY} attempts"
                    return state
                continue

            is_valid, errors = validate_plan(state.tool_plan)

            if is_valid:
                source = "llm_generated" if attempt == 1 else f"regenerated_attempt_{attempt}"
                state.add_plan(state.tool_plan, source=source)
                ctx.emit_sub_status({"type": "plan_validated", "valid": True, "steps": len(state.tool_plan), "attempt": attempt})
                print(f"[ORCHESTRATOR] Plan valid ({len(state.tool_plan)} steps) on attempt {attempt}")
                return state
            else:
                ctx.emit_sub_status({"type": "plan_invalid", "valid": False, "attempt": attempt, "errors": errors})
                print(f"[ORCHESTRATOR] Plan invalid on attempt {attempt}: {errors}")
                state.tool_plan = []  # Clear invalid plan
                if attempt >= MAX_PLAN_RETRY:
                    state.error = f"Plan validation failed after {MAX_PLAN_RETRY} attempts: {errors}"
                    return state

        return state

    # ── Response Builder ──────────────────────────────────────────────────────

    @staticmethod
    def _get_widget_from_results(state):
        """Extract widget data from tool results if available."""
        if not state.tool_results:
            return None
        for result in reversed(state.tool_results):
            res_data = result.get("result", {})
            if isinstance(res_data, dict) and res_data.get("widget"):
                return res_data["widget"]
        return None

    def _build_response(self, state, conversation_id, ctx):
        """Build the final response dict."""
        return {
            "response": state.final_response,
            "conversation_id": conversation_id,
            "metadata": {
                "stages_completed": state.stages_completed,
                "total_tool_calls": state.total_tool_calls,
                "intent": state.intent,
                "has_error": state.error is not None,
                "widget": self._get_widget_from_results(state),
                "state_summary": state.get_summary(),
            },
            "tool_results": state.tool_results if state.tool_results else None,
            "stage_logs": ctx._stage_logs,
            "error": state.error,
        }
