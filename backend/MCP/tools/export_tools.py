"""
Export tools for HR Agent.
Provides CSV export functionality for employee data with download widget support.
"""
import os
import csv
import traceback
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import cx_Oracle
from dotenv import load_dotenv

load_dotenv()

ORACLE_USER = os.getenv("ORACLE_USER")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD")
ORACLE_HOST = os.getenv("ORACLE_HOST")
ORACLE_PORT = os.getenv("ORACLE_PORT")
ORACLE_SERVICE = os.getenv("ORACLE_SERVICE_NAME")

dsn = cx_Oracle.makedsn(ORACLE_HOST, ORACLE_PORT, service_name=ORACLE_SERVICE)

# Export directory — import from centralized config
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config import EXPORTS_DIR as EXPORT_DIR


def _get_connection():
    """Get Oracle database connection."""
    return cx_Oracle.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=dsn)


def _format_file_size(size_bytes: int) -> str:
    """Format bytes to human readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def export_employee_personal_data(department: str = None) -> Dict[str, Any]:
    """
    Export data pribadi karyawan ke file CSV.
    
    Data yang diekspor:
    - employee_code, name, email, phone
    - department, position, status
    - address, marital_status
    - bpjs_number, employment_status
    - joined_at
    
    Args:
        department: Filter departemen (opsional, None = semua karyawan)
        
    Returns:
        Dict with file path, download URL, and widget data for frontend
    """
    try:
        conn = _get_connection()
        cur = conn.cursor()
        
        # Build query
        if department:
            cur.execute("""
                SELECT employee_code, name, email, phone, department, position, status,
                       address, marital_status, bpjs_number, employment_status, joined_at
                FROM employees
                WHERE LOWER(department) = LOWER(:dept)
                ORDER BY name
            """, {"dept": department})
        else:
            cur.execute("""
                SELECT employee_code, name, email, phone, department, position, status,
                       address, marital_status, bpjs_number, employment_status, joined_at
                FROM employees
                ORDER BY name
            """)
        
        rows = cur.fetchall()
        columns = [
            "employee_code", "name", "email", "phone", "department", "position", "status",
            "address", "marital_status", "bpjs_number", "employment_status", "joined_at"
        ]
        
        if not rows:
            cur.close()
            conn.close()
            return {
                "success": False,
                "error": f"Tidak ada data karyawan ditemukan{' di departemen ' + department if department else ''}."
            }
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        dept_suffix = f"_{department.lower().replace(' ', '_')}" if department else ""
        filename = f"employee_personal{dept_suffix}_{timestamp}.csv"
        filepath = EXPORT_DIR / filename
        
        # Write CSV
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            for row in rows:
                # Convert datetime to string
                row_data = list(row)
                if row_data[11]:  # joined_at
                    row_data[11] = row_data[11].strftime("%Y-%m-%d") if hasattr(row_data[11], 'strftime') else str(row_data[11])
                
                # Handle CLOB fields (address is at index 7)
                if row_data[7] and isinstance(row_data[7], cx_Oracle.LOB):
                    row_data[7] = row_data[7].read()
                
                writer.writerow(row_data)
        
        cur.close()
        conn.close()
        
        # Get file size
        file_size = os.path.getsize(filepath)
        
        return {
            "success": True,
            "message": f"Data pribadi {len(rows)} karyawan berhasil diekspor.",
            "file_path": str(filepath),
            "download_url": f"/api/exports/{filename}",
            "filename": filename,
            "row_count": len(rows),
            "department_filter": department,
            "widget": {
                "type": "download",
                "filename": filename,
                "size": _format_file_size(file_size),
                "icon": "csv",
                "download_url": f"/api/exports/{filename}"
            }
        }
        
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


def export_employee_operational_data(
    period: str = "all",
    year: int = None,
    month: int = None
) -> Dict[str, Any]:
    """
    Export data operasional karyawan ke file CSV.
    
    Data yang diekspor:
    - employee_code, name, department
    - remaining_leave (sisa cuti)
    - Total absensi: on-time, late, absent, remote
    
    Args:
        period: "monthly", "yearly", atau "all" (jika user menyebut nama bulan seperti "January", akan dikonversi ke "monthly")
        year: Tahun untuk filter (opsional, default: tahun ini)
        month: Bulan untuk filter 1-12 (opsional, hanya untuk period="monthly")
        
    Returns:
        Dict with file path, download URL, and widget data for frontend
    """
    try:
        conn = _get_connection()
        cur = conn.cursor()
        
        # Default to current year/month
        now = datetime.now()
        if year is None:
            year = now.year
        if month is None:
            month = now.month
        
        # Normalize period parameter (handle month names from LLM)
        month_names = {
            "january": 1, "february": 2, "march": 3, "april": 4,
            "may": 5, "june": 6, "july": 7, "august": 8,
            "september": 9, "october": 10, "november": 11, "december": 12,
            "januari": 1, "februari": 2, "maret": 3, "april": 4,
            "mei": 5, "juni": 6, "juli": 7, "agustus": 8,
            "september": 9, "oktober": 10, "november": 11, "desember": 12
        }
        
        period_lower = period.lower().strip() if period else "all"
        
        # Check if period is a month name
        if period_lower in month_names:
            month = month_names[period_lower]
            period = "monthly"
        elif period_lower not in ["monthly", "yearly", "all"]:
            # Default to "all" for unrecognized values
            period = "all"
        else:
            period = period_lower
        
        # Build date filter
        if period == "monthly":
            date_filter = """
                AND EXTRACT(YEAR FROM a.attendance_date) = :year
                AND EXTRACT(MONTH FROM a.attendance_date) = :month
            """
            params = {"year": year, "month": month}
            period_label = f"{year}-{month:02d}"
        elif period == "yearly":
            date_filter = "AND EXTRACT(YEAR FROM a.attendance_date) = :year"
            params = {"year": year}
            period_label = str(year)
        else:
            date_filter = ""
            params = {}
            period_label = "all_time"
        
        # Main query with attendance statistics
        query = f"""
            SELECT 
                e.employee_code,
                e.name,
                e.department,
                e.remaining_leave,
                e.sp_level,
                COUNT(a.id) as total_attendance,
                SUM(CASE WHEN a.status = 'on-time' THEN 1 ELSE 0 END) as ontime_count,
                SUM(CASE WHEN a.status = 'late' THEN 1 ELSE 0 END) as late_count,
                SUM(CASE WHEN a.status = 'absent' THEN 1 ELSE 0 END) as absent_count,
                SUM(CASE WHEN a.work_location = 'Remote' THEN 1 ELSE 0 END) as remote_count
            FROM employees e
            LEFT JOIN attendance a ON e.id = a.employee_id {date_filter}
            WHERE e.status = 'active'
            GROUP BY e.employee_code, e.name, e.department, e.remaining_leave, e.sp_level
            ORDER BY e.name
        """
        
        cur.execute(query, params)
        rows = cur.fetchall()
        
        columns = [
            "employee_code", "name", "department", "remaining_leave", "sp_level",
            "total_attendance", "ontime_count", "late_count", "absent_count", "remote_count"
        ]
        
        cur.close()
        conn.close()
        
        if not rows:
            return {"success": False, "error": "Tidak ada data karyawan aktif ditemukan."}
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        filename = f"employee_operational_{period_label}_{timestamp}.csv"
        filepath = EXPORT_DIR / filename
        
        # Write CSV
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            for row in rows:
                row_data = list(row)
                # Handle None values
                row_data = [0 if val is None else val for val in row_data]
                writer.writerow(row_data)
        
        # Get file size
        file_size = os.path.getsize(filepath)
        
        return {
            "success": True,
            "message": f"Data operasional {len(rows)} karyawan berhasil diekspor ({period}: {period_label}).",
            "file_path": str(filepath),
            "download_url": f"/api/exports/{filename}",
            "filename": filename,
            "row_count": len(rows),
            "period": period,
            "period_label": period_label,
            "widget": {
                "type": "download",
                "filename": filename,
                "size": _format_file_size(file_size),
                "icon": "csv",
                "download_url": f"/api/exports/{filename}"
            }
        }
        
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


# Tool definitions for agent
EXPORT_TOOLS = [
    {
        "name": "export_employee_personal_data",
        "description": """EKSPOR / EXPORT DATA KARYAWAN ke file CSV - Data Pribadi/Personal.

🎯 GUNAKAN TOOL INI KETIKA USER MEMINTA:
- "export data karyawan" / "ekspor data karyawan"
- "download data karyawan" / "download CSV karyawan"
- "buat laporan karyawan" / "rekap data karyawan"
- "export semua karyawan" / "list karyawan ke file"

📋 DATA YANG DIEKSPOR:
- employee_code (NIK/nomor karyawan)
- name (nama lengkap)
- email, phone (kontak)
- department, position, status
- address, marital_status
- bpjs_number, employment_status
- joined_at (tanggal bergabung)

💾 OUTPUT: File CSV yang bisa didownload langsung oleh user melalui widget download di chat.""",
        "parameters": {
            "type": "object",
            "properties": {
                "department": {
                    "type": "string",
                    "description": "Filter berdasarkan departemen (contoh: 'IT', 'HR', 'Finance'). Kosongkan atau null untuk export SEMUA karyawan dari semua departemen.",
                    "default": None
                }
            },
            "required": []
        }
    },
    {
        "name": "export_employee_operational_data",
        "description": """EKSPOR / EXPORT DATA OPERASIONAL KARYAWAN ke file CSV - Absensi & Cuti.

🎯 GUNAKAN TOOL INI KETIKA USER MEMINTA:
- "export rekap absensi" / "ekspor data kehadiran"
- "download laporan absensi" / "rekap absensi ke CSV"
- "export data cuti karyawan"
- "laporan operasional karyawan"
- "rekap keterlambatan" / "export data telat"

📋 DATA YANG DIEKSPOR:
- employee_code, name, department
- remaining_leave (sisa cuti)
- sp_level (level surat peringatan: 0=tidak ada, 1=SP1, 2=SP2, 3=SP3/pemecatan)
- total_attendance (total record absensi)
- ontime_count (jumlah tepat waktu)
- late_count (jumlah terlambat)
- absent_count (jumlah absen)
- remote_count (jumlah WFH/remote)

📅 FILTER PERIODE:
- period="monthly" + month=1-12 untuk bulan tertentu
- period="yearly" + year untuk tahun tertentu
- period="all" untuk semua data

💾 OUTPUT: File CSV yang bisa didownload langsung oleh user melalui widget download di chat.""",
        "parameters": {
            "type": "object",
            "properties": {
                "period": {
                    "type": "string",
                    "enum": ["monthly", "yearly", "all"],
                    "description": "Periode filter: 'monthly' (per bulan), 'yearly' (per tahun), 'all' (semua waktu). Jika user menyebut nama bulan seperti 'Januari' atau 'January', gunakan 'monthly' dan set month yang sesuai.",
                    "default": "all"
                },
                "year": {
                    "type": "integer",
                    "description": "Tahun untuk filter. Contoh: 2026, 2025. Default: tahun sekarang.",
                    "default": None
                },
                "month": {
                    "type": "integer",
                    "description": "Bulan 1-12 untuk filter period='monthly'. Contoh: 1=Januari, 2=Februari, dst. Default: bulan sekarang.",
                    "default": None
                }
            },
            "required": []
        }
    }
]
