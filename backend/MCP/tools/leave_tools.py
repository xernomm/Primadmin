"""
Leave management tools for HR Agent.
Provides functions to manage employee leave/cuti data.
Uses Oracle Database with SQLAlchemy.
"""
import os
import traceback
from typing import Dict, Any
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import cx_Oracle

load_dotenv()

ORACLE_USER = os.getenv("ORACLE_USER")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD")
ORACLE_HOST = os.getenv("ORACLE_HOST")
ORACLE_PORT = os.getenv("ORACLE_PORT")
ORACLE_SERVICE = os.getenv("ORACLE_SERVICE_NAME")

dsn = cx_Oracle.makedsn(ORACLE_HOST, ORACLE_PORT, service_name=ORACLE_SERVICE)
db_url = f"oracle+cx_oracle://{ORACLE_USER}:{ORACLE_PASSWORD}@{dsn}"
engine = create_engine(db_url)


def get_employee_leave_by_id(emp_id: int) -> Dict[str, Any]:
    """
    Retrieve leave data of employee by ID.
    
    Args:
        emp_id: Employee ID
        
    Returns:
        Dict with leave data or error
    """
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                SELECT id, name as employee_name, remaining_leave
                FROM employees
                WHERE id = :emp_id
            """), {"emp_id": emp_id}).fetchone()
            
            if result is None:
                return {"success": False, "error": f"Karyawan ID {emp_id} tidak ditemukan."}
            
            return {
                "success": True,
                "data": dict(result._mapping)
            }
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


def get_all_employee_leaves(limit: int = 100) -> Dict[str, Any]:
    """
    Retrieve leave data for all employees.
    
    Args:
        limit: Maximum number of rows (default: 100)
        
    Returns:
        Dict with leave data
    """
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                SELECT id, name, remaining_leave
                FROM employees
                FETCH FIRST :limit ROWS ONLY
            """), {"limit": limit}).fetchall()
            
            if not result:
                return {"success": True, "columns": [], "data": [], "count": 0}
            
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


def update_leaves(emp_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update leave data for an employee.
    
    Args:
        emp_id: Employee ID
        updates: Dict of field names and values to update
        
    Valid fields: remaining_leave, sick_leave, maternity_leave, unpaid_leave, other_leave
        
    Returns:
        Dict with success status and message
    """
    try:
        with engine.begin() as conn:
            # Filter valid updates
            if "remaining_leave" not in updates:
                return {"success": False, "error": "Hanya 'remaining_leave' yang dapat diperbarui melalui tool ini."}
                
            conn.execute(text("""
                UPDATE employees
                SET remaining_leave = :rem_leave
                WHERE id = :emp_id
            """), {"rem_leave": updates["remaining_leave"], "emp_id": emp_id})
            
            return {"success": True, "message": f"Sisa cuti karyawan ID {emp_id} berhasil diperbarui."}
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


# Tool definitions for agent
LEAVE_TOOLS = [
    {
        "name": "get_employee_leave_by_id",
        "description": "Mengambil STATUS CUTI karyawan spesifik. Menampilkan sisa cuti tahunan, dan kuota cuti lainnya.",
        "parameters": {
            "type": "object",
            "properties": {
                "emp_id": {
                    "type": "integer",
                    "description": "ID karyawan"
                }
            },
            "required": ["emp_id"]
        }
    },
    {
        "name": "get_all_employee_leaves",
        "description": "Laporan Sisa Cuti Seluruh Karyawan. Gunakan untuk overview kuota cuti.",
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
        "name": "update_leaves",
        "description": "Koreksi Sisa Cuti (Adjustment). Field valid: remaining_leave. Gunakan jika ada kesalahan perhitungan atau penambahan kuota manual.",
        "parameters": {
            "type": "object",
            "properties": {
                "emp_id": {
                    "type": "integer",
                    "description": "ID karyawan"
                },
                "updates": {
                    "type": "object",
                    "description": "Dictionary berisi field dan nilai cuti (Contoh: {'remaining_leave': 10})"
                }
            },
            "required": ["emp_id", "updates"]
        }
    }
]
