import os
import cx_Oracle
from datetime import datetime
import random
import re
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine
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
def add_employee(name: str) -> str:
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
def update_employee_details(name: str, updates: dict) -> str:
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

        # Ambil ID berdasarkan nama karyawan
        cur.execute("SELECT id FROM SMARTBOT.employees WHERE name = :name", {"name": name})
        row = cur.fetchone()
        if not row:
            return f"⚠️ Karyawan dengan nama '{name}' tidak ditemukan."
        emp_id = row[0]

        # Ambil kolom valid dari tabel employee_details
        cur.execute("SELECT * FROM SMARTBOT.employee_details WHERE ROWNUM = 1")
        valid_columns = set(desc[0].lower() for desc in cur.description if desc[0].lower() != "id")

        # Filter hanya kolom yang valid
        clean_updates = {k: v for k, v in updates.items() if k.lower() in valid_columns}
        if not clean_updates:
            return "⚠️ Tidak ada kolom valid untuk diperbarui."

        clean_updates["emp_id"] = emp_id

        # Cek apakah detail sudah ada
        cur.execute("SELECT id FROM SMARTBOT.employee_details WHERE emp_id = :id", {"id": emp_id})
        exists = cur.fetchone()

        if exists:
            set_clause = ", ".join(f"{k} = :{k}" for k in clean_updates if k != "emp_id")
            cur.execute(f"""
                UPDATE SMARTBOT.employee_details SET {set_clause}
                WHERE emp_id = :emp_id
            """, clean_updates)
        else:
            columns = ", ".join(clean_updates.keys())
            values = ", ".join(f":{k}" for k in clean_updates)
            cur.execute(f"""
                INSERT INTO SMARTBOT.employee_details ({columns}) VALUES ({values})
            """, clean_updates)

        conn.commit()
        return f"✅ Data detail untuk '{name}' berhasil disimpan."
    except Exception as e:
        return f"❌ Gagal memperbarui detail: {e}\n{traceback.format_exc()}"
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass


@mcp.tool()
def list_employees(limit: int = 100) -> str:
    """
    Ambil semua data karyawan lengkap dengan detailnya. Cocok untuk ditampilkan sebagai tabel markdown.
    Maksimal 100 baris agar tetap cepat.
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
def find_by_id(emp_id: int) -> dict:
    """
    Mencari satu data karyawan secara lengkap berdasarkan ID unik yang dimiliki setiap karyawan. ID ini berasal dari sistem dan tidak bisa ditentukan manual oleh pengguna. Fungsi ini akan menampilkan data dasar dari tabel employees sekaligus semua detail tambahan dari tabel employee_details, jika tersedia. Ini sangat berguna ketika pengguna mengetahui ID pasti seorang karyawan dan ingin menampilkan semua informasi terkait secara cepat.

    Contoh pertanyaan pengguna yang cocok:

    "Tampilkan data lengkap karyawan dengan id 3"

    "Aku butuh informasi detail karyawan ID 17"

    "Siapa yang punya ID 12, dan apa posisinya?"

    Parameter:

    emp_id (int): ID karyawan, wajib diisi.

    Keluaran:

    Dictionary berisi pasangan nama kolom dan nilainya, atau pesan error jika ID tidak ditemukan
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
def search_name(name: str, limit: int = 20) -> dict:
    """
        Fungsi ini digunakan untuk mencari karyawan berdasarkan nama atau sebagian dari nama mereka. Sistem akan melakukan pencarian dengan metode case-insensitive dan menggunakan wildcard %, sehingga kata kunci seperti “andi” bisa menemukan “Andi Setiawan”, “Andika”, dan “Handi”.

        Cocok untuk digunakan saat pengguna hanya tahu nama depan, nama panggilan, atau hanya ingat sebagian nama.

        Contoh pertanyaan:

        "Cari karyawan bernama Andi"

        "Siapa saja yang namanya mengandung 'nugroho'?"

        "Saya lupa nama lengkapnya, tapi kayaknya ada 'fitri' di namanya"

        Parameter:

        name (str): Kata kunci nama yang ingin dicari.

        limit (int, default 20): Jumlah maksimal hasil yang ingin ditampilkan.

        Keluaran:

        Dictionary dengan dua elemen:

        columns: daftar nama kolom.

        data: list baris hasil pencarian dalam bentuk list of list.
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
def search_email(email: str, limit: int = 20) -> dict:
    """
        Menemukan data karyawan berdasarkan alamat email. Ideal digunakan jika pengguna mengetahui email lengkap atau sebagian dari email yang terkait dengan karyawan. Sistem mencari secara case-insensitive dan menggunakan wildcard, sehingga pencarian seperti “@company.com” bisa menemukan banyak entri sekaligus.

        Contoh prompt:

        "Cari karyawan dengan email andi@example.com"

        "Siapa yang pakai email @smartbot.co.id?"

        "Saya cuma ingat bagian belakangnya, seperti .org, bisa dicari?"

        Parameter:

        email (str): Kata kunci alamat email.

        limit (int, default 20): Jumlah maksimal hasil yang ingin ditampilkan.

        Keluaran:

        Dictionary berisi kolom dan data karyawan yang cocok dengan email tersebut.
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
def search_phone(phone: str, limit: int = 20) -> dict:
    """
        Digunakan untuk mencari karyawan berdasarkan nomor telepon. Sistem akan mencari nomor yang mengandung substring tertentu, sehingga sangat fleksibel untuk kasus ketika pengguna hanya ingat sebagian nomor. Pencarian tidak case-sensitive, dan cocok untuk data lokal maupun internasional.

        Contoh prompt:

        "Cari karyawan dengan nomor 0812345"

        "Nomor 62-812 ada di data siapa?"

        "Saya cuma ingat 123, coba cari siapa yang punya"

        Parameter:

        phone (str): Angka atau bagian dari nomor telepon.

        limit (int, default 20): Maksimal jumlah hasil.

        Keluaran:

        Dictionary dengan hasil pencarian yang menampilkan semua kolom relevan seperti nama, posisi, email, dan sebagainya.

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
def filter_position(position: str, limit: int = 50) -> dict:
    """
        Fungsi ini memfilter semua karyawan yang memiliki posisi tertentu di perusahaan. Posisi bisa berupa “Manager”, “Staff”, “Software Engineer”, dan sebagainya, sesuai nilai yang disimpan di kolom position pada tabel employee_details. Sistem akan melakukan pencarian menggunakan LIKE dan case-insensitive, jadi sangat fleksibel terhadap variasi input pengguna.

        Contoh prompt:

        "Tampilkan semua karyawan dengan posisi manager"

        "Siapa saja yang Software Engineer?"

        "Saya ingin melihat semua yang bekerja sebagai marketing"

        Parameter:

        position (str): Nama jabatan atau posisi.

        limit (int, default 50): Batas jumlah hasil.

        Keluaran:

        Dictionary berisi kolom dan data karyawan dengan posisi yang sesuai.
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
def filter_status(status: str, limit: int = 50) -> dict:
    """
        Memfilter karyawan berdasarkan status kepegawaian seperti "tetap", "kontrak", atau "magang". Berguna untuk HR yang ingin mengetahui siapa saja yang masih kontrak atau sudah menjadi karyawan tetap. Input bersifat case-insensitive dan nilai status harus sesuai dengan data di kolom status pada employee_details.

        Contoh prompt:

        "Lihat semua karyawan dengan status kontrak"

        "Tampilkan siapa saja yang masih magang"

        "Siapa yang sudah tetap?"

        Parameter:

        status (str): Status pekerjaan. Contoh: "tetap", "kontrak".

        limit (int, default 50): Jumlah maksimal hasil.

        Keluaran:

        Dictionary yang menampilkan daftar karyawan sesuai status.
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
def salary_above(min_salary: float, limit: int = 50) -> dict:
    """
        Menampilkan daftar karyawan yang memiliki gaji di atas atau sama dengan nilai tertentu. Fungsi ini sangat berguna untuk mencari karyawan dengan penghasilan tinggi, baik untuk keperluan audit, evaluasi kompensasi, ataupun seleksi internal berdasarkan performa atau jabatan strategis.

        Contoh pertanyaan pengguna:

        "Siapa saja karyawan yang gajinya di atas 10 juta?"

        "Tampilkan semua orang dengan gaji lebih dari 5 juta."

        "Saya ingin melihat daftar karyawan bergaji tinggi."

        "Ada berapa banyak karyawan dengan gaji minimal 8 juta?"

        Fungsi ini akan menampilkan hasil dari gabungan tabel employees dan employee_details, yang mencakup:

        id: ID karyawan.

        name: Nama lengkap.

        position: Jabatan atau peran.

        status: Status kepegawaian (tetap, kontrak, dsb).

        salary: Gaji pokok.

        phone: Nomor HP (jika tersedia).

        email: Email aktif.

        gender: Jenis kelamin.

        marital: Status pernikahan.

        sp: Jumlah surat peringatan.

        Parameter:

        min_salary (float): Nilai batas bawah gaji yang ingin dicari. Karyawan dengan gaji sama atau di atas nilai ini akan ditampilkan.

        limit (int, default: 50): Jumlah maksimum data yang dikembalikan. Bisa disesuaikan sesuai kebutuhan pengguna.

        Fungsi menggunakan perintah SQL dengan kondisi WHERE salary >= :1 dan batas FETCH FIRST :2 ROWS ONLY untuk memastikan efisiensi kueri.
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
def salary_below(max_salary: float, limit: int = 50) -> dict:
    """
        Menampilkan daftar karyawan yang memiliki gaji di bawah atau sama dengan nilai tertentu. Fungsi ini digunakan untuk keperluan monitoring keseimbangan struktur gaji, pemetaan pegawai dengan gaji rendah, atau evaluasi potensi kenaikan kompensasi bagi pegawai dengan pendapatan minim.

        Contoh pertanyaan pengguna:

        "Tampilkan semua karyawan dengan gaji di bawah 5 juta."

        "Siapa saja yang gajinya kurang dari 6 juta?"

        "Saya ingin tahu siapa saja yang masih digaji kecil."

        "Ada berapa pegawai magang dengan gaji rendah?"

        Fungsi mengembalikan kolom yang sama dengan salary_above, yaitu semua informasi dasar dan detail pegawai yang tersedia.

        Parameter:

        max_salary (float): Nilai batas atas gaji. Semua karyawan dengan gaji sama atau di bawah nilai ini akan ditampilkan.

        limit (int, default: 50): Jumlah maksimum hasil yang ditampilkan. Gunakan angka lebih tinggi bila diperlukan hasil lebih lengkap.

        Pencarian dilakukan dengan kueri WHERE salary <= :1, digabungkan dari tabel employees dan employee_details melalui JOIN.
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

# @mcp.tool()
# def import_from_file(filepath: str) -> str:
#     """
#     Mengimpor data karyawan dari file eksternal ke database secara otomatis. Sistem mendukung berbagai jenis file seperti CSV, Excel, TXT, DOCX, PDF, dan SQL.

#     File dapat berupa tabel terstruktur (seperti .csv atau .xlsx) maupun narasi bebas (seperti .txt, .docx, .pdf). Sistem akan mencoba mengenali informasi penting seperti nama, jabatan, gaji, dan kontak karyawan secara cerdas dari isi dokumen, lalu menambahkan data tersebut ke dalam dua tabel utama: `employees` dan `employee_details`.

#     Contoh pertanyaan pengguna:
#     - "Saya punya file .csv daftar karyawan, tolong masukkan ke sistem."
#     - "Ada dokumen PDF berisi biodata karyawan, bisa langsung diimpor?"
#     - "File ini naratif, isinya seperti: Nama: Andi, Posisi: HR, Email: andi@... — apakah bisa dimasukkan ke sistem?"

#     Format yang didukung:
#     - `.csv`, `.xlsx`: Akan dibaca sebagai tabel, dengan kolom minimal `name`.
#     - `.txt`, `.docx`, `.pdf`: Akan diekstrak menjadi teks biasa dan dianalisis menggunakan regex.
#     - `.sql`: Akan langsung dieksekusi sebagai query ke database.

#     Informasi yang dapat dikenali secara otomatis:
#     - name, position, status, salary, phone, email, gender, marital, sp

#     Jika hanya nama yang dikenali, maka hanya akan dimasukkan ke tabel `employees`.
#     Jika detail lainnya tersedia, akan dimasukkan ke `employee_details` juga.

#     Contoh narasi dalam file:
#     "Nama: Siti Aminah\nPosisi: Staff Marketing\nGaji: 5.000.000\nEmail: siti@company.com\nStatus: kontrak"

#     """
#     try:
#         from docx import Document

#         text = ""

#         if filepath.endswith(".csv"):
#             df = pd.read_csv(filepath)
#         elif filepath.endswith(".xlsx"):
#             df = pd.read_excel(filepath)
#         elif filepath.endswith(".txt"):
#             with open(filepath, encoding="utf-8") as f:
#                 text = f.read()
#         elif filepath.endswith(".docx"):
#             doc = Document(filepath)
#             text = "\n".join([p.text for p in doc.paragraphs])
#         elif filepath.endswith(".pdf"):
#             import PyPDF2
#             with open(filepath, "rb") as f:
#                 reader = PyPDF2.PdfReader(f)
#                 for page in reader.pages:
#                     text += page.extract_text() + "\n"
#         elif filepath.endswith(".sql"):
#             with open(filepath, "r", encoding="utf-8") as f:
#                 sql = f.read()
#             with engine.begin() as conn:
#                 conn.execute(sql)
#             return "✅ Query SQL berhasil dijalankan."
#         else:
#             return "❌ Format file tidak didukung."

#         if text:
#             pattern_map = {
#                 "name": r"(?i)nama[:\s]+([\w\s]+)",
#                 "position": r"(?i)posisi[:\s]+([\w\s]+)",
#                 "status": r"(?i)status[:\s]+([\w]+)",
#                 "salary": r"(?i)gaji[:\s]+(\d+[.,]?\d*)",
#                 "phone": r"(?i)telepon[:\s]+([\d\-+() ]+)",
#                 "email": r"(?i)email[:\s]+([\w._%+-]+@[\w.-]+)",
#                 "gender": r"(?i)jenis kelamin[:\s]+(\w+)",
#                 "marital": r"(?i)status pernikahan[:\s]+(\w+)",
#                 "sp": r"(?i)surat peringatan[:\s]+(\d+)"
#             }
#             data = {}
#             for key, pattern in pattern_map.items():
#                 match = re.search(pattern, text)
#                 if match:
#                     data[key] = match.group(1).strip()
#             if "name" not in data:
#                 return "❌ Gagal mengenali nama dalam narasi."
#             df = pd.DataFrame([data])

#         df = df.fillna(None)
#         conn = cx_Oracle.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=dsn)
#         cur = conn.cursor()

#         for _, row in df.iterrows():
#             id_var = cur.var(cx_Oracle.NUMBER)
#             cur.execute("INSERT INTO SMARTBOT.employees (name) VALUES (:1) RETURNING id INTO :2", [row["name"], id_var])
#             emp_id = int(id_var.getvalue()[0])

#             detail_data = {
#                 "emp_id": emp_id,
#                 "position": row.get("position"),
#                 "status": row.get("status"),
#                 "salary": row.get("salary"),
#                 "phone": row.get("phone"),
#                 "email": row.get("email"),
#                 "gender": row.get("gender"),
#                 "marital": row.get("marital"),
#                 "sp": row.get("sp")
#             }
#             detail_data = {k: v for k, v in detail_data.items() if v is not None}

#             if detail_data:
#                 columns = ', '.join(detail_data.keys())
#                 values = ', '.join(f":{k}" for k in detail_data.keys())
#                 cur.execute(f"INSERT INTO SMARTBOT.employee_details ({columns}) VALUES ({values})", detail_data)

#         conn.commit()
#         cur.close()
#         conn.close()

#         return f"✅ Data dari file {os.path.basename(filepath)} berhasil diimpor."
#     except Exception as e:
#         return f"❌ Gagal import: {e}"



if __name__ == "__main__":
    mcp.run(transport='sse')
