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

def save_chat_history_to_oracle(email: str, prompt: str, answer: str):
    try:
        conn = cx_Oracle.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=dsn)
        cur = conn.cursor()

        # Cari user ID berdasarkan email
        cur.execute("SELECT id FROM users WHERE email = :email", {"email": email})
        user = cur.fetchone()

        if not user:
            raise ValueError(f"User dengan email '{email}' tidak ditemukan di database.")

        user_id = user[0]

        # Simpan chat history
        cur.execute("""
            INSERT INTO chat_history (user_id, prompt, answer)
            VALUES (:user_id, :prompt, :answer)
        """, {
            "user_id": user_id,
            "prompt": prompt,
            "answer": answer
        })

        conn.commit()

    except Exception as e:
        print(f"❌ Gagal menyimpan chat history: {e}")
        raise
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass

def save_prompt_only(email: str, prompt: str, is_streamed: bool = False) -> int:
    try:
        conn = cx_Oracle.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=dsn)
        cur = conn.cursor()

        cur.execute("SELECT id FROM users WHERE email = :email", {"email": email})
        user = cur.fetchone()
        if not user:
            raise ValueError(f"User dengan email '{email}' tidak ditemukan.")

        user_id = user[0]
        chat_id_var = cur.var(cx_Oracle.NUMBER)

        cur.execute("""
            INSERT INTO chat_history (user_id, prompt, answer, is_streamed)
            VALUES (:user_id, :prompt, NULL, :is_streamed)
            RETURNING id INTO :chat_id
        """, {
            "user_id": user_id,
            "prompt": prompt,
            "is_streamed": int(is_streamed),
            "chat_id": chat_id_var
        })

        conn.commit()
        return int(chat_id_var.getvalue()[0])

    except Exception as e:
        print(f"❌ Gagal menyimpan prompt: {e}")
        raise
    finally:
        cur.close()
        conn.close()



def update_answer(chat_id: int, answer: str):
    try:
        conn = cx_Oracle.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=dsn)
        cur = conn.cursor()

        cur.execute("""
            UPDATE chat_history SET answer = :answer WHERE id = :chat_id
        """, {"answer": answer, "chat_id": chat_id})
        conn.commit()
    except Exception as e:
        print(f"❌ Gagal update jawaban: {e}")
        raise
    finally:
        cur.close()
        conn.close()


def mark_stream_complete(chat_id: int):
    try:
        conn = cx_Oracle.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=dsn)
        cur = conn.cursor()
        cur.execute("""
            UPDATE chat_history
            SET is_streamed = 1
            WHERE id = :chat_id
        """, {"chat_id": chat_id})
        conn.commit()
    except Exception as e:
        print(f"❌ Gagal update is_streamed: {e}")
        raise
    finally:
        cur.close()
        conn.close()


def get_chat_history_by_email(email: str) -> list[dict]:
    try:
        conn = cx_Oracle.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=dsn)
        cur = conn.cursor()

        # Ambil user_id berdasarkan email
        cur.execute("SELECT id FROM users WHERE email = :email", {"email": email})
        user = cur.fetchone()

        if not user:
            raise ValueError(f"User dengan email '{email}' tidak ditemukan.")

        user_id = user[0]

        # Ambil chat history berdasarkan user_id
        cur.execute("""
            SELECT prompt, answer, created_at, is_streamed
            FROM chat_history
            WHERE user_id = :user_id
            ORDER BY created_at ASC
        """, {"user_id": user_id})

        rows = cur.fetchall()
        columns = [col[0].lower() for col in cur.description]

        chat_history = []
        for row in rows:
            row_dict = dict(zip(columns, row))

            # Konversi LOB ke string
            for key in ["prompt", "answer"]:
                if isinstance(row_dict[key], cx_Oracle.LOB):
                    row_dict[key] = row_dict[key].read()

            # Tambahkan ke list chat (user & bot)
            chat_history.append({"role": "user", "content": row_dict["prompt"]})
            chat_history.append({"role": "assistant", "content": row_dict["answer"]})

        return chat_history

    except Exception as e:
        import logging
        logging.exception("Gagal mengambil chat history")
        raise

    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass


def truncate_chat_history(email: str):
    try:
        conn = cx_Oracle.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=dsn)
        cur = conn.cursor()

        # Ambil user_id berdasarkan email
        cur.execute("SELECT id FROM SMARTBOT.users WHERE email = :email", {"email": email})
        user = cur.fetchone()

        if not user:
            return jsonify({"error": "User tidak ditemukan"}), 404

        user_id = user[0]

        # Hapus chat history berdasarkan user_id
        cur.execute("DELETE FROM SMARTBOT.chat_history WHERE user_id = :user_id", {"user_id": user_id})
        conn.commit()

        cur.close()
        conn.close()

        return jsonify({"message": "Riwayat chat berhasil dihapus"}), 200

    except Exception as e:
        logging.exception("Gagal menghapus chat history")
        return jsonify({"error": "Terjadi kesalahan saat menghapus riwayat chat"}), 500
