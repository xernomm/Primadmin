"""
Payroll tools for HR Agent.
Provides payroll data retrieval, anomaly analysis (LLM-powered),
CSV export, PDF generation, and email sending for payroll slips.
"""
import os
import csv
import json
import re
import smtplib
import traceback
from datetime import datetime, date
from typing import Dict, Any, Optional, List
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import cx_Oracle
from dotenv import load_dotenv
from agent.gemini_client import gemini_generate

load_dotenv()

ORACLE_USER = os.getenv("ORACLE_USER")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD")
ORACLE_HOST = os.getenv("ORACLE_HOST")
ORACLE_PORT = os.getenv("ORACLE_PORT")
ORACLE_SERVICE = os.getenv("ORACLE_SERVICE_NAME")

dsn = cx_Oracle.makedsn(ORACLE_HOST, ORACLE_PORT, service_name=ORACLE_SERVICE)

# SMTP config (reuse from email_tools)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", SMTP_USER)

# LLM Model for analysis
ANALYSIS_MODEL = os.getenv("ANALYSIS_MODEL", "gemini-2.5-flash")

# Directories — import from centralized config
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config import EXPORTS_DIR as EXPORT_DIR, PAYROLL_EXPORTS_DIR as PAYROLL_DIR


def _get_connection():
    """Get Oracle database connection."""
    return cx_Oracle.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=dsn)


def _format_currency(amount) -> str:
    """Format number as Indonesian Rupiah."""
    if amount is None:
        return "Rp 0"
    return f"Rp {int(amount):,}".replace(",", ".")


def _format_file_size(size_bytes: int) -> str:
    """Format bytes to human readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def _read_lob(val):
    """Read Oracle LOB if needed."""
    if val and hasattr(val, 'read'):
        return val.read()
    return val


# ==================== TOOL 1: GET PAYROLL DETAIL ====================

def get_payroll_detail(emp_id: int, month: int = None, year: int = None) -> Dict[str, Any]:
    """
    Ambil detail slip gaji karyawan. Bisa per periode tertentu atau semua periode.
    
    Args:
        emp_id: Database ID karyawan
        month: Bulan (1-12), kosongkan untuk semua periode
        year: Tahun, kosongkan untuk semua periode
        
    Returns:
        Dict with payroll slip data
    """
    try:
        conn = _get_connection()
        cur = conn.cursor()
        
        # Get employee info
        cur.execute("SELECT name, employee_code, department, position FROM employees WHERE id = :eid", {"eid": emp_id})
        emp = cur.fetchone()
        if not emp:
            cur.close(); conn.close()
            return {"success": False, "error": f"Karyawan dengan ID {emp_id} tidak ditemukan."}
        
        emp_name, emp_code, dept, position = emp
        
        if month and year:
            # Single period
            cur.execute("""
                SELECT id, period_month, period_year, basic_salary, overtime_pay, bonus,
                       allowance_transport, allowance_meal, allowance_housing,
                       allowance_communication, allowance_other,
                       deduction_bpjs_kesehatan, deduction_bpjs_ketenagakerjaan,
                       deduction_pph21, deduction_loan, deduction_absence, deduction_other,
                       gross_salary, total_deductions, net_salary,
                       payment_date, payment_method, bank_account, status, notes, file_path
                FROM payroll_slips
                WHERE employee_id = :eid AND period_month = :m AND period_year = :y
            """, {"eid": emp_id, "m": month, "y": year})
        else:
            # All periods
            cur.execute("""
                SELECT id, period_month, period_year, basic_salary, overtime_pay, bonus,
                       allowance_transport, allowance_meal, allowance_housing,
                       allowance_communication, allowance_other,
                       deduction_bpjs_kesehatan, deduction_bpjs_ketenagakerjaan,
                       deduction_pph21, deduction_loan, deduction_absence, deduction_other,
                       gross_salary, total_deductions, net_salary,
                       payment_date, payment_method, bank_account, status, notes, file_path
                FROM payroll_slips
                WHERE employee_id = :eid
                ORDER BY period_year DESC, period_month DESC
            """, {"eid": emp_id})
        
        rows = cur.fetchall()
        cur.close(); conn.close()
        
        if not rows:
            period_str = f" periode {month}/{year}" if month and year else ""
            return {"success": False, "error": f"Tidak ada data payroll untuk {emp_name}{period_str}."}
        
        slips = []
        for r in rows:
            slips.append({
                "id": r[0], "period": f"{r[1]:02d}/{r[2]}",
                "basic_salary": r[3], "overtime_pay": r[4], "bonus": r[5],
                "allowances": {
                    "transport": r[6], "meal": r[7], "housing": r[8],
                    "communication": r[9], "other": r[10]
                },
                "deductions": {
                    "bpjs_kesehatan": r[11], "bpjs_ketenagakerjaan": r[12],
                    "pph21": r[13], "loan": r[14], "absence": r[15], "other": r[16]
                },
                "gross_salary": r[17], "total_deductions": r[18], "net_salary": r[19],
                "payment_date": r[20].strftime("%Y-%m-%d") if r[20] else None,
                "payment_method": r[21], "bank_account": r[22],
                "status": r[23], "notes": _read_lob(r[24]),
                "file_path": r[25]
            })
        
        return {
            "success": True,
            "employee": {"id": emp_id, "name": emp_name, "code": emp_code, "department": dept, "position": position},
            "payroll_slips": slips,
            "total_records": len(slips)
        }
        
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


# ==================== TOOL 2: GET PAYROLL INFO (DETAIL BREAKDOWN) ====================

def get_payroll_info(emp_id: int, month: int = None, year: int = None) -> Dict[str, Any]:
    """
    Ambil informasi detail penggajian karyawan termasuk rincian tunjangan dan potongan.
    
    Args:
        emp_id: Database ID karyawan
        month: Bulan (1-12), default bulan terakhir yang tersedia
        year: Tahun, default tahun terakhir yang tersedia
        
    Returns:
        Dict with detailed salary breakdown
    """
    try:
        conn = _get_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT name, employee_code, department, position FROM employees WHERE id = :eid", {"eid": emp_id})
        emp = cur.fetchone()
        if not emp:
            cur.close(); conn.close()
            return {"success": False, "error": f"Karyawan dengan ID {emp_id} tidak ditemukan."}
        
        emp_name, emp_code, dept, position = emp
        
        if month and year:
            cur.execute("""
                SELECT * FROM payroll_slips
                WHERE employee_id = :eid AND period_month = :m AND period_year = :y
            """, {"eid": emp_id, "m": month, "y": year})
        else:
            cur.execute("""
                SELECT * FROM payroll_slips
                WHERE employee_id = :eid
                ORDER BY period_year DESC, period_month DESC
                FETCH FIRST 1 ROWS ONLY
            """, {"eid": emp_id})
        
        # Get column names
        columns = [desc[0].lower() for desc in cur.description]
        row = cur.fetchone()
        cur.close(); conn.close()
        
        if not row:
            return {"success": False, "error": f"Tidak ada data payroll untuk {emp_name}."}
        
        data = dict(zip(columns, row))
        
        # Build detailed breakdown
        total_allowances = sum([
            data.get("allowance_transport", 0) or 0,
            data.get("allowance_meal", 0) or 0,
            data.get("allowance_housing", 0) or 0,
            data.get("allowance_communication", 0) or 0,
            data.get("allowance_other", 0) or 0,
        ])
        
        total_deductions = sum([
            data.get("deduction_bpjs_kesehatan", 0) or 0,
            data.get("deduction_bpjs_ketenagakerjaan", 0) or 0,
            data.get("deduction_pph21", 0) or 0,
            data.get("deduction_loan", 0) or 0,
            data.get("deduction_absence", 0) or 0,
            data.get("deduction_other", 0) or 0,
        ])
        
        return {
            "success": True,
            "employee": {"id": emp_id, "name": emp_name, "code": emp_code, "department": dept, "position": position},
            "period": f"{int(data.get('period_month', 0)):02d}/{int(data.get('period_year', 0))}",
            "salary_breakdown": {
                "gaji_pokok": _format_currency(data.get("basic_salary")),
                "lembur": _format_currency(data.get("overtime_pay")),
                "bonus": _format_currency(data.get("bonus")),
                "tunjangan": {
                    "transportasi": _format_currency(data.get("allowance_transport")),
                    "makan": _format_currency(data.get("allowance_meal")),
                    "perumahan": _format_currency(data.get("allowance_housing")),
                    "komunikasi": _format_currency(data.get("allowance_communication")),
                    "lainnya": _format_currency(data.get("allowance_other")),
                    "total_tunjangan": _format_currency(total_allowances)
                },
                "potongan": {
                    "bpjs_kesehatan": _format_currency(data.get("deduction_bpjs_kesehatan")),
                    "bpjs_ketenagakerjaan": _format_currency(data.get("deduction_bpjs_ketenagakerjaan")),
                    "pph21": _format_currency(data.get("deduction_pph21")),
                    "pinjaman": _format_currency(data.get("deduction_loan")),
                    "potongan_absensi": _format_currency(data.get("deduction_absence")),
                    "lainnya": _format_currency(data.get("deduction_other")),
                    "total_potongan": _format_currency(total_deductions)
                },
                "gaji_kotor": _format_currency(data.get("gross_salary")),
                "total_potongan": _format_currency(total_deductions),
                "gaji_bersih": _format_currency(data.get("net_salary"))
            },
            "payment_info": {
                "tanggal_bayar": data.get("payment_date").strftime("%Y-%m-%d") if data.get("payment_date") else None,
                "metode": data.get("payment_method"),
                "bank": data.get("bank_account"),
                "status": data.get("status")
            }
        }
        
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


# ==================== TOOL 3: ANALYZE PAYROLL ANOMALY (LLM) ====================

def analyze_payroll_anomaly(emp_id: int = None, period_count: int = 6) -> Dict[str, Any]:
    """
    Analisa anomali penggajian karyawan menggunakan AI.
    Mendeteksi kenaikan/penurunan gaji yang tidak wajar.
    
    Args:
        emp_id: Database ID karyawan (None = analisa semua karyawan)
        period_count: Jumlah periode terakhir untuk dianalisa (default: 6)
        
    Returns:
        Dict with AI analysis of payroll anomalies
    """
    try:
        conn = _get_connection()
        cur = conn.cursor()
        
        if emp_id:
            cur.execute("""
                SELECT e.name, e.department, e.position, e.employee_code,
                       p.period_month, p.period_year, p.basic_salary, p.overtime_pay,
                       p.bonus, p.gross_salary, p.total_deductions, p.net_salary,
                       p.allowance_transport, p.allowance_meal, p.allowance_housing
                FROM payroll_slips p
                JOIN employees e ON p.employee_id = e.id
                WHERE p.employee_id = :eid
                ORDER BY p.period_year DESC, p.period_month DESC
                FETCH FIRST :cnt ROWS ONLY
            """, {"eid": emp_id, "cnt": period_count})
        else:
            cur.execute("""
                SELECT e.name, e.department, e.position, e.employee_code,
                       p.period_month, p.period_year, p.basic_salary, p.overtime_pay,
                       p.bonus, p.gross_salary, p.total_deductions, p.net_salary,
                       p.allowance_transport, p.allowance_meal, p.allowance_housing
                FROM payroll_slips p
                JOIN employees e ON p.employee_id = e.id
                ORDER BY e.name, p.period_year DESC, p.period_month DESC
                FETCH FIRST :cnt ROWS ONLY
            """, {"cnt": period_count * 12})  # all employees
        
        rows = cur.fetchall()
        cur.close(); conn.close()
        
        if not rows:
            return {"success": False, "error": "Tidak ada data payroll untuk dianalisa."}
        
        # Format payroll data for LLM
        payroll_table = "Nama | Dept | Periode | Gaji Pokok | Lembur | Bonus | Gaji Kotor | Potongan | Gaji Bersih\n"
        payroll_table += "-" * 100 + "\n"
        for r in rows:
            payroll_table += f"{r[0]} | {r[1]} | {r[4]:02d}/{r[5]} | {r[6]:,} | {r[7]:,} | {r[8]:,} | {r[9]:,} | {r[10]:,} | {r[11]:,}\n"
        
        analysis_prompt = f"""Analisa data penggajian berikut untuk mendeteksi anomali:

## Data Payroll (Periode Terakhir)
{payroll_table}

## Instruksi Analisis
1. Bandingkan gaji antar periode untuk setiap karyawan
2. Deteksi kenaikan atau penurunan yang signifikan (>10%)
3. Identifikasi anomali pada komponen lembur, bonus, atau potongan
4. Bandingkan gaji antar karyawan di posisi/departemen yang sama
5. Berikan rekomendasi tindakan

Format output sebagai JSON:
{{
  "summary": "ringkasan temuan utama",
  "anomalies": [
    {{
      "employee": "nama",
      "type": "kenaikan/penurunan/anomali",
      "detail": "penjelasan",
      "severity": "low/medium/high"
    }}
  ],
  "trends": "tren umum penggajian",
  "recommendations": ["rekomendasi 1", "rekomendasi 2"]
}}"""

        analysis_text = gemini_generate(
            model=ANALYSIS_MODEL,
            prompt=analysis_prompt,
            temperature=0.3,
            response_mime_type="application/json"
        )
        
        # Parse JSON from LLM response
        json_match = re.search(r'\{[\s\S]*\}', analysis_text)
        if json_match:
            try:
                analysis_result = json.loads(json_match.group())
            except json.JSONDecodeError:
                analysis_result = {"summary": analysis_text, "parse_error": True}
        else:
            analysis_result = {"summary": analysis_text, "parse_error": True}
        
        return {
            "success": True,
            "analysis": analysis_result,
            "data_count": len(rows),
            "period_count": period_count,
            "employee_filter": emp_id
        }
        
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


# ==================== TOOL 4: EXPORT PAYROLL CSV ====================

def export_payroll_csv(department: str = None, month: int = None, year: int = None) -> Dict[str, Any]:
    """
    Export laporan payroll ke file CSV.
    
    Args:
        department: Filter departemen (None = semua)
        month: Bulan filter (None = semua)
        year: Tahun filter (None = tahun ini)
        
    Returns:
        Dict with file path, download URL, and widget
    """
    try:
        conn = _get_connection()
        cur = conn.cursor()
        
        query = """
            SELECT e.employee_code, e.name, e.department, e.position,
                   p.period_month, p.period_year,
                   p.basic_salary, p.overtime_pay, p.bonus,
                   p.allowance_transport, p.allowance_meal, p.allowance_housing,
                   p.allowance_communication, p.allowance_other,
                   p.deduction_bpjs_kesehatan, p.deduction_bpjs_ketenagakerjaan,
                   p.deduction_pph21, p.deduction_loan, p.deduction_absence, p.deduction_other,
                   p.gross_salary, p.total_deductions, p.net_salary,
                   p.payment_date, p.payment_method, p.bank_account, p.status
            FROM payroll_slips p
            JOIN employees e ON p.employee_id = e.id
            WHERE 1=1
        """
        params = {}
        
        if department:
            query += " AND LOWER(e.department) = LOWER(:dept)"
            params["dept"] = department
        if month:
            query += " AND p.period_month = :m"
            params["m"] = month
        if year:
            query += " AND p.period_year = :y"
            params["y"] = year
        
        query += " ORDER BY e.name, p.period_year, p.period_month"
        
        cur.execute(query, params)
        rows = cur.fetchall()
        cur.close(); conn.close()
        
        if not rows:
            return {"success": False, "error": "Tidak ada data payroll sesuai filter."}
        
        # Generate CSV
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        dept_suffix = f"_{department.lower().replace(' ', '_')}" if department else ""
        period_suffix = f"_{month:02d}_{year}" if month and year else ""
        filename = f"payroll_report{dept_suffix}{period_suffix}_{timestamp}.csv"
        filepath = EXPORT_DIR / filename
        
        columns = [
            "Kode Karyawan", "Nama", "Departemen", "Posisi",
            "Bulan", "Tahun",
            "Gaji Pokok", "Lembur", "Bonus",
            "Tunj. Transport", "Tunj. Makan", "Tunj. Perumahan",
            "Tunj. Komunikasi", "Tunj. Lainnya",
            "Pot. BPJS Kes", "Pot. BPJS TK",
            "Pot. PPh21", "Pot. Pinjaman", "Pot. Absensi", "Pot. Lainnya",
            "Gaji Kotor", "Total Potongan", "Gaji Bersih",
            "Tanggal Bayar", "Metode Bayar", "Rekening", "Status"
        ]
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            for row in rows:
                row_data = list(row)
                if row_data[23] and hasattr(row_data[23], 'strftime'):
                    row_data[23] = row_data[23].strftime("%Y-%m-%d")
                writer.writerow(row_data)
        
        file_size = os.path.getsize(filepath)
        
        from config import BASE_URL
        download_url = f"/api/exports/{filename}"
        full_server_url = f"{BASE_URL}{download_url}"
        
        return {
            "success": True,
            "message": f"Laporan payroll {len(rows)} record berhasil diekspor.",
            "file_path": full_server_url,
            "download_url": download_url,
            "filename": filename,
            "row_count": len(rows),
            "widget": {
                "type": "download",
                "filename": filename,
                "size": _format_file_size(file_size),
                "icon": "csv",
                "download_url": download_url
            }
        }
        
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


# ==================== TOOL 5: GET PAYROLL FILE ====================

def get_payroll_file(emp_id: int, month: int = None, year: int = None) -> Dict[str, Any]:
    """
    Ambil file slip gaji karyawan yang sudah ada.
    
    Args:
        emp_id: Database ID karyawan
        month: Bulan (default: bulan terakhir)
        year: Tahun (default: tahun terakhir)
        
    Returns:
        Dict with file path and download URL
    """
    try:
        conn = _get_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT name, employee_code FROM employees WHERE id = :eid", {"eid": emp_id})
        emp = cur.fetchone()
        if not emp:
            cur.close(); conn.close()
            return {"success": False, "error": f"Karyawan dengan ID {emp_id} tidak ditemukan."}
        
        emp_name, emp_code = emp
        
        if month and year:
            cur.execute("""
                SELECT file_path, download_url, period_month, period_year
                FROM payroll_slips
                WHERE employee_id = :eid AND period_month = :m AND period_year = :y
            """, {"eid": emp_id, "m": month, "y": year})
        else:
            cur.execute("""
                SELECT file_path, download_url, period_month, period_year
                FROM payroll_slips
                WHERE employee_id = :eid
                ORDER BY period_year DESC, period_month DESC
                FETCH FIRST 1 ROWS ONLY
            """, {"eid": emp_id})
        
        row = cur.fetchone()
        cur.close(); conn.close()
        
        if not row:
            return {"success": False, "error": f"Tidak ada slip gaji untuk {emp_name}."}
        
        file_path, download_url, pm, py = row
        
        from config import url_to_abs_path
        resolved_path = None
        if file_path:
            # Check if URL
            if file_path.startswith("http://") or file_path.startswith("https://"):
                resolved_path = url_to_abs_path(file_path)
            else:
                resolved_path = Path(file_path)
        
        if not resolved_path or not resolved_path.exists():
            return {
                "success": False,
                "error": f"File slip gaji {emp_name} periode {pm:02d}/{py} belum dibuat. Gunakan tool 'create_payroll_report_pdf' untuk membuatnya.",
                "suggestion": f"Buat slip gaji dengan create_payroll_report_pdf(emp_id={emp_id}, month={pm}, year={py})"
            }
        
        # File name for widget display
        fname = resolved_path.name if resolved_path else Path(file_path).name
        
        return {
            "success": True,
            "employee": {"name": emp_name, "code": emp_code},
            "period": f"{pm:02d}/{py}",
            "file_path": file_path,
            "download_url": download_url or f"/api/exports/payroll/{fname}",
            "widget": {
                "type": "download",
                "filename": fname,
                "size": _format_file_size(os.path.getsize(resolved_path if resolved_path else file_path)),
                "icon": "pdf",
                "download_url": download_url or f"/api/exports/payroll/{fname}"
            }
        }
        
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


# ==================== TOOL 6: CREATE PAYROLL REPORT PDF ====================

def create_payroll_report_pdf(emp_id: int, month: int = None, year: int = None) -> Dict[str, Any]:
    """
    Buat slip gaji PDF untuk karyawan.
    
    Args:
        emp_id: Database ID karyawan
        month: Bulan (default: bulan ini)
        year: Tahun (default: tahun ini)
        
    Returns:
        Dict with generated PDF file path and download URL
    """
    try:
        from fpdf import FPDF
        
        today = date.today()
        if not month:
            month = today.month
        if not year:
            year = today.year
        
        # Get payroll data
        result = get_payroll_detail(emp_id, month, year)
        if not result.get("success"):
            return result
        
        slip = result["payroll_slips"][0]
        emp = result["employee"]
        
        # Create PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        
        # Header
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "SLIP GAJI KARYAWAN", ln=True, align="C")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, f"Periode: {month:02d}/{year}", ln=True, align="C")
        pdf.ln(5)
        
        # Divider
        pdf.set_draw_color(0, 102, 204)
        pdf.set_line_width(0.5)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)
        
        # Employee Info
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "INFORMASI KARYAWAN", ln=True)
        pdf.set_font("Helvetica", "", 10)
        info_items = [
            ("Nama", emp["name"]),
            ("Kode Karyawan", emp["code"]),
            ("Departemen", emp["department"]),
            ("Posisi", emp["position"]),
        ]
        for label, value in info_items:
            pdf.cell(50, 6, f"{label}:", 0)
            pdf.cell(0, 6, str(value or "-"), ln=True)
        pdf.ln(5)
        
        # Income Section
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "PENGHASILAN", ln=True)
        pdf.set_font("Helvetica", "", 10)
        
        income_items = [
            ("Gaji Pokok", slip["basic_salary"]),
            ("Lembur", slip["overtime_pay"]),
            ("Bonus", slip["bonus"]),
            ("Tunj. Transportasi", slip["allowances"]["transport"]),
            ("Tunj. Makan", slip["allowances"]["meal"]),
            ("Tunj. Perumahan", slip["allowances"]["housing"]),
            ("Tunj. Komunikasi", slip["allowances"]["communication"]),
            ("Tunj. Lainnya", slip["allowances"]["other"]),
        ]
        for label, value in income_items:
            if value and value > 0:
                pdf.cell(100, 6, f"  {label}", 0)
                pdf.cell(0, 6, _format_currency(value), ln=True, align="R")
        
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(100, 7, "  GAJI KOTOR", 0)
        pdf.cell(0, 7, _format_currency(slip["gross_salary"]), ln=True, align="R")
        pdf.ln(3)
        
        # Deduction Section
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, "POTONGAN", ln=True)
        pdf.set_font("Helvetica", "", 10)
        
        deduction_items = [
            ("BPJS Kesehatan", slip["deductions"]["bpjs_kesehatan"]),
            ("BPJS Ketenagakerjaan", slip["deductions"]["bpjs_ketenagakerjaan"]),
            ("PPh 21", slip["deductions"]["pph21"]),
            ("Pinjaman", slip["deductions"]["loan"]),
            ("Potongan Absensi", slip["deductions"]["absence"]),
            ("Potongan Lainnya", slip["deductions"]["other"]),
        ]
        for label, value in deduction_items:
            if value and value > 0:
                pdf.cell(100, 6, f"  {label}", 0)
                pdf.cell(0, 6, f"- {_format_currency(value)}", ln=True, align="R")
        
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(100, 7, "  TOTAL POTONGAN", 0)
        pdf.cell(0, 7, f"- {_format_currency(slip['total_deductions'])}", ln=True, align="R")
        pdf.ln(5)
        
        # Net Salary
        pdf.set_draw_color(0, 102, 204)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(100, 10, "GAJI BERSIH (Take Home Pay)", 0)
        pdf.cell(0, 10, _format_currency(slip["net_salary"]), ln=True, align="R")
        pdf.ln(5)
        
        # Payment Info
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 5, f"Metode Pembayaran: {slip.get('payment_method', '-')} | Bank: {slip.get('bank_account', '-')}", ln=True)
        pdf.cell(0, 5, f"Tanggal Pembayaran: {slip.get('payment_date', '-')}", ln=True)
        pdf.ln(10)
        
        # Footer
        pdf.set_font("Helvetica", "I", 8)
        pdf.cell(0, 5, f"Dokumen ini digenerate secara otomatis pada {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align="C")
        pdf.cell(0, 5, "Slip gaji ini bersifat rahasia dan hanya untuk keperluan karyawan yang bersangkutan.", ln=True, align="C")
        
        # Save PDF
        safe_name = emp["name"].replace(" ", "_")
        filename = f"slip_gaji_{safe_name}_{month:02d}_{year}.pdf"
        filepath = PAYROLL_DIR / filename
        pdf.output(str(filepath))
        
        # Update DB with file path
        from config import BASE_URL
        conn = _get_connection()
        cur = conn.cursor()
        download_url = f"/api/exports/payroll/{filename}"
        full_server_url = f"{BASE_URL}{download_url}"
        
        cur.execute("""
            UPDATE payroll_slips SET file_path = :fp, download_url = :du
            WHERE employee_id = :eid AND period_month = :m AND period_year = :y
        """, {"fp": full_server_url, "du": download_url, "eid": emp_id, "m": month, "y": year})
        conn.commit()
        cur.close(); conn.close()
        
        file_size = os.path.getsize(filepath)
        
        return {
            "success": True,
            "message": f"Slip gaji {emp['name']} periode {month:02d}/{year} berhasil dibuat.",
            "file_path": full_server_url,
            "download_url": download_url,
            "filename": filename,
            "widget": {
                "type": "download",
                "filename": filename,
                "size": _format_file_size(file_size),
                "icon": "pdf",
                "download_url": download_url
            }
        }
        
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


# ==================== TOOL 7: SEND PAYROLL EMAIL ====================

def send_payroll_email(emp_id: int, month: int = None, year: int = None) -> Dict[str, Any]:
    """
    Kirim email slip gaji ke karyawan. Otomatis mencari atau membuat file PDF.
    
    Args:
        emp_id: Database ID karyawan
        month: Bulan (default: bulan terakhir)
        year: Tahun (default: tahun terakhir)
        
    Returns:
        Dict with success status and message
    """
    try:
        conn = _get_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT name, email, employee_code FROM employees WHERE id = :eid", {"eid": emp_id})
        emp = cur.fetchone()
        if not emp:
            cur.close(); conn.close()
            return {"success": False, "error": f"Karyawan dengan ID {emp_id} tidak ditemukan."}
        
        emp_name, emp_email, emp_code = emp
        
        today = date.today()
        if not month:
            # Find latest payroll period
            cur.execute("""
                SELECT period_month, period_year FROM payroll_slips
                WHERE employee_id = :eid
                ORDER BY period_year DESC, period_month DESC
                FETCH FIRST 1 ROWS ONLY
            """, {"eid": emp_id})
            latest = cur.fetchone()
            if latest:
                month, year = latest[0], latest[1]
            else:
                month, year = today.month, today.year
        
        if not year:
            year = today.year
        
        # Check if PDF exists, if not create it
        cur.execute("""
            SELECT file_path FROM payroll_slips
            WHERE employee_id = :eid AND period_month = :m AND period_year = :y
        """, {"eid": emp_id, "m": month, "y": year})
        row = cur.fetchone()
        cur.close(); conn.close()
        
        file_path = row[0] if row else None
        
        from config import url_to_abs_path
        resolved_path = None
        if file_path:
            if file_path.startswith("http://") or file_path.startswith("https://"):
                resolved_path = url_to_abs_path(file_path)
            else:
                resolved_path = Path(file_path)
        
        if not resolved_path or not resolved_path.exists():
            # Auto-create PDF
            pdf_result = create_payroll_report_pdf(emp_id, month, year)
            if not pdf_result.get("success"):
                return {"success": False, "error": f"Gagal membuat slip gaji: {pdf_result.get('error')}"}
            file_path = pdf_result["file_path"]
            resolved_path = url_to_abs_path(file_path) or Path(file_path)
        
        # Compose email
        subject = f"Slip Gaji - Periode {month:02d}/{year}"
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 10px 10px 0 0;">
                <h2 style="color: white; margin: 0;">Slip Gaji Karyawan</h2>
                <p style="color: rgba(255,255,255,0.8); margin: 5px 0 0 0;">Periode {month:02d}/{year}</p>
            </div>
            <div style="background: #f8f9fa; padding: 20px; border: 1px solid #e9ecef;">
                <p>Yth. <strong>{emp_name}</strong>,</p>
                <p>Berikut terlampir slip gaji Anda untuk periode <strong>{month:02d}/{year}</strong>.</p>
                <p>Slip gaji ini bersifat <strong>rahasia</strong> dan hanya untuk keperluan pribadi.</p>
                <p>Jika ada pertanyaan mengenai komponen gaji, silakan hubungi tim HR.</p>
                <br>
                <p style="color: #666;">Salam,<br><strong>HR Department</strong></p>
            </div>
            <div style="background: #e9ecef; padding: 10px; text-align: center; border-radius: 0 0 10px 10px;">
                <p style="font-size: 12px; color: #999; margin: 0;">Email ini dikirim secara otomatis oleh sistem HR.</p>
            </div>
        </body>
        </html>
        """
        
        # Send email with attachment
        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM_EMAIL
        msg["To"] = emp_email
        msg.attach(MIMEText(html_content, "html"))
        
        # Attach PDF
        with open(str(resolved_path), "rb") as f:
            part = MIMEBase("application", "pdf")
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={resolved_path.name}")
            msg.attach(part)
        
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM_EMAIL, emp_email, msg.as_string())
        
        return {
            "success": True,
            "message": f"Slip gaji {emp_name} periode {month:02d}/{year} berhasil dikirim ke {emp_email}.",
            "recipient": {"name": emp_name, "email": emp_email},
            "period": f"{month:02d}/{year}",
            "attachment": Path(file_path).name
        }
        
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


# ==================== TOOL DEFINITIONS ====================

PAYROLL_TOOLS = [
    {
        "name": "get_payroll_detail",
        "description": "Ambil detail slip gaji karyawan. Bisa melihat slip gaji per periode (bulan/tahun) atau semua periode sekaligus. Menampilkan gaji pokok, lembur, bonus, tunjangan, potongan, gaji kotor, dan gaji bersih.",
        "parameters": {
            "type": "object",
            "properties": {
                "emp_id": {
                    "type": "integer",
                    "description": "Database ID karyawan"
                },
                "month": {
                    "type": "integer",
                    "description": "Bulan (1-12). Kosongkan untuk semua periode."
                },
                "year": {
                    "type": "integer",
                    "description": "Tahun. Kosongkan untuk semua periode."
                }
            },
            "required": ["emp_id"]
        }
    },
    {
        "name": "get_payroll_info",
        "description": "Ambil informasi DETAIL penggajian karyawan dengan rincian lengkap tunjangan (transport, makan, perumahan, komunikasi) dan potongan (BPJS, PPh21, pinjaman, dll). Gunakan untuk pertanyaan detail tentang komponen gaji.",
        "parameters": {
            "type": "object",
            "properties": {
                "emp_id": {
                    "type": "integer",
                    "description": "Database ID karyawan"
                },
                "month": {
                    "type": "integer",
                    "description": "Bulan (1-12). Default: bulan terakhir yang tersedia."
                },
                "year": {
                    "type": "integer",
                    "description": "Tahun. Default: tahun terakhir yang tersedia."
                }
            },
            "required": ["emp_id"]
        }
    },
    {
        "name": "analyze_payroll_anomaly",
        "description": "Analisa ANOMALI penggajian menggunakan AI. Mendeteksi kenaikan/penurunan gaji tidak wajar, perbedaan antar karyawan, dan anomali komponen gaji. Gunakan untuk audit atau investigasi gaji.",
        "parameters": {
            "type": "object",
            "properties": {
                "emp_id": {
                    "type": "integer",
                    "description": "Database ID karyawan. Kosongkan untuk analisis semua karyawan.",
                    "default": None
                },
                "period_count": {
                    "type": "integer",
                    "description": "Jumlah periode terakhir untuk dianalisa (default: 6).",
                    "default": 6
                }
            },
            "required": []
        }
    },
    {
        "name": "export_payroll_csv",
        "description": "Export LAPORAN payroll ke file CSV untuk didownload. Bisa difilter berdasarkan departemen, bulan, dan tahun. Menghasilkan file CSV dengan tombol download.",
        "parameters": {
            "type": "object",
            "properties": {
                "department": {
                    "type": "string",
                    "description": "Filter departemen (opsional, kosongkan untuk semua)"
                },
                "month": {
                    "type": "integer",
                    "description": "Bulan filter (1-12, opsional)"
                },
                "year": {
                    "type": "integer",
                    "description": "Tahun filter (opsional, default: tahun ini)"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_payroll_file",
        "description": "Ambil FILE slip gaji karyawan (PDF) yang sudah ada. Mengembalikan link download file slip gaji.",
        "parameters": {
            "type": "object",
            "properties": {
                "emp_id": {
                    "type": "integer",
                    "description": "Database ID karyawan"
                },
                "month": {
                    "type": "integer",
                    "description": "Bulan (1-12, default: terakhir)"
                },
                "year": {
                    "type": "integer",
                    "description": "Tahun (default: terakhir)"
                }
            },
            "required": ["emp_id"]
        }
    },
    {
        "name": "create_payroll_report_pdf",
        "description": "BUAT slip gaji PDF baru untuk karyawan. Menggenerate dokumen PDF berisi rincian lengkap gaji, tunjangan, dan potongan.",
        "parameters": {
            "type": "object",
            "properties": {
                "emp_id": {
                    "type": "integer",
                    "description": "Database ID karyawan"
                },
                "month": {
                    "type": "integer",
                    "description": "Bulan (1-12, default: bulan ini)"
                },
                "year": {
                    "type": "integer",
                    "description": "Tahun (default: tahun ini)"
                }
            },
            "required": ["emp_id"]
        }
    },
    {
        "name": "send_payroll_email",
        "description": "KIRIM email slip gaji ke karyawan dengan lampiran PDF. Otomatis mencari file slip gaji yang ada, atau membuat baru jika belum tersedia. Gunakan untuk distribusi slip gaji via email.",
        "parameters": {
            "type": "object",
            "properties": {
                "emp_id": {
                    "type": "integer",
                    "description": "Database ID karyawan"
                },
                "month": {
                    "type": "integer",
                    "description": "Bulan (default: periode terakhir)"
                },
                "year": {
                    "type": "integer",
                    "description": "Tahun (default: tahun terakhir)"
                }
            },
            "required": ["emp_id"]
        }
    }
]
