# tools/jwt_middleware.py

from functools import wraps
from flask import request, jsonify, g
from tools.jwt_services import decode_token # pastikan decode_token sudah ada

def jwt_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            bearer = request.headers['Authorization']
            token = bearer.split(" ")[1] if " " in bearer else bearer

        if not token:
            return jsonify({"error": "Token tidak ditemukan."}), 401

        try:
            payload = decode_token(token)
            g.email = payload.get('sub')  # ✅ set ke flask.g
        except ValueError as ve:
            return jsonify({"error": str(ve)}), 401

        return f(*args, **kwargs)
    return decorated