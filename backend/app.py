import nest_asyncio
nest_asyncio.apply()

from flask import Flask, request, jsonify, g
from flask_jwt_extended import get_jwt_identity  # pastikan ini di-import
from flask_cors import CORS
import ollama
import base64, os
import logging
import traceback
from database.db import init_db
from chats.chat_service import save_prompt_only, update_answer, get_chat_history_by_email, truncate_chat_history
from users.user_auth import login_user, logout_user
from LLM.bot import get_context_from_rag, store_chat_history
from MCP.agent_runner import run_agent
from tools.run_async import run_async
from tools.jwt_services import generate_jwt_pair, save_tokens, refresh_access_token
from tools.jwt_middleware import jwt_required


init_db()

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = os.getenv("JWT_SECRET")

# <----------------------------------------------------APP ROUTER ---------------------------------------------------->
        
@app.route("/api/login", methods=["POST"])
def login():
    try:
        data = request.json
        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            return jsonify({"error": "Email dan password wajib diisi."}), 400

        if login_user(email, password):
            access_token, refresh_token = generate_jwt_pair(email)
            save_tokens(email, access_token, refresh_token)

            return jsonify({
                "message": "Login berhasil.",
                "access_token": access_token,
                "refresh_token": refresh_token
            }), 200
        else:
            return jsonify({"error": "Email atau password salah."}), 401

    except Exception as e:
        logging.exception("Gagal login")
        return jsonify({"error": "Terjadi kesalahan saat login."}), 500

@app.route("/api/logout", methods=["POST"])
@jwt_required
def logout():
    try:
        email = g.email
        logout_user(email)
        return jsonify({"message": "Logout berhasil."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/refresh", methods=["POST"])
def refresh_token():
    try:
        data = request.json
        refresh_token = data.get("refresh_token")

        if not refresh_token:
            return jsonify({"error": "Refresh token wajib diisi."}), 400

        new_access = refresh_access_token(refresh_token)
        return jsonify({"access_token": new_access}), 200

    except ValueError as ve:
        return jsonify({"error": str(ve)}), 401
    except Exception:
        return jsonify({"error": "Terjadi kesalahan saat me-refresh token."}), 500

@app.route("/ask", methods=["POST"])
@jwt_required
def ask_with_tool():
    try:
        data = request.json
        user_input = data.get("question")
        email = g.email

        if not user_input:
            return jsonify({"error": "Pertanyaan wajib diisi"}), 400

        chat_id = save_prompt_only(email, user_input, is_streamed=False)

        context = """ Your name is Primassistant. You are a professional assistant that speaks bahasa Indonesia. Think and analyze carefully about the prompt. Show your thinking process in detail and in dot points. The feedback from the tool call is the data that is returned by the tool after it has been called. This data can be in the form of table or json, your job is to show the data in the form of a markdown and add a conclusion that describes the data. Just re-show the data in a markdown table.
        """

        response = run_async(run_agent(user_input=user_input, context=context))

        update_answer(chat_id, response)
        store_chat_history(email, user_input, response)

        return jsonify({"response": response})
    except Exception as e:
        return jsonify({
            "error": str(e),
            "trace": traceback.format_exc()
        }), 500


@app.route("/ask-rag", methods=["POST"])
@jwt_required
def ask_context_only():
    try:
        data = request.json
        user_input = data.get("question")
        email = g.email

        if not user_input:
            return jsonify({"error": "Pertanyaan wajib diisi"}), 400

        chat_id = save_prompt_only(email, user_input, is_streamed=False)
        context = get_context_from_rag(email, user_input)

        # Gunakan LLM langsung tanpa tools
        response = ollama.generate(
            model="llama3",
            prompt=f"Gunakan informasi ini:\n{context}\n\nJawablah pertanyaan ini: {user_input}"
        )["response"]

        update_answer(chat_id, response)
        store_chat_history(email, user_input, response)

        return jsonify({"response": response})
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500
    

@app.route("/chat-history", methods=["GET"])
@jwt_required
def chat_history():
    try:
        email = g.email  # dari token
        if not email:
            return jsonify({"error": "email wajib diisi"}), 400
        history = get_chat_history_by_email(email)
        return jsonify({"chat_history": history})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/truncate-chat-history', methods=['POST'])
@jwt_required
def handle_truncate_chat():
    email = g.email  # dari JWT middleware
    return truncate_chat_history(email)


if __name__ == "__main__":
    app.run(port=5001)
