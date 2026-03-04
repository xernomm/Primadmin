"""
Orchestrator Agent State — Append-based versioned state management.
Compatible with existing agent.core.AgentState fields.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class AgentState:
    """
    State container for orchestrator-managed agent execution.
    All updates use append-based versioning — history is never overwritten.
    """
    # ── Core fields (backward compatible with agent.core.AgentState) ──────────
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
    stages_completed: List[str] = field(default_factory=list)
    total_tool_calls: int = 0

    # ── Append-only versioned collections ─────────────────────────────────────
    plan_versions: List[Dict] = field(default_factory=list)
    mcp_results: List[Dict] = field(default_factory=list)
    verification_results: List[Dict] = field(default_factory=list)

    # ── Internal ──────────────────────────────────────────────────────────────
    _retry_hint: str = ""

    # ── Versioned mutation helpers ────────────────────────────────────────────

    def add_plan(self, plan: List[Dict], source: str = ""):
        """Append a plan version. Also sets tool_plan for backward compat."""
        self.plan_versions.append({
            "plan": plan,
            "source": source,
            "version": len(self.plan_versions) + 1,
        })
        self.tool_plan = plan

    def add_mcp_result(self, result: Dict):
        """Append an MCP execution result."""
        self.mcp_results.append(result)

    def add_verification(self, satisfied: bool, reason: str):
        """Append a verification result."""
        self.verification_results.append({
            "satisfied": satisfied,
            "reason": reason,
        })

    @property
    def latest_plan(self) -> List[Dict]:
        """Get the most recent plan version."""
        if self.plan_versions:
            return self.plan_versions[-1]["plan"]
        return self.tool_plan

    def get_summary(self) -> Dict:
        """Return a summary of state for logging/debugging."""
        return {
            "plan_versions": len(self.plan_versions),
            "mcp_executions": len(self.mcp_results),
            "verification_count": len(self.verification_results),
            "stages_completed": self.stages_completed,
            "total_tool_calls": self.total_tool_calls,
            "retry_count": self.retry_count,
        }
