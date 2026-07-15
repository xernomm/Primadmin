import nest_asyncio
nest_asyncio.apply()

from flask import Flask, request, jsonify, g
from flask_jwt_extended import get_jwt_identity  # pastikan ini di-import
from flask_cors import CORS
from agent.gemini_client import gemini_generate
import base64, os
import logging
import traceback
from config import BACKEND_DIR, CV_DIR, EXPORTS_DIR, PAYROLL_EXPORTS_DIR, DOCUMENTS_DIR
from database.db import init_db
from users.user_auth import login_user, logout_user, get_user_id_by_email, get_user_by_email
from chats.chat_service import (
    save_user_message,
    save_assistant_message,
    save_chat_history_to_oracle, # still imported if needed
    update_answer, 
    get_chat_history_by_email, 
    truncate_chat_history,
    get_conversations_by_email,
    get_messages_by_conversation_id,
    delete_conversation_by_id,
    update_conversation_title
)
from chats.processing_service import save_processing_stage, get_processing_stages, clear_processing_stages
from LLM.bot import get_context_from_rag, store_chat_history
from agent.core import set_abort as agent_set_abort
from MCP.agent_runner import run_agent
from tools.run_async import run_async
from tools.jwt_services import generate_jwt_pair, save_tokens, refresh_access_token
from tools.jwt_middleware import jwt_required


from flask_socketio import SocketIO, emit

init_db()

app = Flask(__name__)
CORS(app)
# Use threading mode for better Windows compatibility with asyncio
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = os.getenv("JWT_SECRET")

# <----------------------------------------------------APP ROUTER ---------------------------------------------------->
        
@app.route("/api/auth/login", methods=["POST"])
def login():
    try:
        data = request.json
        # Accept either email or username as the identifier
        identifier = data.get("email") or data.get("username")
        password = data.get("password")

        if not identifier or not password:
            return jsonify({"error": "Email/Username dan password wajib diisi."}), 400

        if login_user(identifier, password):
            # Resolve actual email if identifier was username
            from database.db import get_connection
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT email FROM hr_users WHERE email = :id OR username = :id", {"id": identifier})
            row = cur.fetchone()
            actual_email = row[0] if row else identifier
            cur.close()
            conn.close()

            access_token, refresh_token = generate_jwt_pair(actual_email)
            save_tokens(actual_email, access_token, refresh_token)

            user_data = get_user_by_email(actual_email)

            return jsonify({
                "message": "Login berhasil.",
                "access_token": access_token,
                "refresh_token": refresh_token,
                "user": user_data
            }), 200
        else:
            return jsonify({"error": "Email/Username atau password salah."}), 401

    except Exception as e:
        logging.exception("Gagal login")
        return jsonify({"error": "Terjadi kesalahan saat login."}), 500

@app.route("/api/auth/me", methods=["GET"])
@jwt_required
def get_me():
    try:
        email = g.email
        user_data = get_user_by_email(email)
        if not user_data:
            return jsonify({"error": "User tidak ditemukan."}), 404
        return jsonify(user_data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/auth/logout", methods=["POST"])
@jwt_required
def logout():
    try:
        email = g.email
        logout_user(email)
        return jsonify({"message": "Logout berhasil."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/auth/refresh", methods=["POST"])
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
        conversation_id = data.get("conversation_id")  # Optional for continuing conversations
        use_full_pipeline = data.get("full_pipeline", True)  # Default to full pipeline
        email = g.email

        if not user_input:
            return jsonify({"error": "Pertanyaan wajib diisi"}), 400

        user_msg_id, conv_id = save_user_message(email, user_input, conversation_id=conversation_id)

        context = """Your name is Primassistant. You are a professional HR assistant that speaks bahasa Indonesia. 
        You help HR teams manage employee data, attendance, leave balance (stored in employees table), and other HR operations.
        Always be helpful, professional, and accurate in your responses.
        Format data clearly using markdown tables when appropriate."""

        # Run the new agent with full pipeline
        user_id = get_user_id_by_email(email) or 1
        
        result = run_async(run_agent(
            user_input=user_input, 
            context=context,
            user_id=user_id,
            conversation_id=conversation_id,
            use_full_pipeline=use_full_pipeline
        ))

        # Extract response
        if isinstance(result, dict):
            response = result.get("response", "Tidak ada jawaban ditemukan.")
            metadata = result.get("metadata", {})
            tool_results = result.get("tool_results")
            conv_id = result.get("conversation_id")
        else:
            response = str(result)
            metadata = {}
            tool_results = None
            conv_id = None

        if conv_id is None:
             conv_id = user_msg_id # fallback if needed, but conv_id should come from save_user_message

        # Assistant message is saved by HRAgent internally via HistoryManager
        # save_assistant_message(conv_id, response)

        return jsonify({
            "response": response,
            "conversation_id": conv_id,
            "metadata": metadata,
            "tool_results": tool_results
        })
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

        user_msg_id, conv_id = save_user_message(email, user_input)
        context = get_context_from_rag(email, user_input)

        # Gunakan LLM langsung tanpa tools
        response = gemini_generate(
            model="gemini-2.5-flash",
            prompt=f"Gunakan informasi ini:\n{context}\n\nJawablah pertanyaan ini: {user_input}"
        )

        save_assistant_message(conv_id, response)

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

@app.route("/api/conversations", methods=["GET"])
@jwt_required
def list_conversations():
    try:
        email = g.email
        conversations = get_conversations_by_email(email)
        return jsonify(conversations)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/conversations/<int:conversation_id>", methods=["GET"])
@jwt_required
def get_conversation(conversation_id):
    try:
        email = g.email
        messages = get_messages_by_conversation_id(conversation_id, email)
        return jsonify({
            "conversation_id": conversation_id,
            "messages": messages
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/conversations/<int:conversation_id>", methods=["DELETE"])
@jwt_required
def delete_conversation(conversation_id):
    try:
        email = g.email
        success = delete_conversation_by_id(conversation_id, email)
        if success:
            return jsonify({"message": "Percakapan berhasil dihapus"}), 200
        else:
            return jsonify({"error": "Percakapan tidak ditemukan atau bukan milik Anda"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/conversations/<int:conversation_id>/processing_stages", methods=["GET"])
@jwt_required
def get_conversation_processing_stages(conversation_id):
    """Get processing stages for a conversation (used for page refresh recovery)."""
    try:
        stages = get_processing_stages(conversation_id)
        return jsonify({"stages": stages})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# <---------------------------------------------------- POLICIES API ------------------------------------------------------>

@app.route("/api/policies", methods=["GET"])
@jwt_required
def get_policies():
    """Get all policy documents for frontend display."""
    try:
        from pathlib import Path
        
        policies_dir = DOCUMENTS_DIR / "policies"
        policies = []
        
        # Define the order and metadata for policies
        policy_files = [
            {"file": "attendance_policy.md", "title": "Aturan Absensi & Kehadiran", "icon": "clock"},
            {"file": "leave_policy.md", "title": "Kebijakan Cuti Karyawan", "icon": "calendar"},
            {"file": "company_rules.md", "title": "Peraturan Umum Perusahaan", "icon": "book"}
        ]
        
        for policy in policy_files:
            filepath = policies_dir / policy["file"]
            if filepath.exists():
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                policies.append({
                    "id": policy["file"].replace(".md", ""),
                    "title": policy["title"],
                    "icon": policy["icon"],
                    "content": content
                })
        
        return jsonify(policies)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# <---------------------------------------------------- EXPORT DOWNLOADS ---------------------------------------------------->

# Upload CV file
@app.route("/api/upload/cv", methods=["POST"])
@jwt_required
def upload_cv_file():
    """Upload a CV file for an employee.
    
    Form fields:
        file          - The CV file (required)
        employee_id   - Database ID of the employee (optional).
                        If provided, the file is renamed and registered in employee_cv.
                        If omitted, file is saved temporarily and path is returned for
                        the agent to call manage_cv_file manually.
    """
    try:
        from pathlib import Path
        from werkzeug.utils import secure_filename
        
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        # Validate file type
        allowed_extensions = {'.pdf', '.doc', '.docx', '.txt', '.jpg', '.jpeg', '.png'}
        ext = Path(file.filename).suffix.lower()
        if ext not in allowed_extensions:
            return jsonify({"error": f"File type {ext} not allowed"}), 400
        
        # Save to cv uploads directory (temporary name = original filename)
        filename = secure_filename(file.filename)
        filepath = CV_DIR / filename
        file.save(str(filepath))
        
        # If employee_id provided, call manage_cv_file to rename + update DB
        employee_id = request.form.get("employee_id") or request.args.get("employee_id")
        if employee_id:
            try:
                emp_id_int = int(employee_id)
                from MCP.tools.cv_tools import manage_cv_file
                result = manage_cv_file(
                    emp_id=emp_id_int,
                    action="upload",
                    file_path=str(filepath)
                )
                if result.get("success"):
                    # Remove the temp file if it differs from the registered dest
                    registered_path = Path(result.get("file_path", ""))
                    if registered_path != filepath and filepath.exists():
                        try:
                            filepath.unlink()
                        except Exception:
                            pass
                    return jsonify({
                        "success": True,
                        "file_path": result["file_path"],
                        "filename": result["filename"],
                        "download_url": result.get("download_url"),
                        "db_updated": True,
                        "size": registered_path.stat().st_size if registered_path.exists() else None
                    })
                else:
                    # manage_cv_file failed — still return the temp file path
                    return jsonify({
                        "success": True,
                        "file_path": str(filepath),
                        "filename": filename,
                        "db_updated": False,
                        "db_error": result.get("error"),
                        "size": filepath.stat().st_size
                    })
            except (ValueError, TypeError):
                pass  # bad employee_id, fall through to basic response

        # No employee_id — return saved path as dynamic URL for agent to process (with or without domain)
        from config import BASE_URL
        download_url = f"/api/uploads/cv/{filename}"
        full_server_url = f"{BASE_URL}{download_url}"
        
        return jsonify({
            "success": True,
            "file_path": full_server_url,
            "filename": filename,
            "db_updated": False,
            "note": "File disimpan sementara. Kirim employee_id untuk mendaftarkan ke database.",
            "size": filepath.stat().st_size
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/exports/<filename>", methods=["GET"])
@jwt_required
def download_export(filename):
    """Download exported CSV files."""
    try:
        from flask import send_from_directory
        from pathlib import Path
        
        # Validate filename to prevent path traversal
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({"error": "Invalid filename"}), 400
        
        exports_dir = EXPORTS_DIR
        filepath = exports_dir / filename
        
        if not filepath.exists():
            return jsonify({"error": "File tidak ditemukan"}), 404
        
        return send_from_directory(
            exports_dir,
            filename,
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/exports/payroll/<filename>", methods=["GET"])
@jwt_required
def download_payroll_export(filename):
    """Download generated payroll PDF files."""
    try:
        from flask import send_from_directory
        from pathlib import Path
        
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({"error": "Invalid filename"}), 400
        
        payroll_dir = PAYROLL_EXPORTS_DIR
        filepath = payroll_dir / filename
        
        if not filepath.exists():
            return jsonify({"error": "File tidak ditemukan"}), 404
        
        return send_from_directory(
            payroll_dir,
            filename,
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/uploads/cv/<filename>", methods=["GET"])
@jwt_required
def download_cv_file(filename):
    """Download/view uploaded CV files."""
    try:
        from flask import send_from_directory
        from pathlib import Path
        
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({"error": "Invalid filename"}), 400
        
        filepath = CV_DIR / filename
        
        if not filepath.exists():
            return jsonify({"error": "File tidak ditemukan"}), 404
        
        return send_from_directory(
            CV_DIR,
            filename,
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# <---------------------------------------------------- SOCKETIO EVENTS ---------------------------------------------------->


@socketio.on('connect')
def handle_connect():
    logging.info(f"Client connected: {request.sid}")

@socketio.on('abort')
def handle_abort():
    """Client pressed Stop — set abort flag for this session."""
    sid = request.sid
    agent_set_abort(sid)
    print(f"[ABORT] Received abort from socket {sid}")
    emit('status_update', {'status': '⏹ Proses dihentikan.'})

@app.route("/api/abort", methods=["POST"])
@jwt_required
def http_abort():
    """REST fallback to abort the current agent run for a given socket session."""
    sid = request.json.get("session_id") if request.is_json else None
    if sid:
        agent_set_abort(sid)
        return jsonify({"success": True, "message": "Proses dibatalkan."}), 200
    return jsonify({"success": False, "error": "session_id wajib"}), 400

@socketio.on('chat_message')
def handle_chat_message(data):
    try:
        user_input = data.get("message")
        conversation_id = data.get("conversation_id")
        
        # Token verification (logic kept same)
        from tools.jwt_services import decode_token
        token = data.get("token")
        if token:
            payload = decode_token(token)
            email = payload.get("sub")
        else:
            email = "admin@hr.com" 
        
        if not user_input:
            emit('error', {'message': 'Pertanyaan wajib diisi'})
            return

        # Capture SID for targeted emitting
        sid = request.sid

        # 1. Update status immediatey
        emit('status_update', {'status': 'Memulai proses...'})
        
        # Define background task
        def process_chat_in_background(app_context, uid, conv_id, query, user_email, user_sid):
            # Manually push app context for Flask extensions/DB if needed
            with app.app_context(): 
                try:
                    def status_callback(status_msg):
                        # Direct emit - background task runs in greenlet context
                        socketio.emit('status_update', {'status': status_msg}, room=user_sid)
                    
                    def stage_callback(stage_data):
                        # --- RESET event: verification failed, agent retrying ---
                        if stage_data.get("type") == "reset":
                            print(f"[SOCKET] Emitting stage_retry_reset: attempt {stage_data.get('retry_attempt', '?')}")
                            socketio.emit('stage_retry_reset', stage_data, room=user_sid)
                            # Clear persisted stages in DB so retry starts with fresh slate
                            if conv_id and conv_id > 0:
                                clear_processing_stages(conv_id)
                            return
                        # --- Normal stage_complete ---
                        print(f"[SOCKET] Emitting stage_complete: Stage {stage_data.get('stage', '?')}")
                        socketio.emit('stage_complete', stage_data, room=user_sid)
                        # Persist stage to database
                        if conv_id and conv_id > 0:
                            save_processing_stage(
                                conversation_id=conv_id,
                                stage_number=stage_data.get('stage', 0),
                                stage_name=stage_data.get('name', ''),
                                content=stage_data.get('content', ''),
                                status=stage_data.get('status', 'complete')
                            )

                    def sub_status_callback(sub_data):
                        """Forward tool-level sub-status events to frontend."""
                        socketio.emit('sub_status', sub_data, room=user_sid)

                    # Run agent with both callbacks
                    result = run_async(run_agent(
                        user_input=query,
                        context="", 
                        user_id=uid,
                        conversation_id=conv_id,
                        status_callback=status_callback,
                        stage_callback=stage_callback,
                        sub_status_callback=sub_status_callback,
                        session_id=user_sid
                    ))
                    
                    if isinstance(result, dict):
                        final_conv_id = result.get("conversation_id", conv_id)
                        result["conversation_id"] = final_conv_id
                        
                        # NEW: If this was a new conversation (original conv_id was None/0), update title
                        if (not conv_id or conv_id <= 0) and final_conv_id:
                            try:
                                # Create title from prompt + date
                                from datetime import datetime
                                short_prompt = (query[:40] + '...') if len(query) > 40 else query
                                date_str = datetime.now().strftime("%d/%m %H:%M")
                                new_title = f"{short_prompt} ({date_str})"
                                update_conversation_title(final_conv_id, new_title)
                            except Exception as title_err:
                                print(f"[TITLE UPDATE ERROR] {title_err}")
                    
                    # FINAL RESPONSE EMIT - Ensure JSON serializable (handle datetime)
                    import json
                    json_compatible_result = json.loads(json.dumps(result, default=str))
                    socketio.emit('chat_response', json_compatible_result, room=user_sid)
                    
                    # Clear processing stages from DB now that response is complete
                    final_conv_id = result.get("conversation_id") if isinstance(result, dict) else conv_id
                    if final_conv_id and final_conv_id > 0:
                        clear_processing_stages(final_conv_id)
                    
                except Exception as agent_error:
                    logging.exception("Background agent failed")
                    save_assistant_message(conv_id, "Maaf, terjadi kesalahan saat memproses permintaan Anda.")
                    socketio.emit('error', {'message': str(agent_error)}, room=user_sid)

        # Get user ID
        user_id = get_user_id_by_email(email) or 1
        
        # Start background task
        socketio.start_background_task(
            process_chat_in_background, 
            app.app_context(),
            user_id, 
            conversation_id, 
            user_input, 
            email,
            sid
        )
        
    except Exception as e:
        logging.exception("WebSocket chat setup failed")
        emit('error', {'message': str(e)})

if __name__ == "__main__":
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=False,
        allow_unsafe_werkzeug=True
    )
