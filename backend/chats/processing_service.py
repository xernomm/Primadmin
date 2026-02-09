"""
Processing Stages Service
Handles CRUD operations for agent processing stages, allowing persistence across page refreshes.
"""
import json
from database.db import get_connection


def save_processing_stage(conversation_id: int, stage_number: int, stage_name: str, content: str, status: str = "complete") -> int:
    """
    Save or update a processing stage for a conversation.
    Returns the stage ID.
    """
    if conversation_id is None or conversation_id < 0:
        # Skip saving for new/unsaved conversations
        return -1
    
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Check if stage already exists
        cur.execute("""
            SELECT id FROM processing_stages 
            WHERE conversation_id = :conv_id AND stage_number = :stage_num
        """, {"conv_id": conversation_id, "stage_num": stage_number})
        
        row = cur.fetchone()
        
        if row:
            # Update existing stage
            stage_id = row[0]
            cur.execute("""
                UPDATE processing_stages 
                SET stage_name = :name, content = :content, status = :status
                WHERE id = :id
            """, {"name": stage_name, "content": content, "status": status, "id": stage_id})
        else:
            # Insert new stage
            cur.execute("""
                INSERT INTO processing_stages (conversation_id, stage_number, stage_name, content, status)
                VALUES (:conv_id, :stage_num, :name, :content, :status)
                RETURNING id INTO :out_id
            """, {
                "conv_id": conversation_id,
                "stage_num": stage_number,
                "name": stage_name,
                "content": content,
                "status": status,
                "out_id": cur.var(int)
            })
            stage_id = cur.getvalue("out_id")
        
        conn.commit()
        return stage_id if stage_id else -1
    except Exception as e:
        print(f"[PROCESSING_STAGES] Error saving stage: {e}")
        conn.rollback()
        return -1
    finally:
        cur.close()
        conn.close()


def get_processing_stages(conversation_id: int) -> list:
    """
    Get all processing stages for a conversation, ordered by stage number.
    Returns list of stage dicts.
    """
    if conversation_id is None or conversation_id < 0:
        return []
    
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT stage_number, stage_name, content, status, created_at
            FROM processing_stages
            WHERE conversation_id = :conv_id
            ORDER BY stage_number ASC
        """, {"conv_id": conversation_id})
        
        rows = cur.fetchall()
        stages = []
        for row in rows:
            # Handle CLOB content
            content = row[2]
            if hasattr(content, 'read'):
                content = content.read()
            
            stages.append({
                "stage": row[0],
                "name": row[1],
                "content": content or "",
                "status": row[3] or "complete",
                "created_at": str(row[4]) if row[4] else None
            })
        
        return stages
    except Exception as e:
        print(f"[PROCESSING_STAGES] Error getting stages: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def clear_processing_stages(conversation_id: int) -> bool:
    """
    Clear all processing stages for a conversation (called when response is finalized).
    Returns True if successful.
    """
    if conversation_id is None or conversation_id < 0:
        return False
    
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            DELETE FROM processing_stages WHERE conversation_id = :conv_id
        """, {"conv_id": conversation_id})
        conn.commit()
        return True
    except Exception as e:
        print(f"[PROCESSING_STAGES] Error clearing stages: {e}")
        conn.rollback()
        return False
    finally:
        cur.close()
        conn.close()


def has_pending_processing(conversation_id: int) -> bool:
    """
    Check if a conversation has pending processing stages (no final response yet).
    Returns True if there are stages with status 'processing'.
    """
    if conversation_id is None or conversation_id < 0:
        return False
    
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT COUNT(*) FROM processing_stages 
            WHERE conversation_id = :conv_id
        """, {"conv_id": conversation_id})
        count = cur.fetchone()[0]
        return count > 0
    except Exception as e:
        print(f"[PROCESSING_STAGES] Error checking pending: {e}")
        return False
    finally:
        cur.close()
        conn.close()
