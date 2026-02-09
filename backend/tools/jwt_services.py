import jwt
from datetime import datetime, timezone, timedelta
import os
from database.db import get_connection
import logging
import cx_Oracle

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")

def decode_token(token):
    try:
        decoded = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return decoded
    except jwt.ExpiredSignatureError:
        raise ValueError("Token kedaluwarsa.")
    except jwt.InvalidTokenError:
        raise ValueError("Token tidak valid.")

def generate_jwt_pair(email: str):
    access_payload = {
        "sub": email,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        "type": "access"
    }
    refresh_payload = {
        "sub": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "type": "refresh"
    }

    access_token = jwt.encode(access_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    refresh_token = jwt.encode(refresh_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    return access_token, refresh_token

def refresh_access_token(refresh_token: str):
    try:
        payload = jwt.decode(refresh_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

        if payload["type"] != "refresh":
            raise ValueError("Token bukan tipe refresh.")

        email = payload["sub"]

        # Validasi refresh token dengan database
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT refresh_token FROM hr_users WHERE email = :email", {"email": email})
        row = cur.fetchone()

        if not row:
            raise ValueError("Token tidak ditemukan di database.")

        db_token = row[0].read() if isinstance(row[0], cx_Oracle.LOB) else row[0]
        if db_token != refresh_token:
            raise ValueError("Refresh token tidak cocok dengan database.")

        cur.close()
        conn.close()
        
        new_access, _ = generate_jwt_pair(email)
        return new_access

    except jwt.ExpiredSignatureError:
        raise ValueError("Refresh token sudah kedaluwarsa.")
    except jwt.InvalidTokenError:
        raise ValueError("Refresh token tidak valid.")
    except Exception as e:
        logging.exception("Gagal me-refresh token")
        raise e

    
def save_tokens(email, access_token, refresh_token):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE hr_users 
            SET jwt_token = :jwt_token, refresh_token = :refresh_token 
            WHERE email = :email
        """, {
            "jwt_token": access_token,
            "refresh_token": refresh_token,
            "email": email
        })
        conn.commit()
    except Exception as e:
        raise RuntimeError(f"Gagal menyimpan token ke database: {e}")
    finally:
        cur.close()
        conn.close()
