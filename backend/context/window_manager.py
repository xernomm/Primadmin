"""
Context window management module.
Handles token budget allocation and context building for LLM prompts.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from .tokenizer import Tokenizer, get_tokenizer


@dataclass
class TokenBudget:
    """
    Token budget allocation for different context components.
    Total default budget: ~6000 tokens (safe for 8k context models)
    """
    system_prompt: int = 500
    db_schema: int = 800
    rag_context: int = 1000
    conversation_history: int = 1500
    current_query: int = 200
    response_buffer: int = 2000
    
    @property
    def total(self) -> int:
        """Total token budget including response buffer"""
        return (
            self.system_prompt +
            self.db_schema +
            self.rag_context +
            self.conversation_history +
            self.current_query +
            self.response_buffer
        )
    
    @property
    def input_budget(self) -> int:
        """Total input token budget (excluding response buffer)"""
        return self.total - self.response_buffer


@dataclass
class ContextComponents:
    """Container for all context components"""
    system_prompt: str = ""
    db_schema: str = ""
    rag_context: str = ""
    conversation_history: List[Dict] = field(default_factory=list)
    current_query: str = ""
    
    # Metadata
    rag_used: bool = False
    history_count: int = 0
    total_tokens: int = 0


class ContextWindowManager:
    """
    Manages context window to fit within model limits.
    Handles truncation and prioritization of context components.
    """
    
    def __init__(
        self, 
        tokenizer: Optional[Tokenizer] = None, 
        budget: Optional[TokenBudget] = None
    ):
        """
        Initialize context window manager.
        
        Args:
            tokenizer: Tokenizer instance (uses singleton if not provided)
            budget: Token budget configuration
        """
        self.tokenizer = tokenizer or get_tokenizer()
        self.budget = budget or TokenBudget()
    
    def build_context(
        self,
        system_prompt: str,
        db_schema: str,
        rag_results: List[str],
        conversation_history: List[Dict],
        current_query: str
    ) -> ContextComponents:
        """
        Build final context with token budget management.
        
        Priority order when budget is tight:
        1. System prompt (never truncate)
        2. Current query (never truncate)
        3. Recent conversation (sliding window)
        4. DB schema (truncate if needed)
        5. RAG context (truncate first if needed)
        
        Args:
            system_prompt: System prompt template
            db_schema: Database schema description
            rag_results: List of RAG document chunks
            conversation_history: List of message dicts
            current_query: Current user query
            
        Returns:
            ContextComponents with all processed components
        """
        result = ContextComponents()
        
        # 1. System prompt (highest priority, truncate last resort)
        result.system_prompt = self._truncate_if_needed(
            system_prompt, 
            self.budget.system_prompt
        )
        
        # 2. Current query (high priority)
        result.current_query = self._truncate_if_needed(
            current_query,
            self.budget.current_query
        )
        
        # 3. DB Schema (medium priority)
        result.db_schema = self._truncate_if_needed(
            db_schema,
            self.budget.db_schema
        )
        
        # 4. RAG context (lower priority, combine and truncate)
        if rag_results:
            rag_combined = "\n\n---\n\n".join(rag_results)
            result.rag_context = self._truncate_if_needed(
                rag_combined,
                self.budget.rag_context
            )
            result.rag_used = True
        
        # 5. Conversation history (sliding window, keep most recent)
        result.conversation_history = self._truncate_history(
            conversation_history,
            self.budget.conversation_history
        )
        result.history_count = len(result.conversation_history)
        
        # Calculate total tokens
        result.total_tokens = self._calculate_total_tokens(result)
        
        return result
    
    def _truncate_if_needed(self, text: str, max_tokens: int) -> str:
        """Truncate text if it exceeds token budget"""
        if not text:
            return ""
        
        current_tokens = self.tokenizer.count_tokens(text)
        if current_tokens <= max_tokens:
            return text
        
        return self.tokenizer.truncate_to_tokens(text, max_tokens)
    
    def _truncate_history(
        self,
        messages: List[Dict],
        max_tokens: int
    ) -> List[Dict]:
        """
        Truncate conversation history from oldest first.
        Always keeps most recent messages.
        
        Args:
            messages: List of message dicts
            max_tokens: Maximum total tokens for history
            
        Returns:
            List of messages that fit within budget
        """
        if not messages:
            return []
        
        # Start from most recent, add backwards until budget exceeded
        result = []
        current_tokens = 0
        
        for msg in reversed(messages):
            content = msg.get("content", "")
            msg_tokens = self.tokenizer.count_tokens(content) + 4  # +4 for overhead
            
            if current_tokens + msg_tokens > max_tokens:
                break
            
            result.insert(0, msg)
            current_tokens += msg_tokens
        
        return result
    
    def _calculate_total_tokens(self, components: ContextComponents) -> int:
        """Calculate total tokens for all components"""
        total = 0
        
        total += self.tokenizer.count_tokens(components.system_prompt)
        total += self.tokenizer.count_tokens(components.db_schema)
        total += self.tokenizer.count_tokens(components.rag_context)
        total += self.tokenizer.count_tokens(components.current_query)
        total += self.tokenizer.estimate_messages_tokens(components.conversation_history)
        
        return total
    
    def build_messages(self, components: ContextComponents) -> List[Dict[str, str]]:
        """
        Build final messages array for LLM.
        
        Args:
            components: ContextComponents from build_context
            
        Returns:
            List of messages ready for LLM API
        """
        # Combine system context
        system_content = components.system_prompt
        
        if components.db_schema:
            system_content += f"\n\n## Database Schema\n{components.db_schema}"
        
        if components.rag_context:
            system_content += f"\n\n## Relevant HR Policies\n{components.rag_context}"
        else:
            system_content += "\n\n## Relevant HR Policies\nTidak ada dokumen yang relevan untuk query ini."
        
        messages = [{"role": "system", "content": system_content}]
        
        # Add conversation history
        messages.extend(components.conversation_history)
        
        # Add current query
        messages.append({"role": "user", "content": components.current_query})
        
        return messages
    
    def get_available_tokens(self, used_tokens: int) -> int:
        """Get remaining tokens available for response"""
        return self.budget.total - used_tokens
