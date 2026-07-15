"""
Attendance management tools for HR Agent.
Provides functions to track and manage employee attendance.
Uses Oracle Database with cx_Oracle.
"""
import os
import cx_Oracle
import traceback
from typing import Dict, Any, Optional
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


def get_attendance(
    date: Optional[str] = None,
    status: Optional[str] = None,
    work_location: Optional[str] = None,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Mengambil data absensi karyawan dengan filter opsional tanggal, status, dan lokasi kerja.
    
    Args:
        date: Tanggal absensi dalam format YYYY-MM-DD (opsional, default: hari ini)
        status: Status kehadiran karyawan, misal 'late', 'ontime' (opsional)
        work_location: Lokasi kerja, misal 'Office', 'Remote' (opsional)
        limit: Jumlah maksimal baris hasil (default: 100)
        
    Returns:
        Dict berisi kolom dan data absensi
    """
    try:
        with engine.begin() as conn:
            sql = """
                SELECT a.id, e.name, a.attendance_date, a.work_location, a.check_in as timestamp, a.status, a.notes
                FROM attendance a
                JOIN employees e ON a.employee_id = e.id
                WHERE 1=1
            """
            params = {}
            
            if date:
                sql += " AND TRUNC(a.attendance_date) = TO_DATE(:attendance_date, 'YYYY-MM-DD')"
                params["attendance_date"] = date
            else:
                sql += " AND TRUNC(a.attendance_date) = TRUNC(SYSDATE)"
                
            if status:
                sql += " AND LOWER(a.status) = :status"
                params["status"] = status.lower()
                
            if work_location:
                sql += " AND LOWER(a.work_location) = :work_location"
                params["work_location"] = work_location.lower()
                
            sql += " ORDER BY a.check_in ASC FETCH FIRST :limit ROWS ONLY"
            params["limit"] = limit
            
            result = conn.execute(text(sql), params).fetchall()
            
            data = []
            for row in result:
                row_dict = dict(row._mapping)
                if row_dict.get("attendance_date") and hasattr(row_dict["attendance_date"], "strftime"):
                    row_dict["attendance_date"] = row_dict["attendance_date"].strftime("%Y-%m-%d")
                if row_dict.get("timestamp") and hasattr(row_dict["timestamp"], "strftime"):
                    row_dict["timestamp"] = row_dict["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                data.append(row_dict)
                
            columns = list(data[0].keys()) if data else []
            
            return {
                "success": True,
                "columns": list(columns),
                "data": data,
                "count": len(data)
            }
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


def get_today_attendance(limit: int = 100) -> Dict[str, Any]:
    """Legacy wrapper for backward compatibility."""
    return get_attendance(limit=limit)


def get_today_late_employees(limit: int = 100) -> Dict[str, Any]:
    """Legacy wrapper for backward compatibility."""
    return get_attendance(status='late', limit=limit)


def get_today_remote_employees(limit: int = 100) -> Dict[str, Any]:
    """Legacy wrapper for backward compatibility."""
    return get_attendance(work_location='remote', limit=limit)


def get_today_onsite_employees(limit: int = 100) -> Dict[str, Any]:
    """Legacy wrapper for backward compatibility."""
    return get_attendance(work_location='office', limit=limit)


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
        "name": "get_attendance",
        "description": "Mengambil log absensi karyawan secara fleksibel. Bisa difilter berdasarkan tanggal tertentu (date), status kehadiran (status: 'late', 'ontime', dll), maupun lokasi kerja (work_location: 'Office', 'Remote'). Berguna untuk monitoring absensi harian, keterlambatan, atau karyawan WFH/WFO.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Tanggal absensi format YYYY-MM-DD (opsional, default: hari ini)"
                },
                "status": {
                    "type": "string",
                    "description": "Status kehadiran: 'late' (terlambat), 'ontime' (tepat waktu) (opsional)"
                },
                "work_location": {
                    "type": "string",
                    "description": "Lokasi kerja: 'Office' (WFO), 'Remote' (WFH) (opsional)"
                },
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
