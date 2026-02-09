import os
import cx_Oracle
import bcrypt
from dotenv import load_dotenv
import logging
from database.db import get_connection

load_dotenv()

ORACLE_USER = os.getenv("ORACLE_USER")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD")
ORACLE_HOST = os.getenv("ORACLE_HOST")
ORACLE_PORT = os.getenv("ORACLE_PORT")
ORACLE_SERVICE = os.getenv("ORACLE_SERVICE_NAME")

# Oracle DSN
dsn = cx_Oracle.makedsn(ORACLE_HOST, ORACLE_PORT, service_name=ORACLE_SERVICE)

def login_user(identifier: str, password: str) -> bool:
    try:
        conn = get_connection()
        cur = conn.cursor()
        # Mendukung login via Email ATAU Username
        cur.execute("""
            SELECT password_hash FROM hr_users 
            WHERE email = :id OR username = :id
        """, {"id": identifier})
        row = cur.fetchone()

        if not row:
            return False

        hashed_password = row[0]
        return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))

    except Exception as e:
        logging.exception("Gagal login user")
        return False

    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass

def logout_user(email: str):
    """
    Menghapus JWT dan refresh token dari database untuk logout.
    """
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE hr_users 
            SET jwt_token = NULL, refresh_token = NULL 
            WHERE email = :email
        """, {"email": email})
        conn.commit()
    except Exception as e:
        raise RuntimeError(f"Gagal logout: {e}")
    finally:
        cur.close()
        conn.close()

def get_user_id_by_email(email: str) -> int:
    """
    Mengambil ID user berdasarkan email dari tabel hr_users.
    """
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM hr_users WHERE email = :email", {"email": email})
        row = cur.fetchone()
        return row[0] if row else None
    except Exception:
        logging.exception("Gagal mengambil user_id by email")
        return None
    finally:
        cur.close()
        conn.close()

def get_user_by_email(email: str) -> dict:
    """
    Mengambil data lengkap user berdasarkan email.
    """
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, username, email, full_name, role, is_active 
            FROM hr_users WHERE email = :email
        """, {"email": email})
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "username": row[1],
            "email": row[2],
            "full_name": row[3],
            "role": row[4],
            "is_active": bool(row[5])
        }
    except Exception:
        logging.exception("Gagal mengambil data user by email")
        return None
    finally:
        cur.close()
        conn.close()
