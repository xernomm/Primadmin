"""
Email tools for HR Agent.
Handles sending warning letters (SP1/SP2/SP3) and broadcast emails.
Uses SMTP for sending emails with HTML templates.
"""
import os
import smtplib
import traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import mimetypes
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import cx_Oracle
from agent.gemini_client import gemini_chat
from dotenv import load_dotenv

load_dotenv()

# SMTP Configuration from .env
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL")

# Oracle Configuration
ORACLE_USER = os.getenv("ORACLE_USER")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD")
ORACLE_HOST = os.getenv("ORACLE_HOST")
ORACLE_PORT = os.getenv("ORACLE_PORT")
ORACLE_SERVICE = os.getenv("ORACLE_SERVICE_NAME")

dsn = cx_Oracle.makedsn(ORACLE_HOST, ORACLE_PORT, service_name=ORACLE_SERVICE)

# Template directory — import from centralized config
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config import EMAIL_TEMPLATES_DIR as TEMPLATE_DIR, url_to_abs_path, TEMP_UPLOADS_DIR, EXPORTS_DIR, PAYROLL_EXPORTS_DIR, BACKEND_DIR


def _sanitize_email(email: str) -> str:
    """Sanitize email address string."""
    if not email:
        return ""
    # Remove whitespace, quotes, and trailing dots
    clean = email.strip().replace("'", "").replace('"', "")
    if clean.endswith("."):
        clean = clean[:-1]
    return clean


def _get_connection():
    """Get Oracle database connection."""
    return cx_Oracle.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=dsn)



def _send_email(to_email: str, subject: str, html_content: str, attachments: Optional[list] = None) -> bool:
    """
    Send email via SMTP with optional attachments.
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        html_content: HTML body content
        attachments: List of Path objects to attach
        
    Returns:
        True if successful, False otherwise
    """
    try:
        clean_email = _sanitize_email(to_email)
        if not clean_email:
            print("[EMAIL ERROR] Invalid email address (empty after sanitization)")
            return False
            
        if attachments:
            msg = MIMEMultipart("mixed")
            msg["Subject"] = subject
            msg["From"] = SMTP_FROM_EMAIL
            msg["To"] = clean_email
            
            # Create alternative body part for HTML rendering
            body_part = MIMEMultipart("alternative")
            html_part = MIMEText(html_content, "html")
            body_part.attach(html_part)
            msg.attach(body_part)
            
            # Attach files
            for path in attachments:
                if not path.exists() or not path.is_file():
                    print(f"[EMAIL WARNING] Attachment file not found or is not a file: {path}")
                    continue
                
                filename = path.name
                ctype, encoding = mimetypes.guess_type(str(path))
                if ctype is None or encoding is not None:
                    ctype = "application/octet-stream"
                maintype, subtype = ctype.split("/", 1)
                
                try:
                    with open(path, "rb") as fp:
                        part = MIMEBase(maintype, subtype)
                        part.set_payload(fp.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        "attachment",
                        filename=filename
                    )
                    msg.attach(part)
                    print(f"[EMAIL INFO] Attached file to email: {filename}")
                except Exception as att_err:
                    print(f"[EMAIL ERROR] Failed to attach file {filename}: {att_err}")
        else:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = SMTP_FROM_EMAIL
            msg["To"] = clean_email
            
            html_part = MIMEText(html_content, "html")
            msg.attach(html_part)
            
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM_EMAIL, clean_email, msg.as_string())
        
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send email to {to_email}: {e}")
        return False


def _load_template(template_name: str) -> str:
    """Load HTML email template."""
    template_path = TEMPLATE_DIR / template_name
    if template_path.exists():
        return template_path.read_text(encoding="utf-8")
    return ""


def _resolve_attachments(attachments: Optional[Any]) -> list[Path]:
    """
    Resolve various input formats of attachments into a list of absolute Path objects.
    
    Args:
        attachments: Can be a single string (URL, absolute path, relative path, or filename)
                     or a list of such strings.
                     
    Returns:
        List of Path objects that exist on the filesystem.
    """
    if not attachments:
        return []
        
    if isinstance(attachments, str):
        import json
        stripped = attachments.strip()
        if (stripped.startswith("[") and stripped.endswith("]")) or (stripped.startswith("{") and stripped.endswith("}")):
            try:
                parsed = json.loads(attachments)
                if isinstance(parsed, list):
                    att_list = [str(x) for x in parsed]
                elif isinstance(parsed, dict):
                    att_list = [str(v) for v in parsed.values()]
                else:
                    att_list = [str(parsed)]
            except Exception:
                att_list = [attachments]
        else:
            att_list = [attachments]
    elif isinstance(attachments, list):
        att_list = [str(x) for x in attachments]
    else:
        try:
            att_list = [str(x) for x in attachments]
        except Exception:
            att_list = [str(attachments)]
            
    resolved = []
    
    for att in att_list:
        if not att:
            continue
            
        att = att.strip()
        path_obj = None
        
        # 1. Resolve HTTP/HTTPS URL
        if att.startswith("http://") or att.startswith("https://"):
            try:
                path_obj = url_to_abs_path(att)
                if path_obj:
                    print(f"[RESOLVE ATTACHMENT] URL resolved to path: {path_obj}")
            except Exception as e:
                print(f"[RESOLVE ATTACHMENT] Failed resolving URL {att}: {e}")
                
        # 2. Treat as absolute path
        if not path_obj:
            try:
                temp_path = Path(att)
                if temp_path.is_absolute():
                    path_obj = temp_path
            except Exception:
                pass
                
        # 3. Resolve relative to BACKEND_DIR
        if not path_obj:
            try:
                temp_path = BACKEND_DIR / att
                if temp_path.exists() and temp_path.is_file():
                    path_obj = temp_path
            except Exception:
                pass
                
        # 4. Resolve relative to Project Root (BACKEND_DIR.parent)
        if not path_obj:
            try:
                temp_path = BACKEND_DIR.parent / att
                if temp_path.exists() and temp_path.is_file():
                    path_obj = temp_path
            except Exception:
                pass
                
        # 5. Check in TEMP_UPLOADS_DIR
        if not path_obj:
            try:
                fname = Path(att).name
                temp_path = TEMP_UPLOADS_DIR / fname
                if temp_path.exists() and temp_path.is_file():
                    path_obj = temp_path
            except Exception:
                pass
                
        # 6. Check in EXPORTS_DIR / PAYROLL_EXPORTS_DIR
        if not path_obj:
            try:
                fname = Path(att).name
                temp_path = EXPORTS_DIR / fname
                if temp_path.exists() and temp_path.is_file():
                    path_obj = temp_path
                else:
                    temp_path = PAYROLL_EXPORTS_DIR / fname
                    if temp_path.exists() and temp_path.is_file():
                        path_obj = temp_path
            except Exception:
                pass

        # 7. Final fallback: just try Path(att) directly
        if not path_obj:
            try:
                temp_path = Path(att)
                if temp_path.exists() and temp_path.is_file():
                    path_obj = temp_path
            except Exception:
                pass
                
        if path_obj and path_obj.exists() and path_obj.is_file():
            resolved.append(path_obj)
            print(f"[RESOLVE ATTACHMENT] Successfully resolved: {att} -> {path_obj}")
        else:
            print(f"[RESOLVE ATTACHMENT WARNING] Could not resolve or find file: {att}")
            
    return resolved


def _auto_polish_content(recipient_name: str, original_subject: str, original_message: str) -> tuple[str, str]:
    """
    Polishes an email subject and body into professional Indonesian HR standard using Gemini.
    """
    if not original_message:
        return original_subject, original_message
        
    try:
        polish_prompt = f"""
Tugas Anda adalah memoles subjek dan pesan email HR agar terdengar sangat profesional, sopan, dan formal dalam Bahasa Indonesia (menggunakan sapaan yang sesuai seperti Bapak/Ibu/Saudara).

Informasi Email Awal:
- Penerima: {recipient_name}
- Subjek Awal: {original_subject}
- Pesan Awal: {original_message}

Instruksi Pemolesan:
1. Ubah bahasa yang informal, santai, atau terlalu singkat menjadi bahasa HR yang formal, terstruktur, santun, dan profesional.
2. JANGAN mengubah esensi pesan, dan JANGAN menghilangkan informasi penting seperti nama, tanggal, angka, tautan, nama file, atau instruksi utama yang ada di Pesan Awal.
3. Jika Subjek Awal terlalu pendek atau kurang profesional, buat subjek baru yang lebih formal dan jelas menggambarkan isi email.
4. Gunakan gaya penulisan HR profesional Indonesia dengan struktur pembuka yang hormat, isi yang jelas dan tertata (gunakan bullet points bila membantu), serta penutup yang profesional.
5. Kembalikan hasilnya dalam format JSON murni dengan key "subject" dan "message":
{{
  "subject": "Subjek email hasil pemolesan",
  "message": "Pesan email hasil pemolesan (plain text, gunakan \\n untuk baris baru)"
}}
"""
        content = gemini_chat(
            model="gemini-2.5-flash",
            messages=[{"role": "user", "content": polish_prompt}],
            temperature=0.3,
            response_mime_type="application/json"
        )
        
        import json
        import re
        
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            polished_subject = data.get("subject", original_subject)
            polished_message = data.get("message", original_message)
            return polished_subject, polished_message
    except Exception as e:
        print(f"[EMAIL WARNING] Failed to auto-polish content, using original: {e}")
    
    return original_subject, original_message


def send_warning_letter(emp_id: int, reason: Optional[str] = "", issued_by: int = 1, attachments: Optional[Any] = None) -> Dict[str, Any]:
    """
    Kirim Surat Peringatan (SP) ke karyawan dan increment level SP dengan opsional lampiran.
    
    SP = Surat Peringatan (Warning Letter):
    - SP1 = Peringatan Pertama (First Warning)
    - SP2 = Peringatan Kedua (Second Warning)  
    - SP3 = Peringatan Terakhir (Final Warning, before termination)
    
    Args:
        emp_id: Database ID karyawan (dari search_employees)
        reason: Alasan pemberian SP
        issued_by: ID HR user yang mengeluarkan SP (default: 1)
        attachments: File tunggal atau list file pendukung untuk dilampirkan
        
    Returns:
        Dict dengan status kesuksesan, level SP baru, dan pesan
    """
    reason = reason or ""
    conn = None
    try:
        conn = _get_connection()
        cur = conn.cursor()
        
        # Get employee data and current sp_level
        cur.execute("""
            SELECT id, name, email, employee_code, sp_level 
            FROM employees 
            WHERE id = :emp_id
        """, {"emp_id": emp_id})
        row = cur.fetchone()
        
        if not row:
            cur.close()
            conn.close()
            return {"success": False, "error": f"Karyawan dengan ID {emp_id} tidak ditemukan."}
        
        emp_id_db, emp_name, emp_email, emp_code, current_sp = row
        current_sp = current_sp or 0
        
        # Check if already at max level
        if current_sp >= 3:
            cur.close()
            conn.close()
            return {
                "success": False,
                "error": f"Karyawan {emp_name} sudah mencapai level SP3 (Peringatan Terakhir). Tidak dapat mengirimkan SP lebih lanjut. Disarankan untuk memproses PHK sesuai prosedur perusahaan.",
                "sp_level": current_sp
            }
        
        # Calculate new SP level (max 3)
        new_sp_level = current_sp + 1
        sp_type = f"SP{new_sp_level}"
        
        # Get issuer name
        cur.execute("SELECT full_name FROM hr_users WHERE id = :user_id", {"user_id": issued_by})
        issuer_row = cur.fetchone()
        issuer_name = issuer_row[0] if issuer_row else "HR Department"
        
        # Load appropriate template
        template_file = f"sp{new_sp_level}.html"
        template = _load_template(template_file)
        
        if not template:
            cur.close()
            conn.close()
            return {"success": False, "error": f"Template {template_file} tidak ditemukan."}
        
        # Format template with data
        issued_date = datetime.now().strftime("%d %B %Y")
        html_content = template.format(
            employee_name=emp_name,
            employee_code=emp_code,
            reason=reason,
            issued_date=issued_date,
            issuer_name=issuer_name
        )
        
        # 1. Update DB first
        # Update employee sp_level
        cur.execute("""
            UPDATE employees 
            SET sp_level = :sp_level, updated_at = CURRENT_TIMESTAMP
            WHERE id = :emp_id
        """, {"sp_level": new_sp_level, "emp_id": emp_id})
        
        # Record in warnings table (initially with email_sent=0)
        cur.execute("""
            INSERT INTO warnings (employee_id, warning_type, reason, issued_date, issued_by, email_sent, email_sent_at)
            VALUES (:emp_id, :w_type, :reason, TRUNC(SYSDATE), :issued_by, 0, NULL)
        """, {
            "emp_id": emp_id,
            "w_type": sp_type,
            "reason": reason,
            "issued_by": issued_by
        })
        
        # 2. Commit DB changes FIRST — data is now safe regardless of email outcome
        conn.commit()
        
        # Resolve attachments
        resolved_attachments = _resolve_attachments(attachments)
        
        # 3. Attempt to send email
        subject = f"Surat Peringatan {new_sp_level} ({sp_type}) - {emp_name}"
        email_sent = _send_email(emp_email, subject, html_content, resolved_attachments)
        
        # 4. If email sent, update the warning record
        if email_sent:
            try:
                cur.execute("""
                    UPDATE warnings 
                    SET email_sent = 1, email_sent_at = CURRENT_TIMESTAMP 
                    WHERE employee_id = :emp_id AND warning_type = :w_type AND issued_date = TRUNC(SYSDATE)
                """, {"emp_id": emp_id, "w_type": sp_type})
                conn.commit()
            except Exception:
                pass  # Non-critical, email was already sent
            
            cur.close()
            conn.close()
            
            return {
                "success": True,
                "message": f"{sp_type} berhasil dikirim ke {emp_name} ({emp_email}).",
                "employee_name": emp_name,
                "employee_email": emp_email,
                "previous_sp_level": current_sp,
                "new_sp_level": new_sp_level,
                "sp_type": sp_type,
                "email_sent": True,
                "reason": reason,
                "attachments_sent": [p.name for p in resolved_attachments]
            }
        else:
            # Email failed — but DB is already committed (sp_level + warnings saved)
            cur.close()
            conn.close()
            
            return {
                "success": True,
                "message": f"{sp_type} tercatat di database untuk {emp_name}. SP level dinaikkan ke {new_sp_level}. Namun email gagal terkirim ke {emp_email}.",
                "employee_name": emp_name,
                "employee_email": emp_email,
                "previous_sp_level": current_sp,
                "new_sp_level": new_sp_level,
                "sp_type": sp_type,
                "email_sent": False,
                "email_error": f"Gagal mengirim email ke {emp_email}. Data SP tetap tersimpan di database.",
                "reason": reason,
                "attachments_sent": [p.name for p in resolved_attachments]
            }
        
    except Exception as e:
        if conn:
            try:
                conn.rollback()
                conn.close()
            except:
                pass
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


def send_email_to_employee(
    emp_id: int, 
    subject: Optional[str] = "", 
    message: Optional[str] = "", 
    attachments: Optional[Any] = None, 
    auto_polish: bool = True
) -> Dict[str, Any]:
    """
    Kirim email kustom ke satu karyawan spesifik dengan opsi pemolesan otomatis dan lampiran.
    
    Args:
        emp_id: Database ID karyawan
        subject: Subjek email
        message: Isi pesan email (plain text, akan di-format ke HTML)
        attachments: File tunggal atau list file pendukung untuk dilampirkan
        auto_polish: Memoles subjek dan isi email menggunakan AI agar terdengar sangat profesional (default: True)
        
    Returns:
        Dict dengan status kesuksesan dan detail pengiriman
    """
    subject = subject or ""
    message = message or ""
    try:
        conn = _get_connection()
        cur = conn.cursor()
        
        # Get employee email
        cur.execute("SELECT name, email FROM employees WHERE id = :emp_id", {"emp_id": emp_id})
        row = cur.fetchone()
        
        if not row:
            cur.close()
            conn.close()
            return {"success": False, "error": f"Karyawan dengan ID {emp_id} tidak ditemukan."}
        
        emp_name, emp_email = row
        cur.close()
        conn.close()
        
        # Auto polish if enabled
        if auto_polish:
            subject, message = _auto_polish_content(emp_name, subject, message)
            
        # Resolve attachments
        resolved_attachments = _resolve_attachments(attachments)
        
        # Load broadcast template
        template = _load_template("broadcast.html")
        if template:
            html_content = template.format(
                subject=subject,
                message=message,
                recipient_name=emp_name,
                sent_date=datetime.now().strftime("%d %B %Y")
            )
        else:
            # Fallback simple HTML
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <h2>{subject}</h2>
                <p>Kepada Yth. <strong>{emp_name}</strong>,</p>
                <div style="padding: 15px; background: #f5f5f5; border-radius: 5px; white-space: pre-line;">
                    {message}
                </div>
                <hr>
                <p style="color: #666; font-size: 12px;">Email otomatis dari HR System.</p>
            </body>
            </html>
            """
        
        email_sent = _send_email(emp_email, subject, html_content, resolved_attachments)
        
        if email_sent:
            return {
                "success": True,
                "message": f"Email berhasil dikirim ke {emp_name} ({emp_email}).",
                "recipient": emp_name,
                "email": emp_email,
                "subject": subject,
                "auto_polished": auto_polish,
                "attachments_sent": [p.name for p in resolved_attachments]
            }
        else:
            return {"success": False, "error": "Gagal mengirim email. Periksa konfigurasi SMTP."}
        
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


def send_broadcast_email(
    subject: Optional[str] = "", 
    message: Optional[str] = "", 
    department: str = None, 
    attachments: Optional[Any] = None, 
    auto_polish: bool = True
) -> Dict[str, Any]:
    """
    Kirim email broadcast ke semua karyawan aktif atau filter berdasarkan departemen,
    dengan opsi pemolesan otomatis dan lampiran.
    
    Args:
        subject: Subjek email broadcast
        message: Isi pesan broadcast
        department: Filter departemen (opsional, None = semua karyawan)
        attachments: File tunggal atau list file pendukung untuk dilampirkan
        auto_polish: Memoles subjek dan isi email menggunakan AI agar terdengar sangat profesional (default: True)
        
    Returns:
        Dict dengan status kesuksesan, jumlah terkirim, dan rincian
    """
    subject = subject or ""
    message = message or ""
    try:
        conn = _get_connection()
        cur = conn.cursor()
        
        # Build query based on department filter
        if department:
            cur.execute("""
                SELECT id, name, email FROM employees 
                WHERE status = 'active' AND LOWER(department) = LOWER(:dept)
            """, {"dept": department})
        else:
            cur.execute("""
                SELECT id, name, email FROM employees 
                WHERE status = 'active'
            """)
        
        employees = cur.fetchall()
        cur.close()
        conn.close()
        
        if not employees:
            return {
                "success": False, 
                "error": f"Tidak ada karyawan aktif ditemukan{' di departemen ' + department if department else ''}."
            }
            
        # Auto polish if enabled
        if auto_polish:
            recipient_desc = f"Departemen {department}" if department else "Semua Karyawan"
            subject, message = _auto_polish_content(recipient_desc, subject, message)
            
        # Resolve attachments
        resolved_attachments = _resolve_attachments(attachments)
        
        # Load broadcast template
        template = _load_template("broadcast.html")
        
        sent_count = 0
        failed_count = 0
        sent_to = []
        
        for emp_id, emp_name, emp_email in employees:
            if template:
                html_content = template.format(
                    subject=subject,
                    message=message,
                    recipient_name=emp_name,
                    sent_date=datetime.now().strftime("%d %B %Y")
                )
            else:
                html_content = f"""
                <html>
                <body style="font-family: Arial, sans-serif; padding: 20px;">
                    <h2>{subject}</h2>
                    <p>Kepada Yth. <strong>{emp_name}</strong>,</p>
                    <div style="padding: 15px; background: #f5f5f5; border-radius: 5px; white-space: pre-line;">
                        {message}
                    </div>
                    <hr>
                    <p style="color: #666; font-size: 12px;">Email otomatis dari HR System.</p>
                </body>
                </html>
                """
            
            if _send_email(emp_email, subject, html_content, resolved_attachments):
                sent_count += 1
                sent_to.append(emp_name)
            else:
                failed_count += 1
        
        return {
            "success": True,
            "message": f"Broadcast selesai. {sent_count} email berhasil dikirim{', ' + str(failed_count) + ' gagal' if failed_count > 0 else ''}.",
            "total_recipients": len(employees),
            "sent_count": sent_count,
            "failed_count": failed_count,
            "department_filter": department,
            "sent_to": sent_to[:10] if len(sent_to) > 10 else sent_to,
            "subject": subject,
            "auto_polished": auto_polish,
            "attachments_sent": [p.name for p in resolved_attachments]
        }
        
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


def reset_sp_level(emp_id: int, reason: str = "Pemutihan SP") -> Dict[str, Any]:
    """
    Reset SP level employee back to 0.
    """
    conn = None
    cur = None
    try:
        conn = _get_connection()
        cur = conn.cursor()

        # Check employee exists
        cur.execute("SELECT name FROM employees WHERE id = :emp_id", {"emp_id": emp_id})
        row = cur.fetchone()
        
        if not row:
            return {"success": False, "error": f"Karyawan dengan ID {emp_id} tidak ditemukan"}
            
        emp_name = row[0]

        # Reset SP level
        cur.execute("UPDATE employees SET sp_level = 0 WHERE id = :emp_id", {"emp_id": emp_id})
        
        # Log to warnings table as a reset event (using a special code or just note)
        cur.execute("""
            INSERT INTO warnings (employee_id, warning_type, reason, issued_date, issued_by)
            VALUES (:emp_id, 'RESET', :reason, TRUNC(SYSDATE), 'SYSTEM')
        """, {"emp_id": emp_id, "reason": reason})

        conn.commit()
        return {
            "success": True, 
            "message": f"SP Level untuk {emp_name} berhasil di-reset ke 0.",
            "new_sp_level": 0
        }

    except Exception as e:
        if conn: conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        if cur: cur.close()
        if conn: conn.close()



EMAIL_GENERATION_PROMPT = """Tugas Anda adalah menyusun konten email HR yang profesional, padat, dan jelas dalam Bahasa Indonesia.

Informasi Penerima: {recipient_name}
Konteks/Permintaan: {context}

Instruksi:
1. Gunakan bahasa yang sopan dan profesional (gunakan 'Bapak/Ibu' jika perlu).
2. Pastikan isi email langsung pada intinya (to the point).
3. Sesuaikan nada bicara dengan konteks yang diberikan (formal untuk SP, hangat untuk apresiasi, informatif untuk pengumuman).
4. Output HARUS dalam format JSON murni:
{{
  "subject": "Subjek email yang menarik dan jelas",
  "body": "Isi pesan email (plain text, gunakan newline \\n jika perlu)"
}}
"""


def generate_email_content(recipient_name: Optional[str] = "", context: Optional[str] = "") -> Dict[str, Any]:
    """
    Menyusun konten subjek dan pesan email menggunakan LLM agar lebih profesional dan padat.
    
    Args:
        recipient_name: Nama penerima email
        context: Konteks atau poin-poin informasi yang ingin disampaikan
        
    Returns:
        Dict dengan subjek dan body email
    """
    recipient_name = recipient_name or "Karyawan"
    context = context or ""
    try:
        prompt = EMAIL_GENERATION_PROMPT.format(
            recipient_name=recipient_name,
            context=context
        )
        
        content = gemini_chat(
            model="gemini-2.5-flash",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            response_mime_type="application/json"
        )
        
        # Ekstrak JSON dari response
        import json
        import re
        
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            return {
                "success": True,
                "subject": data.get("subject", "Pemberitahuan HR"),
                "body": data.get("body", ""),
                "recipient_name": recipient_name
            }
        else:
            return {
                "success": False, 
                "error": "Format respons LLM tidak valid (bukan JSON).",
                "raw_content": content
            }
            
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


# Tool definitions for agent
EMAIL_TOOLS = [
    {
        "name": "send_warning_letter",
        "description": "ACTION TOOL: Mengirim email SP dan menaikkan level SP. JANGAN gunakan untuk sekadar mengecek status. Gunakan get_employee_by_id untuk cek status. SP = Surat Peringatan. Level SP auto-increment: SP1→SP2→SP3.",
        "parameters": {
            "type": "object",
            "properties": {
                "emp_id": {
                    "type": "integer",
                    "description": "Database ID karyawan (integer). Dapatkan dari search_employees jika hanya punya nama."
                },
                "reason": {
                    "type": "string",
                    "description": "Alasan pemberian SP. Contoh: 'Terlambat lebih dari 5x dalam sebulan tanpa keterangan yang jelas.'"
                },
                "issued_by": {
                    "type": "integer",
                    "description": "ID HR user yang mengeluarkan SP (default: 1)",
                    "default": 1
                },
                "attachments": {
                    "type": ["string", "array"],
                    "description": "File tunggal atau daftar file (path lokal, URL, atau nama file temp) untuk dilampirkan sebagai bukti/laporan pendukung SP.",
                    "default": None
                }
            },
            "required": ["emp_id", "reason"]
        }
    },
    {
        "name": "send_email_to_employee",
        "description": "Kirim email kustom ke satu karyawan spesifik dengan opsi pemolesan otomatis dan lampiran. Gunakan untuk pemberitahuan individual seperti reminder, pengumuman personal, dll.",
        "parameters": {
            "type": "object",
            "properties": {
                "emp_id": {
                    "type": "integer",
                    "description": "Database ID karyawan"
                },
                "subject": {
                    "type": "string",
                    "description": "Subjek email"
                },
                "message": {
                    "type": "string",
                    "description": "Isi pesan email (plain text, akan dipoles otomatis dan di-format ke HTML)"
                },
                "attachments": {
                    "type": ["string", "array"],
                    "description": "File tunggal atau daftar file (path lokal, URL, atau nama file temp) untuk dilampirkan.",
                    "default": None
                },
                "auto_polish": {
                    "type": "boolean",
                    "description": "Jika true, pesan akan dipoles secara otomatis menggunakan AI agar terdengar sangat profesional dalam bahasa Indonesia.",
                    "default": True
                }
            },
            "required": ["emp_id", "subject", "message"]
        }
    },
    {
        "name": "send_broadcast_email",
        "description": "Kirim email broadcast ke SEMUA karyawan aktif atau filter berdasarkan departemen dengan opsi pemolesan otomatis dan lampiran. Gunakan untuk pengumuman umum seperti libur, kebijakan baru, event perusahaan.",
        "parameters": {
            "type": "object",
            "properties": {
                "subject": {
                    "type": "string",
                    "description": "Subjek email broadcast"
                },
                "message": {
                    "type": "string",
                    "description": "Isi pesan broadcast (plain text, akan dipoles otomatis)"
                },
                "department": {
                    "type": "string",
                    "description": "Filter departemen (opsional). Kosongkan untuk kirim ke semua karyawan.",
                    "default": None
                },
                "attachments": {
                    "type": ["string", "array"],
                    "description": "File tunggal atau daftar file (path lokal, URL, atau nama file temp) untuk dilampirkan.",
                    "default": None
                },
                "auto_polish": {
                    "type": "boolean",
                    "description": "Jika true, pesan akan dipoles secara otomatis menggunakan AI agar terdengar sangat profesional dalam bahasa Indonesia.",
                    "default": True
                }
            },
            "required": ["subject", "message"]
        }
    },
    {
        "name": "reset_sp_level",
        "description": "ACTION TOOL: Mereset level SP karyawan kembali ke 0. Gunakan ini jika SP sebelumnya salah kirim atau ada pemutihan.",
        "parameters": {
            "type": "object",
            "properties": {
                "emp_id": {
                    "type": "integer",
                    "description": "Database ID karyawan"
                },
                "reason": {
                    "type": "string",
                    "description": "Alasan reset (untuk log audit)"
                }
            },
            "required": ["emp_id", "reason"]
        }
    },
    {
        "name": "generate_email_content",
        "description": "Gunakan LLM untuk menyusun konten email (subjek & pesan) agar lebih profesional, padat, dan jelas berdasarkan konteks yang diberikan. Hasil dari tool ini bisa di-pass ke send_email_to_employee atau send_broadcast_email.",
        "parameters": {
            "type": "object",
            "properties": {
                "recipient_name": {
                    "type": "string",
                    "description": "Nama penerima (misal: 'Semua Karyawan' atau nama spesifik)"
                },
                "context": {
                    "type": "string",
                    "description": "Poin-poin informasi atau instruksi pesan yang ingin disampaikan."
                }
            },
            "required": ["recipient_name", "context"]
        }
    }
]
