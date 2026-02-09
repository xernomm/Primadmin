"""
Employee management tools for HR Agent.
Provides functions to search, create, update, and delete employee data.
Uses Oracle Database with cx_Oracle.
"""
import os
import cx_Oracle
from datetime import datetime
import random
import traceback
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

load_dotenv()

ORACLE_USER = os.getenv("ORACLE_USER")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD")
ORACLE_HOST = os.getenv("ORACLE_HOST")
ORACLE_PORT = os.getenv("ORACLE_PORT")
ORACLE_SERVICE = os.getenv("ORACLE_SERVICE_NAME")

dsn = cx_Oracle.makedsn(ORACLE_HOST, ORACLE_PORT, service_name=ORACLE_SERVICE)


def _get_connection():
    """Get Oracle database connection."""
    return cx_Oracle.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=dsn)


def search_employees(query: str, limit: int = 20) -> Dict[str, Any]:
    """
    Search employees by name, email, or phone (partial match).
    
    Args:
        query: Search query string
        limit: Maximum number of results (default: 20)
        
    Returns:
        Dict with columns and data
    """
    try:
        conn = _get_connection()
        cur = conn.cursor()
        
        sql = """
            SELECT id, name, employee_code, position, status, 
                   basic_salary, phone, email, marital_status, department
            FROM employees
            WHERE LOWER(name) LIKE :query 
               OR LOWER(email) LIKE :query 
               OR phone LIKE :query
            FETCH FIRST :lim ROWS ONLY
        """
        search_pattern = f"%{query.lower()}%"
        cur.execute(sql, {"query": search_pattern, "lim": limit})
        
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return {
            "success": True,
            "columns": columns,
            "data": [dict(zip(columns, row)) for row in rows],
            "count": len(rows)
        }
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


def get_employee_by_id(emp_id: int) -> Dict[str, Any]:
    """
    Retrieve single employee and details by employee ID.
    
    Args:
        emp_id: Employee ID
        
    Returns:
        Employee dict or error
    """
    try:
        conn = _get_connection()
        cur = conn.cursor()
        
        sql = """
            SELECT id, name, employee_code, position, address, 
                   status, basic_salary, phone, email, marital_status, department,
                   remaining_leave, employment_status, joined_at
            FROM employees
            WHERE id = :emp_id
        """
        cur.execute(sql, {"emp_id": emp_id})
        cur.execute(sql, {"emp_id": emp_id})
        row = cur.fetchone()
        
        if row:
            columns = [desc[0] for desc in cur.description]
            result = {}
            for col, val in zip(columns, row):
                if isinstance(val, cx_Oracle.LOB):
                    result[col] = val.read()
                else:
                    result[col] = val
            
            cur.close()
            conn.close()
            return {"success": True, "data": result}
        else:
            cur.close()
            conn.close()
            return {"success": False, "error": f"Karyawan dengan ID {emp_id} tidak ditemukan."}
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


def get_all_employees(limit: int = 100) -> Dict[str, Any]:
    """
    Retrieve all employees with basic details.
    
    Args:
        limit: Maximum number of rows (default: 100)
        
    Returns:
        Dict with columns and data
    """
    try:
        conn = _get_connection()
        cur = conn.cursor()
        
        sql = """
            SELECT id, name, employee_code as employee_number, position, status, 
                   basic_salary as salary, phone, email, department
            FROM employees
            ORDER BY id ASC
            FETCH FIRST :lim ROWS ONLY
        """
        cur.execute(sql, {"lim": limit})
        
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return {
            "success": True,
            "columns": columns,
            "data": [dict(zip(columns, row)) for row in rows],
            "count": len(rows)
        }
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


def create_employee(name: str) -> Dict[str, Any]:
    """
    Create a new employee with auto-generated employee number.
    
    Args:
        name: Full name of the employee
        
    Returns:
        Dict with success status and employee info
    """
    try:
        now = datetime.now()
        random_number = random.randint(100, 999)
        employee_number = f"{now.year}-{now.month:02d}-{now.day:02d}-{random_number}"
        
        conn = _get_connection()
        cur = conn.cursor()
        
        emp_id_var = cur.var(cx_Oracle.NUMBER)
        cur.execute("""
            INSERT INTO employees (name, employee_code, email, department, position, joined_at)
            VALUES (:name, :code, :email, 'Unassigned', 'Staff', CURRENT_DATE) RETURNING id INTO :id
        """, {
            "name": name,
            "code": employee_number,
            "email": f"{name.lower().replace(' ', '.')}@company.com",
            "id": emp_id_var
        })
        
        emp_id = int(emp_id_var.getvalue()[0])
        conn.commit()
        
        cur.close()
        conn.close()
        
        return {
            "success": True,
            "message": f"Karyawan '{name}' berhasil ditambahkan.",
            "employee_id": emp_id,
            "employee_number": employee_number
        }
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


def update_employee_by_id(emp_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update employee details by ID.
    
    Args:
        emp_id: Employee ID
        updates: Dict of field names and values to update
        
    Valid fields: position, address, status, salary, phone, email, 
                  gender, marital, sp
        
    Returns:
        Dict with success status and message
    """
    try:
        conn = _get_connection()
        cur = conn.cursor()
        
        # Get valid columns
        cur.execute("SELECT * FROM employees WHERE ROWNUM = 1")
        valid_columns = set(desc[0].lower() for desc in cur.description if desc[0].lower() not in ["id", "employee_code"])
        
        clean_updates = {k: v for k, v in updates.items() if k.lower() in valid_columns}
        if not clean_updates:
            return {"success": False, "error": "Tidak ada kolom valid yang diperbarui."}
        
        clean_updates["emp_id"] = emp_id
        
        set_clause = ", ".join(f"{k} = :{k}" for k in clean_updates if k != "emp_id")
        cur.execute(f"UPDATE employees SET {set_clause} WHERE id = :emp_id", clean_updates)
        
        conn.commit()
        cur.close()
        conn.close()
        
        return {"success": True, "message": f"Data karyawan ID {emp_id} berhasil diperbarui."}
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


def delete_employee_by_id(emp_id: int) -> Dict[str, Any]:
    """
    Delete employee and all related data by employee ID.
    
    Args:
        emp_id: Employee ID to delete
        
    Returns:
        Dict with success status and message
    """
    try:
        conn = _get_connection()
        cur = conn.cursor()
        
        # Delete related data first
        cur.execute("DELETE FROM attendance WHERE employee_id = :id", {"id": emp_id})
        cur.execute("DELETE FROM warnings WHERE employee_id = :id", {"id": emp_id})
        
        # Delete employee
        cur.execute("DELETE FROM employees WHERE id = :id", {"id": emp_id})
        
        conn.commit()
        cur.close()
        conn.close()
        
        return {"success": True, "message": f"Karyawan ID {emp_id} berhasil dihapus beserta seluruh data terkait."}
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


def filter_employees_by_position(position: str, limit: int = 50) -> Dict[str, Any]:
    """
    Filter employees by job position.
    
    Args:
        position: Position to filter (partial match)
        limit: Maximum number of results
        
    Returns:
        Dict with columns and data
    """
    try:
        conn = _get_connection()
        cur = conn.cursor()
        
        sql = """
            SELECT id, name, position, status, basic_salary as salary, phone, email, department
            FROM employees
            WHERE LOWER(position) LIKE :pos
            FETCH FIRST :lim ROWS ONLY
        """
        cur.execute(sql, {"pos": f"%{position.lower()}%", "lim": limit})
        
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return {
            "success": True,
            "columns": columns,
            "data": [dict(zip(columns, row)) for row in rows],
            "count": len(rows)
        }
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


def filter_employees_by_status(status: str, limit: int = 50) -> Dict[str, Any]:
    """
    Filter employees by employment status.
    
    Args:
        status: Status to filter (exact match: tetap, kontrak, magang)
        limit: Maximum number of results
        
    Returns:
        Dict with columns and data
    """
    try:
        conn = _get_connection()
        cur = conn.cursor()
        
        sql = """
            SELECT id, name, position, status, employment_status, basic_salary as salary, phone, email, department
            FROM employees
            WHERE LOWER(status) = :stat OR LOWER(employment_status) = :stat
            FETCH FIRST :lim ROWS ONLY
        """
        cur.execute(sql, {"stat": status.lower(), "lim": limit})
        
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return {
            "success": True,
            "columns": columns,
            "data": [dict(zip(columns, row)) for row in rows],
            "count": len(rows)
        }
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


def filter_employees_salary_above(min_salary: float, limit: int = 50) -> Dict[str, Any]:
    """
    Filter employees with salary above threshold.
    
    Args:
        min_salary: Minimum salary threshold
        limit: Maximum number of results
        
    Returns:
        Dict with columns and data
    """
    try:
        conn = _get_connection()
        cur = conn.cursor()
        
        sql = """
            SELECT id, name, position, status, basic_salary as salary, phone, email, department
            FROM employees
            WHERE basic_salary >= :min_sal
            ORDER BY basic_salary DESC
            FETCH FIRST :lim ROWS ONLY
        """
        cur.execute(sql, {"min_sal": min_salary, "lim": limit})
        
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return {
            "success": True,
            "columns": columns,
            "data": [dict(zip(columns, row)) for row in rows],
            "count": len(rows)
        }
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


def filter_employees_salary_below(max_salary: float, limit: int = 50) -> Dict[str, Any]:
    """
    Filter employees with salary below threshold.
    
    Args:
        max_salary: Maximum salary threshold
        limit: Maximum number of results
        
    Returns:
        Dict with columns and data
    """
    try:
        conn = _get_connection()
        cur = conn.cursor()
        
        sql = """
            SELECT id, name, position, status, basic_salary as salary
            FROM employees
            WHERE basic_salary <= :max_sal
            ORDER BY basic_salary ASC
            FETCH FIRST :lim ROWS ONLY
        """
        cur.execute(sql, {"max_sal": max_salary, "lim": limit})
        
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return {
            "success": True,
            "columns": columns,
            "data": [dict(zip(columns, row)) for row in rows],
            "count": len(rows)
        }
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


# Tool definitions for agent
# IMPORTANT: Parameter names MUST match function signatures exactly!
# - 'id' = internal database ID (auto-generated integer)
# - 'employee_code' = business identifier/NIK (string like "2026-01-15-123")
# Do NOT confuse these two identifiers!

EMPLOYEE_TOOLS = [
    {
        "name": "search_employees",
        "description": "Mencari data karyawan secara fleksibel (Fuzzy Search). Gunakan tool ini untuk mencari berdasarkan nama, email, atau telepon. PENTING: Tool ini mengembalikan 'id' (database ID integer) yang digunakan untuk tool lainnya.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Kata kunci pencarian (nama, email, atau telepon). Contoh: 'Budi', 'budi@company.com'"
                },
                "limit": {
                    "type": "integer",
                    "description": "Jumlah maksimal hasil (default: 20)",
                    "default": 20
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_employee_by_id",
        "description": "Mengambil DETAIL LENGKAP satu karyawan. WAJIB dipanggil setelah search_employees untuk mendapatkan informasi lengkap seperti gaji, alamat, BPJS, sisa cuti, dll. Parameter: emp_id (integer dari hasil search).",
        "parameters": {
            "type": "object",
            "properties": {
                "emp_id": {
                    "type": "integer",
                    "description": "Database ID karyawan (integer). Dapatkan dari hasil search_employees field 'id' atau 'ID'."
                }
            },
            "required": ["emp_id"]
        }
    },
    {
        "name": "get_all_employees",
        "description": "Mengambil daftar SEMUA karyawan dengan info dasar. Gunakan jika user meminta 'daftar semua karyawan' atau statistik keseluruhan.",
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
        "name": "create_employee",
        "description": "Membuat data karyawan BARU (onboarding). Otomatis membuat employee_code unik.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Nama lengkap karyawan baru. Contoh: 'Budi Santoso'"
                }
            },
            "required": ["name"]
        }
    },
    {
        "name": "update_employee_by_id",
        "description": "Update data karyawan. HARUS gunakan emp_id (database ID integer), BUKAN employee_code. Field valid: position, address, status, basic_salary, phone, email, marital_status, department.",
        "parameters": {
            "type": "object",
            "properties": {
                "emp_id": {
                    "type": "integer",
                    "description": "Database ID karyawan (integer). BUKAN employee_code! Dapatkan dari search_employees."
                },
                "updates": {
                    "type": "object",
                    "description": "Object berisi field dan nilai baru. Contoh: {\"position\": \"Manager\", \"basic_salary\": 15000000}"
                }
            },
            "required": ["emp_id", "updates"]
        }
    },
    {
        "name": "delete_employee_by_id",
        "description": "Menghapus karyawan dan SEMUA data terkait (absensi, warning, cuti). Operasi ini PERMANEN.",
        "parameters": {
            "type": "object",
            "properties": {
                "emp_id": {
                    "type": "integer",
                    "description": "Database ID karyawan (integer) yang akan dihapus."
                }
            },
            "required": ["emp_id"]
        }
    },
    {
        "name": "filter_employees_by_position",
        "description": "Filter karyawan berdasarkan jabatan/posisi (partial match).",
        "parameters": {
            "type": "object",
            "properties": {
                "position": {
                    "type": "string",
                    "description": "Jabatan yang dicari. Contoh: 'Manager', 'Staff', 'Developer'"
                },
                "limit": {
                    "type": "integer",
                    "description": "Jumlah maksimal hasil (default: 50)",
                    "default": 50
                }
            },
            "required": ["position"]
        }
    },
    {
        "name": "filter_employees_by_status",
        "description": "Filter karyawan berdasarkan status kepegawaian.",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Status: 'active', 'inactive', 'terminated'"
                },
                "limit": {
                    "type": "integer",
                    "description": "Jumlah maksimal hasil (default: 50)",
                    "default": 50
                }
            },
            "required": ["status"]
        }
    },
    {
        "name": "filter_employees_salary_above",
        "description": "Filter karyawan dengan gaji >= threshold.",
        "parameters": {
            "type": "object",
            "properties": {
                "min_salary": {
                    "type": "number",
                    "description": "Batas minimum gaji. Contoh: 10000000"
                },
                "limit": {
                    "type": "integer",
                    "description": "Jumlah maksimal hasil (default: 50)",
                    "default": 50
                }
            },
            "required": ["min_salary"]
        }
    },
    {
        "name": "filter_employees_salary_below",
        "description": "Filter karyawan dengan gaji <= threshold.",
        "parameters": {
            "type": "object",
            "properties": {
                "max_salary": {
                    "type": "number",
                    "description": "Batas maksimum gaji. Contoh: 5000000"
                },
                "limit": {
                    "type": "integer",
                    "description": "Jumlah maksimal hasil (default: 50)",
                    "default": 50
                }
            },
            "required": ["max_salary"]
        }
    }
]
