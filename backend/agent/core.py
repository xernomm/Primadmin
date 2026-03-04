"""
HR Agent Core Module - 5-Stage Pipeline.

This module is a THIN WRAPPER that delegates to the orchestrator module.
The orchestrator controls the lifecycle: Escalation → Planning → Execution → Verification → Response.

Public interface (backward compatible):
  - HRAgent          — main agent class
  - get_agent()      — singleton accessor
  - set_abort()      — stop current agent run
  - clear_abort()    — clear stop flag
  - is_aborted()     — check stop flag
  - AgentAbortedError — exception for stopped runs
  - AgentState        — re-exported from orchestrator.agent_state
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

# Models configuration — used by orchestrator stage modules via import
ESCALATION_MODEL = "qwen3:latest"       # Fast model for JSON parsing/intent
PLANNING_MODEL = "qwen3:latest"          # Fast model for tool planning (JSON)
TOOL_MODEL = "qwen3:latest"              # Main model with function calling
VERIFICATION_MODEL = "qwen3:latest"      # Verification/reasoning
RESPONSE_MODEL = "qwen2.5:1.5b"          # Reasoning model for final response
SQL_MODEL = "qwen2.5-coder:latest"       # SQL-specific model

# Maximum iterations for tool execution loop
MAX_TOOL_ITERATIONS = 50
MAX_VERIFICATION_RETRIES = 5

# MCP Server URL — runs as a separate SSE process on port 8000
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://localhost:8000/sse")


# ══════════════════════════════════════════════════════════════════════════════
# ABORT / STOP MECHANISM
# ══════════════════════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════════════════════
# AGENT STATE — re-export from orchestrator for backward compatibility
# ══════════════════════════════════════════════════════════════════════════════

from orchestrator.agent_state import AgentState


# ══════════════════════════════════════════════════════════════════════════════
# HR AGENT — Thin wrapper that delegates to AgentOrchestrator
# ══════════════════════════════════════════════════════════════════════════════

class HRAgent:
    """
    HR Agent with 5-stage pipeline.
    
    Delegates all stage execution to the orchestrator module.
    This class maintains the same public interface for backward compatibility.
    """
    
    def __init__(
        self,
        conversation_manager: Optional[ConversationHistoryManager] = None,
        prompt_builder: Optional[PromptBuilder] = None,
        status_callback: Optional[Callable[[str], None]] = None,
        stage_callback: Optional[Callable[[Dict], None]] = None,
        sub_status_callback: Optional[Callable[[Dict], None]] = None,
    ):
        self.conversation_manager = conversation_manager or ConversationHistoryManager()
        self.prompt_builder = prompt_builder or get_prompt_builder()
        self.status_callback = status_callback
        self.stage_callback = stage_callback
        self.sub_status_callback = sub_status_callback
        self._stage_logs = []
        self._session_id: Optional[str] = None

    async def chat(
        self,
        query: str,
        user_id: int = 1,
        conversation_id: Optional[int] = None,
        skip_escalation: bool = False,
        skip_planning: bool = False,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Main entry point for chat interaction.
        Delegates to AgentOrchestrator.run().

        Args:
            query: User query
            user_id: User ID for conversation management
            conversation_id: Optional existing conversation ID
            skip_escalation: Skip Stage 1
            skip_planning: Skip Stage 2
            session_id: Socket session ID for abort support

        Returns:
            Dict with response and metadata
        """
        self._session_id = session_id
        if session_id:
            clear_abort(session_id)

        # Lazy import to avoid circular deps
        from orchestrator.orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator(
            prompt_builder=self.prompt_builder,
            conversation_manager=self.conversation_manager,
            status_callback=self.status_callback,
            stage_callback=self.stage_callback,
            sub_status_callback=self.sub_status_callback,
            session_id=session_id,
        )

        result = await orchestrator.run(
            query=query,
            user_id=user_id,
            conversation_id=conversation_id,
            skip_escalation=skip_escalation,
            skip_planning=skip_planning,
        )

        # Sync stage_logs back for backward compat
        self._stage_logs = result.get("stage_logs", [])

        return result

    def chat_simple(self, query: str) -> str:
        """Simplified chat that only returns the response string."""
        result = self.chat(query, skip_escalation=True, skip_planning=True)
        return result.get("response", "")


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ══════════════════════════════════════════════════════════════════════════════

_agent: Optional[HRAgent] = None


def get_agent() -> HRAgent:
    """Get or create HRAgent singleton."""
    global _agent
    if _agent is None:
        _agent = HRAgent()
    return _agent
