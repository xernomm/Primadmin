import os
import cx_Oracle
from datetime import datetime, date
import random
import re
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from mcp.server.fastmcp import FastMCP
import traceback


load_dotenv()

ORACLE_USER = os.getenv("ORACLE_USER")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD")
ORACLE_HOST = os.getenv("ORACLE_HOST")
ORACLE_PORT = os.getenv("ORACLE_PORT")
ORACLE_SERVICE = os.getenv("ORACLE_SERVICE_NAME")

# Build DSN and connection string for SQLAlchemy
dsn = cx_Oracle.makedsn(ORACLE_HOST, ORACLE_PORT, service_name=ORACLE_SERVICE)

# Init MCP
db_url = f"oracle+cx_oracle://{ORACLE_USER}:{ORACLE_PASSWORD}@{dsn}"
engine = create_engine(db_url)
mcp = FastMCP("OracleEmployeeManager", host="0.0.0.0", port=8000)

@mcp.tool()
def create_employee(name: str) -> str:
    """
    Menambahkan data dasar karyawan baru (hanya nama dan nomor karyawan otomatis).
    """
    try:
        now = datetime.now()
        random_number = random.randint(100, 999)
        employee_number = f"{now.year}-{now.month:02d}-{now.day:02d}-{random_number}"

        conn = cx_Oracle.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=dsn)
        cur = conn.cursor()

        emp_id_var = cur.var(cx_Oracle.NUMBER)
        print("[ORACLE] Menambahkan karyawan baru...")
        print(f"Nama: {name}, Nomor: {employee_number}")
        cur.execute("""
            INSERT INTO employees (name, employee_number)
            VALUES (:name, :empno) RETURNING id INTO :id
        """, {
            "name": name,
            "empno": employee_number,
            "id": emp_id_var
        })

        emp_id = int(emp_id_var.getvalue()[0])  # <--- ini diperbaiki
        print(f"[ORACLE] Insert berhasil. ID: {emp_id}")

        conn.commit()
        return f"✅ Karyawan '{name}' berhasil ditambahkan dengan ID {emp_id} dan nomor karyawan {employee_number}."
    except Exception as e:
        print("[ORACLE ERROR]", traceback.format_exc())
        return f"❌ Gagal menambahkan karyawan: {e}\n{traceback.format_exc()}"
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass

@mcp.tool()
def update_employee_by_id(emp_id: int, updates: dict) -> str:
    """
    Memperbarui satu atau lebih field di tabel 'employee_details' berdasarkan nama karyawan.
    Jika detail belum ada, maka akan ditambahkan.

    Contoh pertanyaan:
    - Tolong update data Rafael Richie, sekarang jabatannya Software Engineer dan gajinya 10 juta ya.
    - Saya ingin memperbarui data Rafael Richie. Jenis kelaminnya pria dan status pernikahannya belum menikah.
    - Ganti email Rafael Richie jadi rafael@company.com dan nomor HP-nya 081234567890.
    - Update status kepegawaian Rafael Richie jadi kontrak dan alamatnya di Jalan Sudirman No. 12, Jakarta.
    - Tolong isi password internal Rafael Richie jadi rahasia123 dan dia sudah punya 2 surat peringatan.

    Parameter:
    - name: Nama lengkap karyawan.
    - updates: Dict berisi pasangan {nama_kolom: nilai}. 
      Kolom harus valid sesuai struktur tabel employee_details.

    Contoh penggunaan:
    name: "Rafael Richie"
    updates: {
      "position": "Software Engineer",
      "gender": "pria",
      "salary": 10000000
    }

    🔎 Daftar kolom yang valid di tabel SMARTBOT.employee_details:
    - position (str): Jabatan atau peran, contoh: "Manager", "Staff".
    - address (str): Alamat tempat tinggal.
    - status (str): Status kepegawaian, contoh: "tetap", "kontrak", "magang".
    - salary (float): Gaji pokok dalam angka, contoh: 8500000.
    - phone (str): Nomor telepon, harus unik.
    - email (str): Alamat email, harus unik.
    - password (str): Kata sandi untuk akses internal.
    - gender (str): Jenis kelamin, contoh: "pria", "wanita".
    - marital (str): Status pernikahan, contoh: "menikah", "belum menikah".
    - sp (int): Jumlah surat peringatan, contoh: 0, 1, 2, 3.

    ❗ Kolom "id" tidak bisa diperbarui secara manual.
    """
    try:
        conn = cx_Oracle.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=dsn)
        cur = conn.cursor()

        # Validasi kolom
        cur.execute("SELECT * FROM SMARTBOT.employee_details WHERE ROWNUM = 1")
        valid_columns = set(desc[0].lower() for desc in cur.description if desc[0].lower() != "id")

        clean_updates = {k: v for k, v in updates.items() if k.lower() in valid_columns}
        if not clean_updates:
            return "⚠️ Tidak ada kolom valid yang diperbarui."

        clean_updates["emp_id"] = emp_id

        # Check existence
        cur.execute("SELECT id FROM SMARTBOT.employee_details WHERE emp_id = :id", {"id": emp_id})
        exists = cur.fetchone()

        if exists:
            set_clause = ", ".join(f"{k} = :{k}" for k in clean_updates if k != "emp_id")
            cur.execute(f"UPDATE SMARTBOT.employee_details SET {set_clause} WHERE emp_id = :emp_id", clean_updates)
        else:
            columns = ", ".join(clean_updates.keys())
            values = ", ".join(f":{k}" for k in clean_updates)
            cur.execute(f"INSERT INTO SMARTBOT.employee_details ({columns}) VALUES ({values})", clean_updates)

        conn.commit()
        return f"✅ Data karyawan ID {emp_id} berhasil diperbarui."
    except Exception as e:
        return f"❌ Gagal update data ID {emp_id}: {e}\n{traceback.format_exc()}"
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass


@mcp.tool()
def delete_employee_by_id(emp_id: int) -> str:
    """
    Delete employee and all related data by employee ID.
    """
    try:
        conn = cx_Oracle.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=dsn)
        cur = conn.cursor()

        # Hapus relasi di leaves, absensi, employee_details
        cur.execute("DELETE FROM SMARTBOT.leaves WHERE emp_id = :id", {"id": emp_id})
        cur.execute("DELETE FROM SMARTBOT.absensi WHERE emp_id = :id", {"id": emp_id})
        cur.execute("DELETE FROM SMARTBOT.employee_details WHERE emp_id = :id", {"id": emp_id})

        # Hapus dari employees
        cur.execute("DELETE FROM SMARTBOT.employees WHERE id = :id", {"id": emp_id})

        conn.commit()
        return f"✅ Data karyawan ID {emp_id} berhasil dihapus beserta seluruh data terkait."
    except Exception as e:
        return f"❌ Gagal menghapus karyawan ID {emp_id}: {e}\n{traceback.format_exc()}"
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass


@mcp.tool()
def get_all_employees(limit: int = 100) -> str:
    """
    Retrieve all employees with basic details (limit 100).
    """
    conn = cx_Oracle.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=dsn)
    cur = conn.cursor()

    query = """
        SELECT e.id, e.name, d.position, d.status, d.salary, d.phone, d.email, d.gender, d.marital, d.sp
        FROM SMARTBOT.employees e
        LEFT JOIN SMARTBOT.employee_details d ON e.id = d.emp_id
        FETCH FIRST :1 ROWS ONLY
    """
    cur.execute(query, [limit])
    columns = [desc[0] for desc in cur.description]
    rows = cur.fetchall()

    cur.close()
    conn.close()

    # Format ke Markdown
    md = "| " + " | ".join(columns) + " |\n"
    md += "| " + " | ".join(["---"] * len(columns)) + " |\n"
    for row in rows:
        md += "| " + " | ".join(str(cell) if cell is not None else "" for cell in row) + " |\n"

    return md




@mcp.tool()
def get_employee_by_id(emp_id: int) -> dict:
    """
    Retrieve single employee and details by employee ID.
    """
    conn = cx_Oracle.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=dsn)
    cur = conn.cursor()
    query = """
        SELECT e.id, e.name, d.position, d.status, d.salary, d.phone, d.email, d.gender, d.marital, d.sp
        FROM SMARTBOT.employees e
        LEFT JOIN SMARTBOT.employee_details d ON e.id = d.emp_id
        WHERE e.id = :1
    """
    cur.execute(query, [emp_id])
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return dict(zip([desc[0] for desc in cur.description], row))
    else:
        return {"error": f"Karyawan dengan id {emp_id} tidak ditemukan."}

@mcp.tool()
def search_employee_by_name(name: str, limit: int = 20) -> dict:
    """
    Search employees by name (partial match).
    """
    conn = cx_Oracle.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=dsn)
    cur = conn.cursor()
    query = """
        SELECT e.id, e.name, d.position, d.status, d.salary, d.phone, d.email, d.gender, d.marital, d.sp
        FROM SMARTBOT.employees e
        LEFT JOIN SMARTBOT.employee_details d ON e.id = d.emp_id
        WHERE LOWER(e.name) LIKE :1
        FETCH FIRST :2 ROWS ONLY
    """
    cur.execute(query, [f"%{name.lower()}%", limit])
    columns = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {"columns": columns, "data": [list(row) for row in rows]}

@mcp.tool()
def search_employee_by_email(email: str, limit: int = 20) -> dict:
    """
    Search employees by email (partial match).
    """
    conn = cx_Oracle.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=dsn)
    cur = conn.cursor()
    query = """
        SELECT e.id, e.name, d.position, d.status, d.salary, d.phone, d.email, d.gender, d.marital, d.sp
        FROM SMARTBOT.employees e
        LEFT JOIN SMARTBOT.employee_details d ON e.id = d.emp_id
        WHERE LOWER(d.email) LIKE :1
        FETCH FIRST :2 ROWS ONLY
    """
    cur.execute(query, [f"%{email.lower()}%", limit])
    columns = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {"columns": columns, "data": [list(row) for row in rows]}

@mcp.tool()
def search_employee_by_phone(phone: str, limit: int = 20) -> dict:
    """
        Search employees by phone number (partial match).

    """
    conn = cx_Oracle.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=dsn)
    cur = conn.cursor()
    query = """
        SELECT e.id, e.name, d.position, d.status, d.salary, d.phone, d.email, d.gender, d.marital, d.sp
        FROM SMARTBOT.employees e
        LEFT JOIN SMARTBOT.employee_details d ON e.id = d.emp_id
        WHERE d.phone LIKE :1
        FETCH FIRST :2 ROWS ONLY
    """
    cur.execute(query, [f"%{phone}%", limit])
    columns = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {"columns": columns, "data": [list(row) for row in rows]}

@mcp.tool()
def filter_employees_by_position(position: str, limit: int = 50) -> dict:
    """
        Filter employees by job position.
    """
    conn = cx_Oracle.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=dsn)
    cur = conn.cursor()
    query = """
        SELECT e.id, e.name, d.position, d.status, d.salary, d.phone, d.email, d.gender, d.marital, d.sp
        FROM SMARTBOT.employees e
        JOIN SMARTBOT.employee_details d ON e.id = d.emp_id
        WHERE LOWER(d.position) LIKE :1
        FETCH FIRST :2 ROWS ONLY
    """
    cur.execute(query, [f"%{position.lower()}%", limit])
    columns = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {"columns": columns, "data": [list(row) for row in rows]}

@mcp.tool()
def filter_employees_by_status(status: str, limit: int = 50) -> dict:
    """
        Filter employees by employment status.

    """
    conn = cx_Oracle.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=dsn)
    cur = conn.cursor()
    query = """
        SELECT e.id, e.name, d.position, d.status, d.salary, d.phone, d.email, d.gender, d.marital, d.sp
        FROM SMARTBOT.employees e
        JOIN SMARTBOT.employee_details d ON e.id = d.emp_id
        WHERE LOWER(d.status) = :1
        FETCH FIRST :2 ROWS ONLY
    """
    cur.execute(query, [status.lower(), limit])
    columns = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {"columns": columns, "data": [list(row) for row in rows]}

@mcp.tool()
def filter_employees_salary_above(min_salary: float, limit: int = 50) -> dict:
    """
        Filter employees with salary above threshold.
    """
    conn = cx_Oracle.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=dsn)
    cur = conn.cursor()
    query = """
        SELECT e.id, e.name, d.position, d.status, d.salary, d.phone, d.email, d.gender, d.marital, d.sp
        FROM SMARTBOT.employees e
        JOIN SMARTBOT.employee_details d ON e.id = d.emp_id
        WHERE d.salary >= :1
        FETCH FIRST :2 ROWS ONLY
    """
    cur.execute(query, [min_salary, limit])
    columns = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    cur.close()
    conn.close()
    print({"columns": columns, "data": [list(row) for row in rows]})

    return {"columns": columns, "data": [list(row) for row in rows]}

@mcp.tool()
def filter_employees_salary_below(max_salary: float, limit: int = 50) -> dict:
    """
        Filter employees with salary below threshold.


    """
    conn = cx_Oracle.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=dsn)
    cur = conn.cursor()
    query = """
        SELECT e.id, e.name, d.position, d.status, d.salary, d.phone, d.email, d.gender, d.marital, d.sp
        FROM SMARTBOT.employees e
        JOIN SMARTBOT.employee_details d ON e.id = d.emp_id
        WHERE d.salary <= :1
        FETCH FIRST :2 ROWS ONLY
    """
    cur.execute(query, [max_salary, limit])
    columns = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    cur.close()
    conn.close()
    print({"columns": columns, "data": [list(row) for row in rows]})

    return {"columns": columns, "data": [list(row) for row in rows]}

@mcp.tool()
def get_employee_leave_by_id(emp_id: int) -> dict:
    """
    Retrieve leave data of employee by ID.
    """
    try:
        with engine.begin() as conn:
            result = conn.execute(text("SELECT * FROM SMARTBOT.leaves WHERE emp_id = :emp_id"), {"emp_id": emp_id}).fetchone()
            if result is None:
                return {"error": "Data cuti tidak ditemukan."}
            columns = result.keys()
            return dict(zip(columns, result))
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def get_all_employee_leaves(limit: int = 100) -> dict:
    """
    Retrieve leave data for all employees.

    Cocok digunakan untuk monitoring HR secara menyeluruh, seperti:
    - "Lihat semua data cuti karyawan"
    - "Siapa yang masih punya cuti banyak?"

    Parameter:
    - limit (int): Jumlah maksimal baris data yang diambil (default 100) untuk mencegah query berat dan error Oracle.

    Output:
    Dictionary berisi:
    - columns: Daftar nama kolom.
    - data: List data karyawan.
    """
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                SELECT l.id, e.name, l.remaining_leave, l.sick_leave, l.maternity_leave, l.unpaid_leave, l.other_leave
                FROM SMARTBOT.leaves l
                JOIN SMARTBOT.employees e ON l.emp_id = e.id
                FETCH FIRST :limit ROWS ONLY
            """), {"limit": limit}).fetchall()
            if not result:
                return {"columns": [], "data": []}
            columns = result[0].keys()
            data = [dict(zip(columns, row)) for row in result]
            return {"columns": columns, "data": data}
    except Exception as e:
        return {"error": str(e), "trace": traceback.format_exc()}
    
@mcp.tool()
def update_leaves(emp_id: int, updates: dict) -> str:
    """
    Memperbarui satu atau lebih field cuti pada tabel `leaves` berdasarkan ID karyawan.

    Contoh pertanyaan:
    - Update cuti pegawai ID 5, sisa cutinya jadi 8, cuti sakitnya jadi 2.
    - Ubah unpaid_leave karyawan ID 7 jadi 3 hari.

    Parameter:
    - emp_id (int): ID karyawan.
    - updates (dict): pasangan {nama_kolom: nilai} yang ingin diubah.
      Kolom valid:
        - remaining_leave
        - sick_leave
        - maternity_leave
        - unpaid_leave
        - other_leave

    ❗ Kolom id dan emp_id tidak bisa diubah.

    Output:
    Pesan sukses atau error terkait update cuti.
    """
    try:
        with engine.begin() as conn:
            columns = [col[0].lower() for col in conn.execute(text("SELECT column_name FROM all_tab_columns WHERE table_name = 'LEAVES' AND owner = 'SMARTBOT'"))]
            valid_updates = {k: v for k, v in updates.items() if k.lower() in columns and k.lower() != "id" and k.lower() != "emp_id"}
            if not valid_updates:
                return "⚠️ Tidak ada kolom cuti valid yang diperbarui."
            set_clause = ", ".join(f"{k} = :{k}" for k in valid_updates)
            valid_updates["emp_id"] = emp_id
            conn.execute(text(f"UPDATE SMARTBOT.leaves SET {set_clause} WHERE emp_id = :emp_id"), valid_updates)
        return f"✅ Data cuti karyawan ID {emp_id} berhasil diperbarui."
    except Exception as e:
        return f"❌ Gagal update data cuti ID {emp_id}: {e}\n{traceback.format_exc()}"

@mcp.tool()
def update_absensi(absen_id: int, updates: dict) -> str:
    """
    Memperbarui satu atau lebih field di tabel 'absensi' berdasarkan ID absensi (absen_id).
    Tool ini digunakan untuk mengoreksi data absensi karyawan apabila terdapat kesalahan lokasi, waktu, atau status remote/terlambat.

    Cocok untuk perintah seperti:
    - "Tolong perbaiki absensi ID 15, alamatnya diubah ke Jalan Gatot Subroto No. 12."
    - "Update jarak absensi ID 22 jadi 2.1 km dan status remote-nya diaktifkan."
    - "Koreksi data absensi ID 30, dia sebenarnya tidak telat."

    Parameter:
    - absen_id (int): ID unik absensi (primary key dari tabel absensi).
    - updates (dict): Dictionary berisi pasangan {nama_kolom: nilai} untuk field yang ingin diperbarui.

    Contoh penggunaan:
    absen_id: 15
    updates: {
        "addr": "Jalan Gatot Subroto No. 12",
        "dist": 1.2,
        "late": 0
    }

    🔎 Daftar kolom yang valid di tabel SMARTBOT.absensi:
    - emp_id (int): ID karyawan (tidak disarankan diubah, kecuali dalam kasus koreksi penginputan).
    - latitude (float): Koordinat latitude lokasi absen, contoh: -6.200123.
    - longitude (float): Koordinat longitude lokasi absen, contoh: 106.812345.
    - addr (str): Alamat teks lokasi absen, contoh: "Jl. Sudirman No.1, Jakarta".
    - dist (float): Jarak dari kantor (dalam kilometer), contoh: 3.25.
    - timestamp (datetime): Waktu absen. Format ideal ISO 8601, contoh: "2025-07-16T08:30:00".
    - late (int): Status keterlambatan, 1 untuk telat, 0 untuk hadir tepat waktu.
    - remote (int): Status remote, 1 berarti bekerja secara remote, 0 berarti onsite.

    ❗ Kolom 'id' (absen_id) tidak bisa diperbarui secara manual. Tool ini hanya melakukan update berdasarkan ID absensi yang valid.

    Output:
    ✅ Pesan keberhasilan update, atau ❌ pesan error jika gagal.
    """
    try:
        with engine.begin() as conn:
            # Ambil semua kolom absensi
            columns = [col[0].lower() for col in conn.execute(text("""
                SELECT column_name FROM all_tab_columns
                WHERE table_name = 'ABSENSI' AND owner = 'SMARTBOT'
            """))]

            # Validasi updates
            valid_updates = {
                k: v for k, v in updates.items()
                if k.lower() in columns and k.lower() not in ["id"]
            }

            if not valid_updates:
                return "⚠️ Tidak ada kolom absensi valid yang diperbarui."

            # Siapkan query update dinamis
            set_clause = ", ".join(f"{k} = :{k}" for k in valid_updates)
            valid_updates["absen_id"] = absen_id

            conn.execute(text(f"""
                UPDATE SMARTBOT.absensi
                SET {set_clause}
                WHERE id = :absen_id
            """), valid_updates)

        return f"✅ Data absensi ID {absen_id} berhasil diperbarui."
    except Exception as e:
        return f"❌ Gagal update data absensi ID {absen_id}: {e}\n{traceback.format_exc()}"

@mcp.tool()
def get_today_attendance(limit: int = 100) -> dict:
    """
    Get today’s attendance records.

    """
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                SELECT a.id, e.name, a.addr, a.dist, a.timestamp, a.late, a.remote
                FROM SMARTBOT.absensi a
                JOIN SMARTBOT.employees e ON a.emp_id = e.id
                WHERE TRUNC(a.timestamp) = TRUNC(SYSDATE)
                ORDER BY a.timestamp ASC, a.dist ASC
                FETCH FIRST :limit ROWS ONLY
            """), {"limit": limit}).fetchall()
            columns = result[0].keys() if result else []
            data = [dict(zip(columns, row)) for row in result]
            return {"columns": columns, "data": data}
    except Exception as e:
        return {"error": str(e), "trace": traceback.format_exc()}


@mcp.tool()
def get_today_late_employees(limit: int = 100) -> dict:
    """
    List employees who were late today.

    """
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                SELECT e.name, a.timestamp
                FROM SMARTBOT.absensi a
                JOIN SMARTBOT.employees e ON a.emp_id = e.id
                WHERE TRUNC(a.timestamp) = TRUNC(SYSDATE)
                AND TO_CHAR(a.timestamp, 'HH24:MI') > '08:30'
                ORDER BY a.timestamp ASC
                FETCH FIRST :limit ROWS ONLY
            """), {"limit": limit}).fetchall()
            columns = result[0].keys() if result else []
            data = [dict(zip(columns, row)) for row in result]
            return {"columns": columns, "data": data}
    except Exception as e:
        return {"error": str(e), "trace": traceback.format_exc()}

@mcp.tool()
def get_today_distance_over_five_km(limit: int = 100) -> dict:
    """
    Get employees who checked in >5 km from office.

    """
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                SELECT e.name, a.addr, a.dist
                FROM SMARTBOT.absensi a
                JOIN SMARTBOT.employees e ON a.emp_id = e.id
                WHERE TRUNC(a.timestamp) = TRUNC(SYSDATE)
                AND a.dist > 5
                ORDER BY a.dist DESC
                FETCH FIRST :limit ROWS ONLY
            """), {"limit": limit}).fetchall()
            columns = result[0].keys() if result else []
            data = [dict(zip(columns, row)) for row in result]
            return {"columns": columns, "data": data}
    except Exception as e:
        return {"error": str(e), "trace": traceback.format_exc()}

@mcp.tool()
def get_today_remote_employees(limit: int = 100) -> dict:
    """
    Get employees working remotely today.

    """
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                SELECT e.name, a.timestamp, a.addr, a.dist
                FROM SMARTBOT.absensi a
                JOIN SMARTBOT.employees e ON a.emp_id = e.id
                WHERE TRUNC(a.timestamp) = TRUNC(SYSDATE)
                AND a.remote = 1
                ORDER BY a.timestamp ASC
                FETCH FIRST :limit ROWS ONLY
            """), {"limit": limit}).fetchall()
            columns = result[0].keys() if result else []
            data = [dict(zip(columns, row)) for row in result]
            return {"columns": columns, "data": data}
    except Exception as e:
        return {"error": str(e), "trace": traceback.format_exc()}

@mcp.tool()
def get_today_onsite_employees(limit: int = 100) -> dict:
    """
    Get employees working onsite today.

    """
    try:
        with engine.begin() as conn:
            result = conn.execute(text("""
                SELECT e.name, a.timestamp, a.addr, a.dist
                FROM SMARTBOT.absensi a
                JOIN SMARTBOT.employees e ON a.emp_id = e.id
                WHERE TRUNC(a.timestamp) = TRUNC(SYSDATE)
                AND a.remote = 0
                ORDER BY a.timestamp ASC
                FETCH FIRST :limit ROWS ONLY
            """), {"limit": limit}).fetchall()
            columns = result[0].keys() if result else []
            data = [dict(zip(columns, row)) for row in result]
            return {"columns": columns, "data": data}
    except Exception as e:
        return {"error": str(e), "trace": traceback.format_exc()}
    
if __name__ == "__main__":
    mcp.run(transport='sse')
