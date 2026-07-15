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


def search_employees(
    query: Optional[str] = None,
    position: Optional[str] = None,
    department: Optional[str] = None,
    status: Optional[str] = None,
    min_salary: Optional[float] = None,
    max_salary: Optional[float] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Mencari data karyawan secara fleksibel dan melakukan filter dinamis.
    
    Args:
        query: Kata kunci pencarian nama, email, atau telepon (opsional)
        position: Jabatan karyawan (opsional)
        department: Departemen karyawan (opsional)
        status: Status karyawan, misal 'active' (opsional)
        min_salary: Gaji minimum (opsional)
        max_salary: Gaji maksimum (opsional)
        limit: Jumlah maksimal hasil (default: 20)
        
    Returns:
        Dict dengan kolom dan data hasil filter
    """
    try:
        conn = _get_connection()
        cur = conn.cursor()
        
        sql = """
            SELECT id, name, employee_code, position, status, 
                   basic_salary, phone, email, marital_status, department, sp_level, remaining_leave
            FROM employees
            WHERE 1=1
        """
        params = {}
        
        if query:
            sql += " AND (LOWER(name) LIKE :query OR LOWER(email) LIKE :query OR phone LIKE :query)"
            params["query"] = f"%{query.lower()}%"
            
        if position:
            sql += " AND LOWER(position) = :position"
            params["position"] = position.lower()
            
        if department:
            sql += " AND LOWER(department) = :department"
            params["department"] = department.lower()
            
        if status:
            sql += " AND LOWER(status) = :status"
            params["status"] = status.lower()
            
        if min_salary is not None:
            sql += " AND basic_salary >= :min_salary"
            params["min_salary"] = float(min_salary)
            
        if max_salary is not None:
            sql += " AND basic_salary <= :max_salary"
            params["max_salary"] = float(max_salary)
            
        sql += " ORDER BY id ASC FETCH FIRST :lim ROWS ONLY"
        params["lim"] = limit
        
        cur.execute(sql, params)
        
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
    Retrieve all employees with basic details, remaining leave, and SP level.
    
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
                   basic_salary as salary, phone, email, department, remaining_leave, sp_level
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
        employee_number = f"EMP{now.month:02d}.{random_number}.{now.year}.{now.day:02d}"
        
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
    Memperbarui/Edit data karyawan secara universal.
    Secara otomatis mendeteksi dan memperbarui field di tabel 'employees' maupun 'employee_cv'
    dalam satu transaksi database yang aman.
    
    Args:
        emp_id: Database ID karyawan
        updates: Dict of field names and values to update (optional)
        **kwargs: Field dan nilai baru yang di-pass langsung sebagai arguments
        
    Returns:
        Dict status keberhasilan, pesan, dan data field yang diperbarui
    """
    import json
    import ast
    import re
    
    actual_updates = {}
    
    # 1. Safely parse 'updates' if it is a string representation of a dict
    if isinstance(updates, str):
        updates_str = updates.strip()
        parsed = None
        try:
            parsed = json.loads(updates_str)
        except Exception:
            try:
                parsed = ast.literal_eval(updates_str)
            except Exception:
                pass
        
        if not isinstance(parsed, dict):
            # Attempt to extract dict from string using regex
            match = re.search(r'\{[\s\S]*\}', updates_str)
            if match:
                try:
                    parsed = json.loads(match.group())
                except Exception:
                    try:
                        parsed = ast.literal_eval(match.group())
                    except Exception:
                        pass
        
        if isinstance(parsed, dict):
            actual_updates = parsed
        else:
            return {
                "success": False,
                "error": f"Argumen 'updates' dikirim sebagai string yang tidak dapat diparse sebagai dictionary: '{updates}'"
            }
    elif isinstance(updates, dict):
        actual_updates = dict(updates)
    elif updates is not None:
        return {
            "success": False,
            "error": f"Argumen 'updates' harus berupa dictionary atau string representasi dictionary, namun menerima tipe: {type(updates).__name__}"
        }
        
    # Merge kwargs (giving them precedence if passed explicitly)
    actual_updates.update({k: v for k, v in kwargs.items() if v is not None})
    
    # 2. Unwrap nested 'data' if passed directly from extract_data_from_file result
    if "data" in actual_updates and isinstance(actual_updates["data"], dict):
        nested_data = actual_updates["data"]
        for k, v in nested_data.items():
            if k not in actual_updates or actual_updates[k] is None:
                actual_updates[k] = v
        actual_updates.pop("data", None)
        
    # Handle list of education dictionaries if present (take the first/most recent one)
    if "education" in actual_updates and isinstance(actual_updates["education"], list) and len(actual_updates["education"]) > 0:
        first_edu = actual_updates["education"][0]
        if isinstance(first_edu, dict):
            actual_updates["education"] = first_edu
            
    # Handle nested education dictionary
    if "education" in actual_updates and isinstance(actual_updates["education"], dict):
        edu = actual_updates.pop("education")
        edu_mappings = {
            "institution": "education_institution",
            "univ": "education_institution",
            "university": "education_institution",
            "school": "education_institution",
            "major": "education_major",
            "jurusan": "education_major",
            "year": "graduation_year",
            "grad_year": "graduation_year",
            "level": "education_level",
            "jenjang": "education_level",
            "degree": "education_level",
        }
        for k, v in edu.items():
            k_lower = k.lower()
            if k_lower in edu_mappings:
                canonical = edu_mappings[k_lower]
                if canonical not in actual_updates or actual_updates[canonical] is None:
                    actual_updates[canonical] = v
            else:
                if k in ["education_level", "education_institution", "education_major", "graduation_year"]:
                    if k not in actual_updates or actual_updates[k] is None:
                        actual_updates[k] = v
                        
    # 3. Defensive mapping of key variations and aliases
    alias_map = {
        "phone_number": ["phone"],
        "phone_no": ["phone"],
        "no_telp": ["phone"],
        "no_hp": ["phone"],
        "no_handphone": ["phone"],
        "handphone": ["phone"],
        "email_address": ["email"],
        "education": ["education_level"],
        "experience": ["work_experience"],
        "work_history": ["work_experience"],
        "riwayat_pekerjaan": ["work_experience"],
        "keahlian": ["skills"],
        "salary": ["basic_salary", "current_salary"],
        "gaji": ["basic_salary", "current_salary"],
        "dept": ["department", "current_department"],
        "job_title": ["position", "current_position"],
    }
    
    for alias, canonical_keys in alias_map.items():
        if alias in actual_updates:
            val = actual_updates.pop(alias)
            if val is not None:
                for canonical in canonical_keys:
                    if canonical not in actual_updates or actual_updates[canonical] is None:
                        actual_updates[canonical] = val
                        
    # Apply cross-mappings to keep tables synchronized
    cross_mappings = {
        "position": "current_position",
        "current_position": "position",
        "department": "current_department",
        "current_department": "department",
        "basic_salary": "current_salary",
        "current_salary": "basic_salary",
    }
    
    for src, dst in cross_mappings.items():
        if src in actual_updates and actual_updates[src] is not None:
            if dst not in actual_updates or actual_updates[dst] is None:
                actual_updates[dst] = actual_updates[src]
                
    # Filter out None values to prevent accidentally overwriting with nulls
    actual_updates = {k: v for k, v in actual_updates.items() if v is not None}

    
    # Guard: must be a non-empty dict
    if not actual_updates:
        return {
            "success": False,
            "error": "Parameter update tidak boleh kosong. Pastikan field dan nilai yang ingin diupdate sudah ditentukan."
        }
    
    # Oracle ORA-01484 fix: Ensure no lists/arrays are passed as bound values to standard SQL
    for k, v in list(actual_updates.items()):
        if isinstance(v, list):
            actual_updates[k] = ", ".join(map(str, v))

    try:
        conn = _get_connection()
        cur = conn.cursor()
        
        # Verify employee exists
        cur.execute("SELECT name FROM employees WHERE id = :eid", {"eid": emp_id})
        emp_exists = cur.fetchone()
        if not emp_exists:
            cur.close()
            conn.close()
            return {"success": False, "error": f"Karyawan dengan ID {emp_id} tidak ditemukan."}
        
        # Get valid columns for employees table (dynamically)
        cur.execute("SELECT * FROM employees WHERE ROWNUM = 1")
        valid_emp_columns = set(
            desc[0].lower() for desc in cur.description
            if desc[0].lower() not in ["id", "employee_code"]
        )
        
        # Get valid columns for employee_cv table (dynamically)
        cur.execute("SELECT * FROM employee_cv WHERE ROWNUM = 1")
        valid_cv_columns = set(
            desc[0].lower() for desc in cur.description
            if desc[0].lower() not in ["id", "employee_id"]
        )
        
        # Split updates
        emp_updates = {k: v for k, v in actual_updates.items() if k.lower() in valid_emp_columns}
        cv_updates = {k: v for k, v in actual_updates.items() if k.lower() in valid_cv_columns}
        
        if not emp_updates and not cv_updates:
            cur.close()
            conn.close()
            return {"success": False, "error": "Tidak ada kolom valid yang diperbarui. Periksa nama field yang diberikan."}
        
        messages = []
        updated_data = {}
        
        # --- Update employees table ---
        if emp_updates:
            emp_updates["emp_id"] = emp_id
            set_clause = ", ".join(f"{k} = :{k}" for k in emp_updates if k != "emp_id")
            cur.execute(f"UPDATE employees SET {set_clause} WHERE id = :emp_id", emp_updates)
            messages.append(f"{len(emp_updates) - 1} field di tabel employees")
            
        # --- Update employee_cv table ---
        if cv_updates:
            # Check if CV record exists
            cur.execute("SELECT id FROM employee_cv WHERE employee_id = :eid", {"eid": emp_id})
            cv_row = cur.fetchone()
            
            if cv_row:
                cv_updates["emp_id"] = emp_id
                set_clause = ", ".join(f"{k} = :{k}" for k in cv_updates if k != "emp_id")
                set_clause += ", updated_at = CURRENT_TIMESTAMP"
                cur.execute(f"UPDATE employee_cv SET {set_clause} WHERE employee_id = :emp_id", cv_updates)
                messages.append(f"{len(cv_updates) - 1} field di tabel employee_cv")
            else:
                # Insert minimal CV record with the given fields
                cv_updates["employee_id"] = emp_id
                cols = ", ".join(cv_updates.keys())
                placeholders = ", ".join(f":{k}" for k in cv_updates.keys())
                cur.execute(f"INSERT INTO employee_cv ({cols}) VALUES ({placeholders})", cv_updates)
                messages.append(f"{len(cv_updates) - 1} field di tabel employee_cv (record baru dibuat)")
        
        conn.commit()

        # -- Re-fetch actual committed values for verification --
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
            
            if cv_updates:
                cv_fields = [k for k in cv_updates if k not in ("emp_id", "employee_id")]
                if cv_fields:
                    cur.execute(
                        f"SELECT {', '.join(cv_fields)} FROM employee_cv WHERE employee_id = :eid",
                        {"eid": emp_id}
                    )
                    row = cur.fetchone()
                    if row:
                        for i, field in enumerate(cv_fields):
                            val = row[i]
                            updated_data[field] = val.read() if hasattr(val, "read") else val
        except Exception:
            pass  # non-critical
            
        cur.close()
        conn.close()

        return {
            "success": True,
            "message": f"Data karyawan ID {emp_id} berhasil diperbarui: {', '.join(messages)}.",
            "updated_fields": updated_data
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
        Gunakan abs_path untuk extract_data_from_file.
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
            "hint": "Gunakan 'abs_path' dari files.cv atau files.payroll_slips sebagai file_path di extract_data_from_file / get_payroll_file."
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
        "description": "Mencari data karyawan secara fleksibel dan melakukan filter dinamis. Gunakan tool ini untuk mencari berdasarkan nama, email, atau telepon (fuzzy query), atau melakukan filter spesifik berdasarkan jabatan (position), departemen (department), status kepegawaian (status), serta rentang gaji (min_salary dan max_salary). PENTING: Tool ini mengembalikan 'id' (database ID integer) yang digunakan untuk tool lainnya.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Kata kunci pencarian nama, email, atau telepon (opsional). Contoh: 'Budi'"
                },
                "position": {
                    "type": "string",
                    "description": "Jabatan/posisi karyawan (opsional). Contoh: 'Manager'"
                },
                "department": {
                    "type": "string",
                    "description": "Departemen karyawan (opsional). Contoh: 'IT'"
                },
                "status": {
                    "type": "string",
                    "description": "Status karyawan (opsional). Contoh: 'active', 'inactive'"
                },
                "min_salary": {
                    "type": "number",
                    "description": "Gaji pokok minimum (opsional). Contoh: 8000000"
                },
                "max_salary": {
                    "type": "number",
                    "description": "Gaji pokok maksimum (opsional). Contoh: 15000000"
                },
                "limit": {
                    "type": "integer",
                    "description": "Jumlah maksimal hasil (default: 20)",
                    "default": 20
                }
            },
            "required": []
        }
    },
    {
        "name": "get_employee_by_id",
        "description": "Mengambil DETAIL LENGKAP satu karyawan. WAJIB dipanggil setelah search_employees untuk mendapatkan informasi lengkap seperti gaji, alamat, BPJS, sisa cuti, dll. PENTING: Output juga menyertakan 'CV_FILE_PATH' (path file CV, gunakan sebagai file_path di extract_data_from_file) dan 'cv_info' (data profil CV: pendidikan, skill, sertifikasi, dll). Gunakan {{step_N.result.data.CV_FILE_PATH}} untuk file_path di step berikutnya.",
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
        "description": "Mengambil daftar SEMUA karyawan dengan info dasar termasuk sisa cuti dan level SP. Gunakan jika user meminta 'daftar semua karyawan' atau statistik keseluruhan.",
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
        "description": "UPDATE data karyawan secara universal. HARUS gunakan emp_id (database ID integer). Tool ini secara dinamis memperbarui kolom pada tabel 'employees' (seperti posisi, departemen, alamat, gaji pokok basic_salary, email, telepon, status pernikahan, status kepegawaian, BPJS number, sisa cuti, level SP, tanggal bergabung) dan/atau kolom pada tabel 'employee_cv' (seperti pendidikan, sertifikasi, keahlian, rekening bank, kontak darurat, serta potongan bulanan).",
        "parameters": {
            "type": "object",
            "properties": {
                "emp_id": {
                    "type": "integer",
                    "description": "Database ID karyawan (integer). BUKAN employee_code! Dapatkan dari search_employees."
                },
                "position": {"type": "string", "description": "Jabatan/Posisi (tabel employees)"},
                "department": {"type": "string", "description": "Departemen (tabel employees)"},
                "status": {"type": "string", "description": "Status karyawan, misal 'active' (tabel employees)"},
                "employment_status": {"type": "string", "description": "Status kepegawaian (tabel employees)"},
                "basic_salary": {"type": "number", "description": "Gaji Pokok (tabel employees)"},
                "phone": {"type": "string", "description": "Nomor Telepon (tabel employees)"},
                "email": {"type": "string", "description": "Alamat Email (tabel employees)"},
                "address": {"type": "string", "description": "Alamat Lengkap (tabel employees)"},
                "marital_status": {"type": "string", "description": "Status Pernikahan (tabel employees)"},
                "sp_level": {"type": "integer", "description": "Tingkat Surat Peringatan SP 0-3 (tabel employees)"},
                "remaining_leave": {"type": "integer", "description": "Sisa Cuti dalam hari (tabel employees)"},
                "bpjs_number": {"type": "string", "description": "Nomor BPJS (tabel employees)"},
                "joined_at": {"type": "string", "description": "Tanggal Bergabung YYYY-MM-DD (tabel employees)"},
                "education_level": {"type": "string", "description": "Tingkat pendidikan terakhir (tabel CV)"},
                "education_institution": {"type": "string", "description": "Nama universitas/sekolah (tabel CV)"},
                "education_major": {"type": "string", "description": "Jurusan pendidikan (tabel CV)"},
                "graduation_year": {"type": "integer", "description": "Tahun kelulusan (tabel CV)"},
                "skills": {"type": "string", "description": "Daftar skill keahlian (tabel CV)"},
                "certifications": {"type": "string", "description": "Sertifikasi keahlian (tabel CV)"},
                "work_experience": {"type": "string", "description": "Ringkasan pengalaman kerja (tabel CV)"},
                "emergency_contact_name": {"type": "string", "description": "Nama kontak darurat (tabel CV)"},
                "emergency_contact_phone": {"type": "string", "description": "Telepon kontak darurat (tabel CV)"},
                "emergency_contact_relation": {"type": "string", "description": "Hubungan kontak darurat (tabel CV)"},
                "bank_name": {"type": "string", "description": "Nama Bank (tabel CV)"},
                "bank_account_number": {"type": "string", "description": "Nomor rekening bank (tabel CV)"},
                "bank_account_name": {"type": "string", "description": "Nama pemilik rekening bank (tabel CV)"},
                "deduction_bpjs_kesehatan": {"type": "number", "description": "Potongan bulanan BPJS Kesehatan (tabel CV)"},
                "deduction_bpjs_ketenagakerjaan": {"type": "number", "description": "Potongan bulanan BPJS Ketenagakerjaan (tabel CV)"},
                "deduction_meal": {"type": "number", "description": "Potongan bulanan Makan (tabel CV)"},
                "deduction_transport": {"type": "number", "description": "Potongan bulanan Transport (tabel CV)"},
                "deduction_insurance": {"type": "number", "description": "Potongan bulanan Asuransi (tabel CV)"},
                "deduction_laptop_installment": {"type": "number", "description": "Potongan cicilan laptop (tabel CV)"},
                "deduction_laptop_remaining_months": {"type": "integer", "description": "Sisa bulan cicilan laptop (tabel CV)"},
                "deduction_other": {"type": "number", "description": "Potongan lainnya (tabel CV)"},
                "deduction_other_description": {"type": "string", "description": "Deskripsi potongan lainnya (tabel CV)"}
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
        "name": "get_employee_files",
        "description": (
            "Ambil daftar semua file penting milik satu karyawan: file CV (dari employee_cv) "
            "dan slip gaji/payroll (dari payroll_slips). Mengembalikan 'abs_path' dan 'server_url' "
            "untuk setiap file. WAJIB dipanggil sebelum extract_data_from_file atau get_payroll_file "
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
