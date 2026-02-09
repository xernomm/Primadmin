"""
Tokenizer module using tiktoken.
Provides token counting and text truncation utilities.
"""
import tiktoken
from typing import List, Dict, Optional


class Tokenizer:
    """
    Token counting and manipulation using tiktoken.
    Uses cl100k_base encoding (GPT-4/Claude compatible).
    For Qwen models, this is approximate but sufficiently accurate.
    """
    
    def __init__(self, encoding_name: str = "cl100k_base"):
        """
        Initialize tokenizer with specified encoding.
        
        Args:
            encoding_name: tiktoken encoding name (default: cl100k_base)
        """
        self.encoding = tiktoken.get_encoding(encoding_name)
        self.encoding_name = encoding_name
    
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text.
        
        Args:
            text: Input text to count tokens for
            
        Returns:
            Number of tokens
        """
        if not text:
            return 0
        return len(self.encoding.encode(text))
    
    def truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """
        Truncate text to maximum number of tokens.
        
        Args:
            text: Input text to truncate
            max_tokens: Maximum number of tokens to keep
            
        Returns:
            Truncated text
        """
        if not text:
            return ""
        
        tokens = self.encoding.encode(text)
        if len(tokens) <= max_tokens:
            return text
        
        truncated_tokens = tokens[:max_tokens]
        return self.encoding.decode(truncated_tokens)
    
    def split_into_chunks(self, text: str, chunk_size: int, overlap: int = 50) -> List[str]:
        """
        Split text into chunks of specified token size with overlap.
        Useful for RAG document chunking.
        
        Args:
            text: Input text to split
            chunk_size: Target size of each chunk in tokens
            overlap: Number of overlapping tokens between chunks
            
        Returns:
            List of text chunks
        """
        if not text:
            return []
        
        tokens = self.encoding.encode(text)
        chunks = []
        
        start = 0
        while start < len(tokens):
            end = min(start + chunk_size, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text = self.encoding.decode(chunk_tokens)
            chunks.append(chunk_text)
            
            # Move start forward by chunk_size - overlap
            start = start + chunk_size - overlap
            if start >= len(tokens):
                break
        
        return chunks
    
    def estimate_messages_tokens(self, messages: List[Dict]) -> int:
        """
        Estimate total tokens from a list of messages.
        Accounts for message formatting overhead.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            
        Returns:
            Estimated total tokens
        """
        total = 0
        for msg in messages:
            # ~4 tokens overhead per message (role, formatting, separators)
            total += 4
            content = msg.get("content", "")
            if content:
                total += self.count_tokens(content)
            
            # Add extra tokens for tool calls if present
            if msg.get("tool_calls"):
                total += 20  # Rough estimate for tool call formatting
        
        # Add a buffer for overall message array formatting
        total += 3
        
        return total
    
    def fits_in_budget(self, text: str, budget: int) -> bool:
        """
        Check if text fits within token budget.
        
        Args:
            text: Text to check
            budget: Token budget
            
        Returns:
            True if text fits in budget
        """
        return self.count_tokens(text) <= budget


# Singleton instance
_tokenizer: Optional[Tokenizer] = None


def get_tokenizer(encoding_name: str = "cl100k_base") -> Tokenizer:
    """
    Get or create Tokenizer singleton.
    
    Args:
        encoding_name: tiktoken encoding name
        
    Returns:
        Tokenizer instance
    """
    global _tokenizer
    if _tokenizer is None or _tokenizer.encoding_name != encoding_name:
        _tokenizer = Tokenizer(encoding_name)
    return _tokenizer
