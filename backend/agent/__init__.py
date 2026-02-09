"""
Agent module for HR Agent.
Provides the core multi-stage pipeline and prompt building.
"""
from .core import HRAgent, get_agent
from .prompt_templates import (
    get_tool_definitions,
    get_tool_descriptions,
    get_tool_summary,
    SYSTEM_PROMPT,
    PROMPT_ESCALATION_TEMPLATE,
    TOOL_PLANNING_TEMPLATE,
    RESPONSE_GENERATION_TEMPLATE
)
from .prompt_builder import PromptBuilder, get_prompt_builder

__all__ = [
    'HRAgent',
    'get_agent',
    'PromptBuilder',
    'get_prompt_builder',
    'get_tool_definitions',
    'get_tool_descriptions',
    'get_tool_summary',
    'SYSTEM_PROMPT',
    'PROMPT_ESCALATION_TEMPLATE',
    'TOOL_PLANNING_TEMPLATE',
    'RESPONSE_GENERATION_TEMPLATE'
]
