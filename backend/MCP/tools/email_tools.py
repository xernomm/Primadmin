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
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import cx_Oracle
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

# Template directory
TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates" / "email"


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



def _send_email(to_email: str, subject: str, html_content: str) -> bool:
    """
    Send email via SMTP.
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        html_content: HTML body content
        
    Returns:
        True if successful, False otherwise
    """
    try:
        clean_email = _sanitize_email(to_email)
        if not clean_email:
            print("[EMAIL ERROR] Invalid email address (empty after sanitization)")
            return False
            
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


def send_warning_letter(emp_id: int, reason: str, issued_by: int = 1) -> Dict[str, Any]:
    """
    Kirim Surat Peringatan (SP) ke karyawan dan increment level SP.
    
    SP = Surat Peringatan (Warning Letter):
    - SP1 = Peringatan Pertama (First Warning)
    - SP2 = Peringatan Kedua (Second Warning)  
    - SP3 = Peringatan Terakhir (Final Warning, before termination)
    
    Args:
        emp_id: Database ID karyawan (dari search_employees)
        reason: Alasan pemberian SP
        issued_by: ID HR user yang mengeluarkan SP (default: 1)
        
    Returns:
        Dict with success status, new SP level, and message
    """
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
        
        # 3. Attempt to send email
        subject = f"Surat Peringatan {new_sp_level} ({sp_type}) - {emp_name}"
        email_sent = _send_email(emp_email, subject, html_content)
        
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
                "reason": reason
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
                "reason": reason
            }
        
    except Exception as e:
        if conn:
            try:
                conn.rollback()
                conn.close()
            except:
                pass
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


def send_email_to_employee(emp_id: int, subject: str, message: str) -> Dict[str, Any]:
    """
    Kirim email kustom ke satu karyawan.
    
    Args:
        emp_id: Database ID karyawan
        subject: Subjek email
        message: Isi pesan email
        
    Returns:
        Dict with success status and message
    """
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
                <div style="padding: 15px; background: #f5f5f5; border-radius: 5px;">
                    {message}
                </div>
                <hr>
                <p style="color: #666; font-size: 12px;">Email otomatis dari HR System.</p>
            </body>
            </html>
            """
        
        email_sent = _send_email(emp_email, subject, html_content)
        
        if email_sent:
            return {
                "success": True,
                "message": f"Email berhasil dikirim ke {emp_name} ({emp_email}).",
                "recipient": emp_name,
                "email": emp_email,
                "subject": subject
            }
        else:
            return {"success": False, "error": "Gagal mengirim email. Periksa konfigurasi SMTP."}
        
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


def send_broadcast_email(subject: str, message: str, department: str = None) -> Dict[str, Any]:
    """
    Kirim email broadcast ke semua karyawan aktif atau filter berdasarkan departemen.
    
    Args:
        subject: Subjek email broadcast
        message: Isi pesan broadcast
        department: Filter departemen (opsional, None = semua karyawan)
        
    Returns:
        Dict with success status, count sent, and details
    """
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
                    <div style="padding: 15px; background: #f5f5f5; border-radius: 5px;">
                        {message}
                    </div>
                    <hr>
                    <p style="color: #666; font-size: 12px;">Email otomatis dari HR System.</p>
                </body>
                </html>
                """
            
            if _send_email(emp_email, subject, html_content):
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
            "sent_to": sent_to[:10] if len(sent_to) > 10 else sent_to,  # Limit list
            "subject": subject
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
                }
            },
            "required": ["emp_id", "reason"]
        }
    },
    {
        "name": "send_email_to_employee",
        "description": "Kirim email kustom ke satu karyawan spesifik. Gunakan untuk pemberitahuan individual seperti reminder, pengumuman personal, dll.",
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
                    "description": "Isi pesan email (plain text, akan di-format ke HTML)"
                }
            },
            "required": ["emp_id", "subject", "message"]
        }
    },
    {
        "name": "send_broadcast_email",
        "description": "Kirim email broadcast ke SEMUA karyawan aktif atau filter berdasarkan departemen. Gunakan untuk pengumuman umum seperti libur, kebijakan baru, event perusahaan.",
        "parameters": {
            "type": "object",
            "properties": {
                "subject": {
                    "type": "string",
                    "description": "Subjek email broadcast"
                },
                "message": {
                    "type": "string",
                    "description": "Isi pesan broadcast"
                },
                "department": {
                    "type": "string",
                    "description": "Filter departemen (opsional). Kosongkan untuk kirim ke semua karyawan.",
                    "default": None
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
    }
]
