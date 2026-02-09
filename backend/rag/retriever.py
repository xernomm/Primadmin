"""
Simple RAG retriever for HR policy documents.
Uses keyword matching for MVP; can be upgraded to embeddings later.
"""
import os
import re
from pathlib import Path
from typing import List, Dict, Optional

# Get documents directory
DOCUMENTS_DIR = Path(__file__).parent.parent / "documents" / "policies"


def load_all_documents() -> Dict[str, str]:
    """
    Load all policy documents from the policies directory.
    
    Returns:
        Dict mapping filename to content
    """
    documents = {}
    
    if not DOCUMENTS_DIR.exists():
        return documents
    
    for file_path in DOCUMENTS_DIR.glob("*.md"):
        try:
            content = file_path.read_text(encoding="utf-8")
            documents[file_path.name] = content
        except Exception as e:
            print(f"[RAG] Failed to load {file_path.name}: {e}")
    
    return documents


def search_documents(query: str, top_k: int = 2) -> List[Dict]:
    """
    Search policy documents using simple keyword matching.
    MVP implementation - can be upgraded to embeddings/vector search later.
    
    Args:
        query: Search query
        top_k: Number of results to return
        
    Returns:
        List of matching document chunks with scores
    """
    documents = load_all_documents()
    
    if not documents:
        return []
    
    # Normalize query
    query_lower = query.lower()
    query_words = set(re.findall(r'\w+', query_lower))
    
    # Define keyword mappings for common HR topics
    keyword_mappings = {
        "leave_policy.md": ["cuti", "leave", "libur", "tahunan", "sakit", "melahirkan", "izin", "mangkir"],
        "attendance_policy.md": ["absen", "absensi", "kehadiran", "terlambat", "telat", "wfh", "remote", "lembur", "jam kerja"],
        "company_rules.md": ["peraturan", "aturan", "sp", "peringatan", "sanksi", "phk", "resign", "pengunduran", "etik"]
    }
    
    results = []
    
    for filename, content in documents.items():
        score = 0
        
        # Check direct keyword matches
        keywords = keyword_mappings.get(filename, [])
        for keyword in keywords:
            if keyword in query_lower:
                score += 10
        
        # Check if any query words appear in content
        content_lower = content.lower()
        for word in query_words:
            if len(word) > 3 and word in content_lower:
                score += 1
        
        if score > 0:
            results.append({
                "source": filename,
                "content": content,
                "score": score
            })
    
    # Sort by score and return top_k
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


def get_relevant_context(query: str) -> str:
    """
    Get relevant policy context for a query.
    Returns formatted string for injection into LLM prompt.
    
    Args:
        query: User query
        
    Returns:
        Formatted context string
    """
    results = search_documents(query, top_k=2)
    
    if not results:
        return ""
    
    context_parts = []
    for result in results:
        source = result["source"].replace("_", " ").replace(".md", "").title()
        # Truncate content to avoid token overflow
        content = result["content"][:1500]
        if len(result["content"]) > 1500:
            content += "\n... (dipotong untuk efisiensi)"
        
        context_parts.append(f"### {source}\n{content}")
    
    return "\n\n---\n\n".join(context_parts)


# Singleton cache
_documents_cache: Optional[Dict[str, str]] = None


def get_rag_context(query: str) -> str:
    """
    Main entry point for getting RAG context.
    Alias for get_relevant_context.
    """
    return get_relevant_context(query)
