"""
Prompt builder module for HR Agent.
Builds context-aware prompts with token budget management.
"""
from typing import List, Dict, Optional, Any
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from context.tokenizer import get_tokenizer
from context.window_manager import ContextWindowManager, TokenBudget
from database.schema_discovery import get_schema_context
from .prompt_templates import SYSTEM_PROMPT, get_tool_descriptions


class PromptBuilder:
    """
    Builds prompts with proper context management.
    Handles schema injection, RAG results, and conversation history.
    """
    
    def __init__(
        self, 
        context_manager: Optional[ContextWindowManager] = None,
        token_budget: Optional[TokenBudget] = None
    ):
        """
        Initialize prompt builder.
        
        Args:
            context_manager: Context window manager (uses default if not provided)
            token_budget: Token budget configuration
        """
        self.tokenizer = get_tokenizer()
        self.budget = token_budget or TokenBudget()
        self.context_manager = context_manager or ContextWindowManager(budget=self.budget)
    
    def build(
        self,
        user_query: str,
        conversation_history: List[Dict] = None,
        rag_results: List[str] = None,
        include_schema: bool = True,
        include_tools: bool = True
    ) -> List[Dict[str, str]]:
        """
        Build complete messages array for LLM.
        
        Args:
            user_query: Current user query
            conversation_history: List of previous messages
            rag_results: List of RAG document chunks
            include_schema: Whether to include DB schema
            include_tools: Whether to include tool descriptions
            
        Returns:
            List of messages ready for LLM API
        """
        # Get schema context if needed
        schema_context = ""
        if include_schema:
            try:
                schema_context = get_schema_context('sql')
            except Exception:
                schema_context = ""
        
        # Build system prompt with optional tool descriptions
        system = SYSTEM_PROMPT
        if include_tools:
            system += "\n\n" + get_tool_descriptions()
        
        # Build context with window manager
        components = self.context_manager.build_context(
            system_prompt=system,
            db_schema=schema_context,
            rag_results=rag_results or [],
            conversation_history=conversation_history or [],
            current_query=user_query
        )
        
        # Build final messages
        messages = self.context_manager.build_messages(components)
        
        return messages
    
    def build_simple(
        self,
        user_query: str,
        system_prompt: str = None
    ) -> List[Dict[str, str]]:
        """
        Build simple messages without context management.
        
        Args:
            user_query: User query
            system_prompt: Optional custom system prompt
            
        Returns:
            List of messages
        """
        return [
            {"role": "system", "content": system_prompt or SYSTEM_PROMPT},
            {"role": "user", "content": user_query}
        ]
    
    def build_for_escalation(self, user_query: str, conversation_history: List[Dict] = None) -> List[Dict[str, str]]:
        """Build messages for Stage 1 (prompt escalation) with conversation context."""
        from .prompt_templates import PROMPT_ESCALATION_TEMPLATE
        
        # Format conversation context
        context_text = "(Tidak ada percakapan sebelumnya - ini adalah pertanyaan baru)"
        if conversation_history:
            context_lines = []
            for msg in conversation_history:
                role_label = "User" if msg.get("role") == "user" else "Assistant"
                content = msg.get("content", "")[:300]  # Limit length
                if len(msg.get("content", "")) > 300:
                    content += "..."
                context_lines.append(f"**{role_label}**: {content}")
            context_text = "\n".join(context_lines)
        
        prompt = PROMPT_ESCALATION_TEMPLATE.format(
            user_query=user_query,
            conversation_context=context_text
        )
        return [{"role": "user", "content": prompt}]
    
    def build_for_planning(
        self,
        intent: str,
        entities: Dict,
        expanded_query: str
    ) -> List[Dict[str, str]]:
        """Build messages for Stage 2 (tool planning)."""
        from .prompt_templates import TOOL_PLANNING_TEMPLATE, get_tool_summary
        
        prompt = TOOL_PLANNING_TEMPLATE.format(
            intent=intent,
            entities=str(entities),
            expanded_query=expanded_query,
            tool_descriptions=get_tool_summary()
        )
        return [{"role": "user", "content": prompt}]
    
    def build_for_response(
        self,
        original_query: str,
        tool_results: List[Dict],
        conversation_history: List[Dict] = None
    ) -> List[Dict[str, str]]:
        """Build messages for Stage 4 (response generation)."""
        from .prompt_templates import RESPONSE_GENERATION_TEMPLATE
        import json
        from datetime import datetime, date

        def json_serializer(obj):
            """Handle datetime serialization."""
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            return str(obj)
        
        # Format tool results
        results_text = ""
        for i, result in enumerate(tool_results, 1):
            results_text += f"\n### Tool {i}: {result.get('tool', 'unknown')}\n"
            results_text += f"```json\n{json.dumps(result.get('result', {}), indent=2, ensure_ascii=False, default=json_serializer)}\n```\n"
        
        # Format conversation context
        context_text = "(Tidak ada percakapan sebelumnya)"
        if conversation_history:
            context_lines = []
            for msg in conversation_history:
                role_label = "User" if msg.get("role") == "user" else "Assistant"
                content = msg.get("content", "")[:200]  # Limit length
                if len(msg.get("content", "")) > 200:
                    content += "..."
                context_lines.append(f"**{role_label}**: {content}")
            context_text = "\n".join(context_lines)
        
        prompt = RESPONSE_GENERATION_TEMPLATE.format(
            original_query=original_query,
            conversation_context=context_text,
            tool_results=results_text
        )
        return [{"role": "user", "content": prompt}]
    
    def estimate_tokens(self, messages: List[Dict]) -> int:
        """Estimate total tokens for a messages array."""
        return self.tokenizer.estimate_messages_tokens(messages)


# Singleton instance
_prompt_builder: Optional[PromptBuilder] = None


def get_prompt_builder() -> PromptBuilder:
    """Get or create PromptBuilder singleton."""
    global _prompt_builder
    if _prompt_builder is None:
        _prompt_builder = PromptBuilder()
    return _prompt_builder
