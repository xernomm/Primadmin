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

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config import CV_DIR, PAYROLL_EXPORTS_DIR, BASE_URL

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
                   basic_salary, phone, email, marital_status, department, sp_level
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
    Also includes CV file info (file_path, education, skills) from employee_cv table.
    
    Args:
        emp_id: Employee ID
        
    Returns:
        Employee dict with cv_info sub-dict, or error
    """
    try:
        conn = _get_connection()
        cur = conn.cursor()
        
        # Main employee data
        sql = """
            SELECT id, name, employee_code, position, address, 
                   status, basic_salary, phone, email, marital_status, department,
                   remaining_leave, employment_status, sp_level, bpjs_number, 
                   joined_at, created_at, updated_at
            FROM employees
            WHERE id = :emp_id
        """
        cur.execute(sql, {"emp_id": emp_id})
        row = cur.fetchone()
        
        if not row:
            cur.close()
            conn.close()
            return {"success": False, "error": f"Karyawan dengan ID {emp_id} tidak ditemukan."}

        columns = [desc[0] for desc in cur.description]
        result = {}
        for col, val in zip(columns, row):
            if isinstance(val, cx_Oracle.LOB):
                result[col] = val.read()
            else:
                result[col] = val

        # Also fetch CV info (file path + key fields)
        try:
            cur.execute("""
                SELECT file_path, education_level, education_institution, education_major,
                       skills, certifications, work_experience, 
                       current_position, current_department, current_salary,
                       bank_name, bank_account_number, bank_account_name,
                       ktp_number, npwp_number, blood_type, religion,
                       notes
                FROM employee_cv
                WHERE employee_id = :emp_id
            """, {"emp_id": emp_id})
            cv_row = cur.fetchone()
            if cv_row:
                cv_cols = [desc[0] for desc in cur.description]
                cv_data = {}
                for col, val in zip(cv_cols, cv_row):
                    if isinstance(val, cx_Oracle.LOB):
                        cv_data[col] = val.read()
                    else:
                        cv_data[col] = val
                result["CV_FILE_PATH"] = cv_data.get("FILE_PATH")  # top-level for easy access
                result["cv_info"] = cv_data
            else:
                result["CV_FILE_PATH"] = None
                result["cv_info"] = None
        except Exception:
            result["CV_FILE_PATH"] = None
            result["cv_info"] = None

        cur.close()
        conn.close()
        return {"success": True, "data": result}

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


# Columns that belong to the employee_cv table (not employees)
CV_TABLE_COLUMNS = {
    "education_level", "education_institution", "education_major", "graduation_year",
    "certifications", "skills", "work_experience",
    "current_position", "current_department", "current_salary",
    "emergency_contact_name", "emergency_contact_phone", "emergency_contact_relation",
    "blood_type", "religion", "ktp_number", "npwp_number",
    "bank_name", "bank_account_number", "bank_account_name",
    "deduction_bpjs_kesehatan", "deduction_bpjs_ketenagakerjaan",
    "deduction_meal", "deduction_transport", "deduction_insurance",
    "deduction_laptop_installment", "deduction_laptop_remaining_months",
    "deduction_other", "deduction_other_description", "total_monthly_deductions",
    "notes", "file_path"
}


def update_employee_by_id(emp_id: int, updates: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
    """
    Update employee details by ID.
    Supports fields from the 'employees' table.
    
    Args:
        emp_id: Employee ID
        updates: Dict of field names and values to update (optional)
        **kwargs: The columns to update, directly as keyword arguments
        
    Valid employees fields: position, address, status, basic_salary, phone, email,
                            marital_status, department, employment_status, sp_level,
                            remaining_leave, bpjs_number, joined_at
        
    Returns:
        Dict with success status and message
    """
    actual_updates = updates or {}
    actual_updates.update({k: v for k, v in kwargs.items() if v is not None})
    
    # Guard: must be a non-empty dict
    if not actual_updates:
        return {
            "success": False,
            "error": "Parameter update tidak boleh kosong. Pastikan field dan nilai yang ingin diupdate sudah ditentukan."
        }
    
    # Oracle ORA-01484 fix: Ensure no lists/arrays are passed as bound values to standard SQL
    # Convert lists to comma-separated strings
    for k, v in actual_updates.items():
        if isinstance(v, list):
            actual_updates[k] = ", ".join(map(str, v))

    try:
        conn = _get_connection()
        cur = conn.cursor()
        
        # Get valid columns for employees table (dynamically)
        cur.execute("SELECT * FROM employees WHERE ROWNUM = 1")
        valid_emp_columns = set(
            desc[0].lower() for desc in cur.description
            if desc[0].lower() not in ["id", "employee_code"]
        )
        emp_updates = {k: v for k, v in actual_updates.items() if k.lower() in valid_emp_columns}
        
        if not emp_updates:
            cur.close()
            conn.close()
            return {"success": False, "error": "Tidak ada kolom valid yang diperbarui. Periksa nama field yang diberikan."}
        
        messages = []
        
        # --- Update employees table ---
        if emp_updates:
            emp_updates["emp_id"] = emp_id
            set_clause = ", ".join(f"{k} = :{k}" for k in emp_updates if k != "emp_id")
            cur.execute(f"UPDATE employees SET {set_clause} WHERE id = :emp_id", emp_updates)
            messages.append(f"{len(emp_updates) - 1} field tabel employees")
        
        conn.commit()

        # -- Re-fetch actual committed values so Stage 4 can verify without hallucinating --
        updated_data = {}
        try:
            if emp_updates:
                fields = [k for k in emp_updates if k != "emp_id"]
                cur.execute(
                    f"SELECT {', '.join(fields)} FROM employees WHERE id = :eid",
                    {"eid": emp_id}
                )
                row = cur.fetchone()
                if row:
                    for i, field in enumerate(fields):
                        val = row[i]
                        updated_data[field] = val.read() if hasattr(val, "read") else val
        except Exception:
            pass  # non-critical

        cur.close()
        conn.close()

        return {
            "success": True,
            "message": f"Data karyawan ID {emp_id} berhasil diperbarui: {', '.join(messages)}.",
            "updated_fields": updated_data  # actual values now in DB — source of truth for verification
        }
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


def get_employee_files(emp_id: int) -> Dict[str, Any]:
    """
    Ambil daftar semua file penting yang terkait satu karyawan:
    - File CV (dari employee_cv.file_path + download_url)
    - File slip gaji/payroll (dari payroll_slips.file_path + download_url)

    Args:
        emp_id: Database ID karyawan

    Returns:
        Dict berisi list file CV dan payroll dengan server_url dan abs_path.
        Gunakan abs_path untuk extract_cv_from_file.
    """
    try:
        conn = _get_connection()
        cur = conn.cursor()

        # Verify employee exists
        cur.execute("SELECT name FROM employees WHERE id = :emp_id", {"emp_id": emp_id})
        emp = cur.fetchone()
        if not emp:
            cur.close(); conn.close()
            return {"success": False, "error": f"Karyawan dengan ID {emp_id} tidak ditemukan."}

        emp_name = emp[0]
        files = {}

        # --- CV file (from employee_cv table) ---
        cur.execute(
            "SELECT file_path, download_url FROM employee_cv WHERE employee_id = :eid",
            {"eid": emp_id}
        )
        cv_row = cur.fetchone()
        if cv_row:
            cv_abs_raw = cv_row[0]  # raw value from DB (could be path or URL)
            cv_url = cv_row[1]  # server URL stored in DB
            
            # Resolve absolute path
            from config import url_to_abs_path
            resolved = url_to_abs_path(str(cv_abs_raw)) if cv_abs_raw else None
            cv_abs = str(resolved) if resolved else (cv_abs_raw if cv_abs_raw and not str(cv_abs_raw).startswith("http") else None)
            
            cv_exists = Path(str(cv_abs)).exists() if cv_abs else False

            # Build server URL if download_url not stored yet
            if not cv_url and cv_abs:
                filename = Path(str(cv_abs)).name
                cv_url = f"{BASE_URL}/uploads/cv/{filename}"

            files["cv"] = {
                "filename": Path(str(cv_abs)).name if cv_abs else None,
                "abs_path": str(cv_abs) if cv_abs else None,
                "server_url": cv_url,
                "exists": cv_exists,
            }
        else:
            files["cv"] = None

        # --- Payroll slip files (from payroll_slips table) ---
        cur.execute("""
            SELECT period_month, period_year, file_path, download_url, status
            FROM payroll_slips
            WHERE employee_id = :eid
            ORDER BY period_year DESC, period_month DESC
            FETCH FIRST 12 ROWS ONLY
        """, {"eid": emp_id})
        payroll_rows = cur.fetchall()
        payroll_files = []
        for row in payroll_rows:
            month, year, fp_raw, du, st = row
            from config import url_to_abs_path
            resolved_fp = url_to_abs_path(str(fp_raw)) if fp_raw else None
            abs_path = str(resolved_fp) if resolved_fp else (fp_raw if fp_raw and not str(fp_raw).startswith("http") else None)
            
            server_url = du if du else (f"{BASE_URL}/uploads/payroll/{Path(fp_raw).name}" if fp_raw else None)
            payroll_files.append({
                "period": f"{year}-{str(month).zfill(2)}",
                "filename": Path(str(abs_path)).name if abs_path else (Path(str(fp_raw)).name if fp_raw else None),
                "abs_path": abs_path,
                "server_url": server_url,
                "exists": Path(str(abs_path)).exists() if abs_path else False,
                "status": st,
            })
        files["payroll_slips"] = payroll_files

        cur.close(); conn.close()

        return {
            "success": True,
            "employee_id": emp_id,
            "employee_name": emp_name,
            "files": files,
            "hint": "Gunakan 'abs_path' dari files.cv atau files.payroll_slips sebagai file_path di extract_cv_from_file / get_payroll_file."
        }

    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


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
        "description": "Mengambil DETAIL LENGKAP satu karyawan. WAJIB dipanggil setelah search_employees untuk mendapatkan informasi lengkap seperti gaji, alamat, BPJS, sisa cuti, dll. PENTING: Output juga menyertakan 'CV_FILE_PATH' (path file CV, gunakan sebagai file_path di extract_cv_from_file) dan 'cv_info' (data profil CV: pendidikan, skill, sertifikasi, dll). Gunakan {{step_N.result.data.CV_FILE_PATH}} untuk file_path di step berikutnya.",
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
        "description": "UPDATE data UTAMA karyawan (hanya tabel employees). HARUS gunakan emp_id (database ID integer). Gunakan tool ini HANYA untuk update informasi inti pegawai seperti: posisi, departemen, alamat, gaji pokok (basic_salary), email, telepon, status pernikahan, status kepegawaian, BPJS number, sisa cuti, dan tanggal bergabung. DILARANG menggunakan tool ini untuk data CV atau potongan gaji bulanan (gunakan update_employee_cv untuk itu).",
        "parameters": {
            "type": "object",
            "properties": {
                "emp_id": {
                    "type": "integer",
                    "description": "Database ID karyawan (integer). BUKAN employee_code! Dapatkan dari search_employees."
                },
                "position": {"type": "string", "description": "Jabatan/Posisi (contoh: 'Manager')"},
                "department": {"type": "string", "description": "Departemen (contoh: 'IT')"},
                "status": {"type": "string", "description": "Status karyawan (contoh: 'active')"},
                "employment_status": {"type": "string", "description": "Status kepegawaian (contoh: 'Tetap', 'Kontrak')"},
                "basic_salary": {"type": "number", "description": "Gaji Pokok (angka)"},
                "phone": {"type": "string", "description": "Nomor Telepon"},
                "email": {"type": "string", "description": "Alamat Email"},
                "address": {"type": "string", "description": "Alamat Lengkap"},
                "marital_status": {"type": "string", "description": "Status Pernikahan (contoh: 'Menikah', 'Belum Menikah')"},
                "sp_level": {"type": "integer", "description": "Tingkat Surat Peringatan (SP) 0-3"},
                "remaining_leave": {"type": "integer", "description": "Sisa Cuti (hari)"},
                "bpjs_number": {"type": "string", "description": "Nomor Kartu BPJS (Bukan nilai potongan uangnya)"},
                "joined_at": {"type": "string", "description": "Tanggal Bergabung (format YYYY-MM-DD)"}
            },
            "required": ["emp_id"]
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
    },
    {
        "name": "get_employee_files",
        "description": (
            "Ambil daftar semua file penting milik satu karyawan: file CV (dari employee_cv) "
            "dan slip gaji/payroll (dari payroll_slips). Mengembalikan 'abs_path' dan 'server_url' "
            "untuk setiap file. WAJIB dipanggil sebelum extract_cv_from_file atau get_payroll_file "
            "agar path file yang digunakan AKURAT — jangan hardcode path atau tebak nama file."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "emp_id": {
                    "type": "integer",
                    "description": "Database ID karyawan (integer dari search_employees)."
                }
            },
            "required": ["emp_id"]
        }
    }
]
