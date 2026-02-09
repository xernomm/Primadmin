"""
Attendance management tools for HR Agent.
Provides functions to track and manage employee attendance.
Uses Oracle Database with cx_Oracle.
"""
import os
import cx_Oracle
import traceback
from typing import Dict, Any
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

ORACLE_USER = os.getenv("ORACLE_USER")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD")
ORACLE_HOST = os.getenv("ORACLE_HOST")
ORACLE_PORT = os.getenv("ORACLE_PORT")
ORACLE_SERVICE = os.getenv("ORACLE_SERVICE_NAME")

dsn = cx_Oracle.makedsn(ORACLE_HOST, ORACLE_PORT, service_name=ORACLE_SERVICE)
db_url = f"oracle+cx_oracle://{ORACLE_USER}:{ORACLE_PASSWORD}@{dsn}"
engine = create_engine(db_url)


def _get_connection():
    """Get Oracle database connection."""
    return cx_Oracle.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=dsn)


def get_today_attendance(limit: int = 100) -> Dict[str, Any]:
    """
    Get today's attendance records.
    
    Args:
        limit: Maximum number of rows (default: 100)
        
    Returns:
        Dict with attendance data
    """
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                SELECT a.id, e.name, a.work_location, a.check_in as timestamp, a.status, a.notes
                FROM attendance a
                JOIN employees e ON a.employee_id = e.id
                WHERE TRUNC(a.attendance_date) = TRUNC(SYSDATE)
                ORDER BY a.check_in ASC
                FETCH FIRST :limit ROWS ONLY
            """), {"limit": limit}).fetchall()
            
            data = [dict(row._mapping) for row in result]
            columns = list(data[0].keys()) if data else []
            
            return {
                "success": True,
                "columns": list(columns),
                "data": data,
                "count": len(data)
            }
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


def get_today_late_employees(limit: int = 100) -> Dict[str, Any]:
    """
    List employees who were late today (check-in after 08:30).
    """
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                SELECT e.name, a.check_in as timestamp, a.work_location, a.status
                FROM attendance a
                JOIN employees e ON a.employee_id = e.id
                WHERE TRUNC(a.attendance_date) = TRUNC(SYSDATE)
                AND (a.status = 'late' OR (TO_CHAR(a.check_in, 'HH24:MI') > '08:30'))
                ORDER BY a.check_in ASC
                FETCH FIRST :limit ROWS ONLY
            """), {"limit": limit}).fetchall()
            
            data = [dict(row._mapping) for row in result]
            columns = list(data[0].keys()) if data else []
            
            return {
                "success": True,
                "columns": list(columns),
                "data": data,
                "count": len(data)
            }
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


def get_today_remote_employees(limit: int = 100) -> Dict[str, Any]:
    """
    Get employees working remotely today.
    """
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                SELECT e.name, a.check_in as timestamp, a.work_location, a.status
                FROM attendance a
                JOIN employees e ON a.employee_id = e.id
                WHERE TRUNC(a.attendance_date) = TRUNC(SYSDATE)
                AND a.work_location = 'Remote'
                ORDER BY a.check_in ASC
                FETCH FIRST :limit ROWS ONLY
            """), {"limit": limit}).fetchall()
            
            data = [dict(row._mapping) for row in result]
            columns = list(data[0].keys()) if data else []
            
            return {
                "success": True,
                "columns": list(columns),
                "data": data,
                "count": len(data)
            }
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


def get_today_onsite_employees(limit: int = 100) -> Dict[str, Any]:
    """
    Get employees working onsite today.
    """
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                SELECT e.name, a.check_in as timestamp, a.work_location, a.status
                FROM attendance a
                JOIN employees e ON a.employee_id = e.id
                WHERE TRUNC(a.attendance_date) = TRUNC(SYSDATE)
                AND a.work_location = 'Office'
                ORDER BY a.check_in ASC
                FETCH FIRST :limit ROWS ONLY
            """), {"limit": limit}).fetchall()
            
            data = [dict(row._mapping) for row in result]
            columns = list(data[0].keys()) if data else []
            
            return {
                "success": True,
                "columns": list(columns),
                "data": data,
                "count": len(data)
            }
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


def update_absensi(absen_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update attendance record by attendance ID.
    
    Args:
        absen_id: Attendance record ID
        updates: Dict of field names and values to update
        
    Valid fields (from DB schema): check_in, check_out, work_location, status, notes
        
    Returns:
        Dict with success status and message
    """
    try:
        with engine.begin() as conn:
            # Get valid columns
            columns_result = conn.execute(text("""
                SELECT column_name FROM all_tab_columns
                WHERE table_name = 'ATTENDANCE'
            """))
            valid_columns = [col[0].lower() for col in columns_result]
            
            # Additional allowed fields mapping to schema if needed
            # But strictly, we should use DB columns from db.py
            
            # Filter valid updates
            clean_updates = {
                k: v for k, v in updates.items()
                if k.lower() in valid_columns and k.lower() != "id"
            }
            
            # Allow 'timestamp' to map to 'check_in' for backward compatibility prompt
            if 'timestamp' in updates and 'check_in' not in updates:
                clean_updates['check_in'] = updates['timestamp']
            
            if not clean_updates:
                return {"success": False, "error": "Tidak ada kolom absensi valid yang diperbarui. Valid: check_in, check_out, work_location, status, notes"}
            
            # Build update query
            set_clause = ", ".join(f"{k} = :{k}" for k in clean_updates)
            clean_updates["absen_id"] = absen_id
            
            conn.execute(text(f"""
                UPDATE attendance
                SET {set_clause}
                WHERE id = :absen_id
            """), clean_updates)
            
            return {"success": True, "message": f"Data absensi ID {absen_id} berhasil diperbarui."}
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


# Tool definitions for agent
ATTENDANCE_TOOLS = [
    {
        "name": "get_today_attendance",
        "description": "Melihat log absensi HARI INI (Real-time). Menampilkan siapa saja yang sudah Check-in, Check-out, atau sedang istirahat hari ini.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Jumlah maksimal hasil (default: 100)",
                    "default": 100
                }
            },
            "required": []
        }
    },
    {
        "name": "get_today_late_employees",
        "description": "Mencari karyawan yang TERLAMBAT (Late) hari ini. Gunakan untuk monitoring kedisiplinan harian.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Jumlah maksimal hasil (default: 100)",
                    "default": 100
                }
            },
            "required": []
        }
    },
    {
        "name": "get_today_remote_employees",
        "description": "Mengambil daftar karyawan yang bekerja remote hari ini.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Jumlah maksimal hasil (default: 100)",
                    "default": 100
                }
            },
            "required": []
        }
    },
    {
        "name": "get_today_onsite_employees",
        "description": "Mengambil daftar karyawan yang bekerja onsite di kantor hari ini.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Jumlah maksimal hasil (default: 100)",
                    "default": 100
                }
            },
            "required": []
        }
    },
    {
        "name": "update_absensi",
        "description": "Koreksi data absensi manual. Memerlukan ID Absensi. Field valid: check_in, check_out, work_location, status, notes.",
        "parameters": {
            "type": "object",
            "properties": {
                "absen_id": {
                    "type": "integer",
                    "description": "ID record absensi"
                },
                "updates": {
                    "type": "object",
                    "description": "Dictionary berisi field dan nilai yang ingin diperbarui (Contoh: {'status': 'late', 'notes': 'Macet'})"
                }
            },
            "required": ["absen_id", "updates"]
        }
    }
]
