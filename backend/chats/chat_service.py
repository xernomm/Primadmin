import os
import cx_Oracle
from dotenv import load_dotenv
from flask import jsonify
import logging

load_dotenv()

ORACLE_USER = os.getenv("ORACLE_USER")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD")
ORACLE_HOST = os.getenv("ORACLE_HOST")
ORACLE_PORT = os.getenv("ORACLE_PORT")
ORACLE_SERVICE = os.getenv("ORACLE_SERVICE_NAME")

# Oracle DSN
dsn = cx_Oracle.makedsn(ORACLE_HOST, ORACLE_PORT, service_name=ORACLE_SERVICE)

def get_connection():
    return cx_Oracle.connect(
        user=ORACLE_USER,
        password=ORACLE_PASSWORD,
        dsn=dsn
    )

def save_chat_history_to_oracle(email: str, prompt: str, answer: str):
    """
    Simpan satu set prompt dan answer ke database (Creates new conversation for simplicity or appends to latest active).
    For backward compatibility with simple chat flows, we might create a new message in the latest active conversation,
    or create a new conversation if none exists.
    """
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # Find user ID
        cur.execute("SELECT id FROM hr_users WHERE email = :email", {"email": email})
        user = cur.fetchone()
        if not user:
            raise ValueError(f"User dengan email '{email}' tidak ditemukan di database.")
        user_id = user[0]

        # Find or create active conversation
        # Simplified logic: Get latest active conversation or create new
        cur.execute("""
            SELECT id FROM conversations 
            WHERE user_id = :user_id AND is_active = 1 
            ORDER BY created_at DESC FETCH FIRST 1 ROWS ONLY
        """, {"user_id": user_id})
        conv = cur.fetchone()
        
        if conv:
            conversation_id = conv[0]
        else:
            # Create new conversation
            conv_id_var = cur.var(cx_Oracle.NUMBER)
            cur.execute("""
                INSERT INTO conversations (user_id, title) 
                VALUES (:user_id, 'New Chat') 
                RETURNING id INTO :conv_id
            """, {"user_id": user_id, "conv_id": conv_id_var})
            conversation_id = int(conv_id_var.getvalue()[0])

        # Save User Message
        cur.execute("""
            INSERT INTO messages (conversation_id, role, content)
            VALUES (:conv_id, 'user', :content)
        """, {"conv_id": conversation_id, "content": prompt})

        # Save Assistant Message
        cur.execute("""
            INSERT INTO messages (conversation_id, role, content)
            VALUES (:conv_id, 'assistant', :content)
        """, {"conv_id": conversation_id, "content": answer})

        conn.commit()

    except Exception as e:
        print(f"❌ Gagal menyimpan chat history: {e}")
        if conn: conn.rollback()
        raise
    finally:
        if cur: cur.close()
        if conn: conn.close()

def save_user_message(email: str, prompt: str, conversation_id: int = None) -> tuple[int, int]:
    """
    Saves the user prompt and returns (user_message_id, conversation_id).
    Fixes ORA-01745 by using safe bind variables.
    """
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("SELECT id FROM hr_users WHERE email = :email", {"email": email})
        user = cur.fetchone()
        if not user:
            raise ValueError(f"User dengan email '{email}' tidak ditemukan.")
        user_id = user[0]

        actual_conversation_id = None
        
        if conversation_id:
            # Verify ownership: use :user_id_val instead of :uid to avoid bind var issues
            cur.execute("""
                SELECT id FROM conversations 
                WHERE id = :cid AND user_id = :user_id_val
            """, {"cid": conversation_id, "user_id_val": user_id})
            row = cur.fetchone()
            if row:
                actual_conversation_id = row[0]
        
        if not actual_conversation_id:
            # Find latest active or create new
            cur.execute("""
                SELECT id FROM conversations 
                WHERE user_id = :user_id AND is_active = 1 
                ORDER BY created_at DESC FETCH FIRST 1 ROWS ONLY
            """, {"user_id": user_id})
            conv = cur.fetchone()
            
            if conv:
                actual_conversation_id = conv[0]
            else:
                conv_id_var = cur.var(cx_Oracle.NUMBER)
                cur.execute("""
                    INSERT INTO conversations (user_id, title) 
                    VALUES (:user_id, 'New Chat') 
                    RETURNING id INTO :conv_id
                """, {"user_id": user_id, "conv_id": conv_id_var})
                actual_conversation_id = int(conv_id_var.getvalue()[0])

        # Save User Message ONLY
        msg_id_var = cur.var(cx_Oracle.NUMBER)
        cur.execute("""
            INSERT INTO messages (conversation_id, role, content)
            VALUES (:conv_id, 'user', :content)
            RETURNING id INTO :msg_id
        """, {"conv_id": actual_conversation_id, "content": prompt, "msg_id": msg_id_var})
        
        conn.commit()
        return int(msg_id_var.getvalue()[0]), actual_conversation_id

    except Exception as e:
        print(f"❌ Gagal menyimpan pesan user: {e}")
        if conn: conn.rollback()
        raise
    finally:
        if cur: cur.close()
        if conn: conn.close()

def save_assistant_message(conversation_id: int, content: str) -> int:
    """
    Saves the assistant's response to the database.
    """
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        msg_id_var = cur.var(cx_Oracle.NUMBER)
        cur.execute("""
            INSERT INTO messages (conversation_id, role, content)
            VALUES (:conv_id, 'assistant', :content)
            RETURNING id INTO :msg_id
        """, {"conv_id": conversation_id, "content": content, "msg_id": msg_id_var})
        
        conn.commit()
        return int(msg_id_var.getvalue()[0])

    except Exception as e:
        print(f"❌ Gagal menyimpan pesan assistant: {e}")
        if conn: conn.rollback()
        raise
    finally:
        if cur: cur.close()
        if conn: conn.close()

def update_answer(chat_id: int, answer: str):
    """
    Updates the content of a specific message ID (previously chat_id).
    """
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            UPDATE messages SET content = :answer WHERE id = :msg_id
        """, {"answer": answer, "msg_id": chat_id})
        conn.commit()
    except Exception as e:
        print(f"❌ Gagal update jawaban: {e}")
        if conn: conn.rollback()
        raise
    finally:
        if cur: cur.close()
        if conn: conn.close()


def update_conversation_title(conversation_id: int, title: str):
    """
    Update the title of a conversation.
    """
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("UPDATE conversations SET title = :title WHERE id = :conv_id", 
                   {"title": title, "conv_id": conversation_id})
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Gagal update title: {e}")
        if conn: conn.rollback()
        return False
    finally:
        if cur: cur.close()
        if conn: conn.close()


def mark_stream_complete(chat_id: int):
    """
    No-op for now unless we add specific status field to messages. 
    Or we can just commit if needed.
    """
    # In new schema, existence of content implies complete for basic usage.
    pass


def get_chat_history_by_email(email: str) -> list[dict]:
    """
    Retrieves full history for the user, flattening conversations.
    """
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("SELECT id FROM hr_users WHERE email = :email", {"email": email})
        user = cur.fetchone()
        if not user:
            raise ValueError(f"User dengan email '{email}' tidak ditemukan.")
        user_id = user[0]

        # Join conversations and messages
        cur.execute("""
            SELECT m.role, m.content, m.created_at
            FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            WHERE c.user_id = :user_id
            ORDER BY m.created_at ASC
        """, {"user_id": user_id})

        rows = cur.fetchall()
        
        chat_history = []
        for row in rows:
            role = row[0]
            content = row[1]
            if isinstance(content, cx_Oracle.LOB):
                content = content.read()
                
            chat_history.append({"role": role, "content": content})

        return chat_history

    except Exception as e:
        logging.exception("Gagal mengambil chat history")
        raise

    finally:
        if cur: cur.close()
        if conn: conn.close()


def truncate_chat_history(email: str):
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("SELECT id FROM hr_users WHERE email = :email", {"email": email})
        user = cur.fetchone()

        if not user:
            return jsonify({"error": "User tidak ditemukan"}), 404

        user_id = user[0]

        # Cascading delete on conversations will delete messages
        cur.execute("DELETE FROM conversations WHERE user_id = :user_id", {"user_id": user_id})
        conn.commit()

        return jsonify({"message": "Riwayat chat berhasil dihapus"}), 200

    except Exception as e:
        logging.exception("Gagal menghapus chat history")
        return jsonify({"error": "Terjadi kesalahan saat menghapus riwayat chat"}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

def get_conversations_by_email(email: str) -> list[dict]:
    """
    Mengambil daftar percakapan milik user.
    """
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("SELECT id FROM hr_users WHERE email = :email", {"email": email})
        user = cur.fetchone()
        if not user:
            return []
        user_id = user[0]

        cur.execute("""
            SELECT id, title, is_active, created_at, updated_at
            FROM conversations
            WHERE user_id = :user_id
            ORDER BY updated_at DESC
        """, {"user_id": user_id})

        rows = cur.fetchall()
        conversations = []
        for row in rows:
            conversations.append({
                "id": row[0],
                "title": row[1],
                "is_active": bool(row[2]),
                "created_at": row[3].isoformat() if row[3] else None,
                "updated_at": row[4].isoformat() if row[4] else None
            })
        return conversations
    finally:
        if cur: cur.close()
        if conn: conn.close()

def get_messages_by_conversation_id(conversation_id: int, email: str) -> list[dict]:
    """
    Mengambil pesan-pesan dari percakapan tertentu, memastikan user adalah pemiliknya.
    """
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # Check ownership
        cur.execute("""
            SELECT c.id 
            FROM conversations c
            JOIN hr_users u ON c.user_id = u.id
            WHERE c.id = :conv_id AND u.email = :email
        """, {"conv_id": conversation_id, "email": email})
        
        if not cur.fetchone():
            return []

        cur.execute("""
            SELECT role, content, token_count, tool_calls, message_metadata, created_at, id
            FROM messages
            WHERE conversation_id = :conv_id
            ORDER BY created_at ASC
        """, {"conv_id": conversation_id})

        rows = cur.fetchall()
        messages = []
        for row in rows:
            content = row[1]
            if isinstance(content, cx_Oracle.LOB):
                content = content.read()
            
            tool_calls = row[3]
            if isinstance(tool_calls, cx_Oracle.LOB):
                tool_calls = tool_calls.read()
            
            metadata = row[4]
            if isinstance(metadata, cx_Oracle.LOB):
                metadata = metadata.read()

            import json
            messages.append({
                "id": row[6],
                "role": row[0],
                "content": content,
                "token_count": row[2],
                "tool_calls": json.loads(tool_calls) if tool_calls else None,
                "metadata": json.loads(metadata) if metadata else None,
                "created_at": row[5].isoformat() if row[5] else None
            })
        return messages
    finally:
        if cur: cur.close()
        if conn: conn.close()

def delete_conversation_by_id(conversation_id: int, email: str) -> bool:
    """
    Menghapus percakapan jika user adalah pemiliknya.
    """
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        # Check ownership and delete
        cur.execute("""
            DELETE FROM conversations 
            WHERE id = :conv_id AND user_id = (SELECT id FROM hr_users WHERE email = :email)
        """, {"conv_id": conversation_id, "email": email})
        
        conn.commit()
        return cur.rowcount > 0
    finally:
        if cur: cur.close()
        if conn: conn.close()


def get_recent_history(conversation_id: int, limit: int = 3) -> list[dict]:
    """
    Mengambil N pesan terakhir dari sebuah conversation untuk context window.
    Digunakan oleh agent agar LLM memahami konteks percakapan sebelumnya.
    
    Args:
        conversation_id: ID percakapan
        limit: Jumlah pesan yang diambil (default 3)
        
    Returns:
        List of dicts dengan 'role' dan 'content'
    """
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # Get last N messages, ordered by created_at DESC, then reverse
        cur.execute("""
            SELECT role, content FROM (
                SELECT role, content, created_at
                FROM messages
                WHERE conversation_id = :conv_id
                ORDER BY created_at DESC
                FETCH FIRST :limit ROWS ONLY
            ) ORDER BY created_at ASC
        """, {"conv_id": conversation_id, "limit": limit})
        
        rows = cur.fetchall()
        history = []
        for row in rows:
            content = row[1]
            if isinstance(content, cx_Oracle.LOB):
                content = content.read()
            history.append({"role": row[0], "content": content})
        
        return history
        
    except Exception as e:
        logging.exception("Failed to get recent history")
        return []
    finally:
        if cur: cur.close()
        if conn: conn.close()


