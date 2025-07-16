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

def login_user(email: str, password: str) -> bool:
    try:
        conn = cx_Oracle.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=dsn)
        cur = conn.cursor()
        cur.execute("SELECT password FROM SMARTBOT.users WHERE email = :email", {"email": email})
        row = cur.fetchone()

        if not row:
            return False  # Email tidak ditemukan

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
            UPDATE SMARTBOT.users 
            SET jwt_token = NULL, refresh_token = NULL 
            WHERE email = :email
        """, {"email": email})
        conn.commit()
    except Exception as e:
        raise RuntimeError(f"Gagal logout: {e}")
    finally:
        cur.close()
        conn.close()
