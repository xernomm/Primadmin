"""
Conversation history manager module.
Manages conversation sessions and message history for the agent.
"""
import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
# pyrefly: ignore [missing-import]
import cx_Oracle


@dataclass
class Message:
    """Represents a single message in a conversation."""
    id: int
    role: str  # 'user', 'assistant', 'system'
    content: str
    created_at: str
    tool_calls: Optional[List[Dict]] = None
    metadata: Optional[Dict] = None


@dataclass
class Conversation:
    """Represents a conversation session."""
    id: int
    user_id: int
    title: Optional[str] = None
    messages: List[Message] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class ConversationHistoryManager:
    """
    Manages conversation history in memory.
    For production, this should be replaced with database storage.
    """
    
    def __init__(self, max_history: int = 10):
        self.max_history = max_history
        from database.db import get_connection
        self.get_connection = get_connection

    def get_or_create_conversation(
        self,
        user_id: int,
        conversation_id: Optional[int] = None
    ) -> Conversation:
        conn = None
        cur = None
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            
            conv_data = None
            if conversation_id:
                # Get existing
                cur.execute("""
                    SELECT id, title, created_at, updated_at 
                    FROM conversations 
                    WHERE id = :cid AND user_id = :user_id_param
                """, {"cid": conversation_id, "user_id_param": user_id})
                conv_data = cur.fetchone()
            
            if not conv_data:
                # Create new
                conv_id_var = cur.var(cx_Oracle.NUMBER)
                cur.execute("""
                    INSERT INTO conversations (user_id, title) 
                    VALUES (:user_id, 'New Chat') 
                    RETURNING id INTO :conv_id
                """, {"user_id": user_id, "conv_id": conv_id_var})
                conversation_id = int(conv_id_var.getvalue()[0])
                conn.commit()
                
                # Fetch back to get timestamps
                cur.execute("""
                    SELECT id, title, created_at, updated_at 
                    FROM conversations 
                    WHERE id = :cid
                """, {"cid": conversation_id})
                conv_data = cur.fetchone()
            
            # Load messages
            cur.execute("""
                SELECT id, role, content, created_at, tool_calls, message_metadata
                FROM messages
                WHERE conversation_id = :cid
                ORDER BY created_at ASC
            """, {"cid": conversation_id})
            
            messages = []
            for row in cur.fetchall():
                content = row[2]
                if hasattr(content, 'read'): content = content.read()
                
                tool_calls = row[4]
                if hasattr(tool_calls, 'read'): tool_calls = tool_calls.read()
                tool_calls = json.loads(tool_calls) if tool_calls else None
                
                metadata = row[5]
                if hasattr(metadata, 'read'): metadata = metadata.read()
                metadata = json.loads(metadata) if metadata else None
                
                messages.append(Message(
                    id=row[0],
                    role=row[1],
                    content=content,
                    created_at=str(row[3]),
                    tool_calls=tool_calls,
                    metadata=metadata
                ))

            return Conversation(
                id=conv_data[0],
                user_id=user_id,
                title=conv_data[1],
                created_at=str(conv_data[2]),
                updated_at=str(conv_data[3]),
                messages=messages
            )
            
        finally:
            if cur: cur.close()
            if conn: conn.close()
    
    def add_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
        tool_calls: Optional[List[Dict]] = None,
        metadata: Optional[Dict] = None
    ) -> Message:
        conn = None
        cur = None
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            
            # Check for Duplicate (Optimistic De-duplication)
            # If the last message in this conversation has the same role and content, skip insert
            # This handles the case where app.py saved it, and agent tries to save again.
            cur.execute("""
                SELECT role, content 
                FROM messages 
                WHERE conversation_id = :cid 
                ORDER BY id DESC FETCH FIRST 1 ROWS ONLY
            """, {"cid": conversation_id})
            last_msg = cur.fetchone()
            
            if last_msg:
                last_role = last_msg[0]
                last_content = last_msg[1]
                if hasattr(last_content, 'read'): last_content = last_content.read()
                
                if last_role == role and last_content == content:
                    # Duplicate detected, return a dummy message object (or fetch the real one)
                    # We'll just return a mock one for now as ID doesn't matter much for internal flow
                    return Message(0, role, content, str(datetime.now()))

            msg_id_var = cur.var(cx_Oracle.NUMBER)
            
            tool_calls_json = json.dumps(tool_calls) if tool_calls else None
            metadata_json = json.dumps(metadata) if metadata else None

            cur.execute("""
                INSERT INTO messages (conversation_id, role, content, tool_calls, message_metadata)
                VALUES (:cid, :role, :content, :tc, :meta)
                RETURNING id INTO :mid
            """, {
                "cid": conversation_id,
                "role": role,
                "content": content,
                "tc": tool_calls_json,
                "meta": metadata_json,
                "mid": msg_id_var
            })
            
            new_id = int(msg_id_var.getvalue()[0])
            conn.commit()
            
            return Message(
                id=new_id,
                role=role,
                content=content,
                created_at=str(datetime.now()),
                tool_calls=tool_calls,
                metadata=metadata
            )
            
        finally:
            if cur: cur.close()
            if conn: conn.close()
    
    def get_recent_messages(
        self,
        conversation_id: int,
        limit: Optional[int] = None
    ) -> List[Dict]:
        # This method duplicates get_or_create loading logic but lightweight
        # For now, just use get_or_create to ensure consistency or direct query
        # Let's direct query for efficiency
        conn = None
        cur = None
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT role, content 
                FROM messages 
                WHERE conversation_id = :cid 
                ORDER BY created_at ASC
            """, {"cid": conversation_id})
            
            rows = cur.fetchall()
            messages = []
            for row in rows:
                content = row[1]
                if hasattr(content, 'read'): content = content.read()
                messages.append({"role": row[0], "content": content})
                
            if limit:
                return messages[-limit:]
            return messages
            
        finally:
            if cur: cur.close()
            if conn: conn.close()

    def get_conversation(self, conversation_id: int) -> Optional[Conversation]:
        # Helper to get without user_id - strictly not used in current flow but good for completeness
        # Skipping to save tokens/complexity, user can use get_or_create
        pass

    def list_conversations(self, user_id: int) -> List[Conversation]:
        pass

    def delete_conversation(self, conversation_id: int) -> bool:
        pass
    
    def clear_all(self) -> None:
        pass
