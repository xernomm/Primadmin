"""
RAG module for HR Agent.
Provides simple keyword-based document retrieval.
"""
from .retriever import get_rag_context, search_documents, get_relevant_context

__all__ = [
    "get_rag_context",
    "search_documents", 
    "get_relevant_context"
]
