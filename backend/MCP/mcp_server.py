"""
MCP Server for HR Agent - Stdio Transport.
Provides tools for HR management operations via MCP protocol.
All tool implementations are imported from the modular tools/ directory.
"""
import os
import sys

# Add backend/ and MCP/ to path — needed both for standalone run AND when imported
# from the Flask backend (agent/core.py lazy-imports this module).
_mcp_dir     = os.path.dirname(os.path.abspath(__file__))        # backend/MCP/
_backend_dir = os.path.dirname(_mcp_dir)                         # backend/
for _p in (_backend_dir, _mcp_dir):
    if _p not in sys.path:
        sys.path.insert(0, _p)


from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
from typing import Optional, Any

# Import tool functions from modular tools
from tools.employee_tools import (
    search_employees as _search_employees,
    get_employee_by_id as _get_employee_by_id,
    get_all_employees as _get_all_employees,
    create_employee as _create_employee,
    update_employee_by_id as _update_employee_by_id,
    delete_employee_by_id as _delete_employee_by_id,
    get_employee_files as _get_employee_files
)
from tools.attendance_tools import (
    get_attendance as _get_attendance,
    update_absensi as _update_absensi
)
from tools.sql_generator import (
    generate_and_execute_sql as _generate_and_execute_sql,
    get_schema_context as _get_schema_context
)
from tools.utility_tools import (
    get_current_time as _get_current_time,
    extract_data_from_file as _extract_data_from_file
)
from tools.cv_tools import (
    get_employee_cv as _get_employee_cv,
    analyze_employee_cv as _analyze_employee_cv,
    summarize_employee_cv as _summarize_employee_cv,
    manage_cv_file as _manage_cv_file
)
from tools.analysis_tools import (
    analyze_attendance_with_policy as _analyze_attendance_with_policy
)
from tools.email_tools import (
    send_warning_letter as _send_warning_letter,
    send_email_to_employee as _send_email_to_employee,
    send_broadcast_email as _send_broadcast_email,
    reset_sp_level as _reset_sp_level,
    generate_email_content as _generate_email_content
)
from tools.export_tools import (
    export_employee_personal_data as _export_employee_personal_data,
    export_employee_operational_data as _export_employee_operational_data
)
from tools.filesystem_tools import (
    read_file as _read_file,
    write_file as _write_file,
    rename_file as _rename_file,
    delete_file as _delete_file
)
from tools.payroll_tools import (
    get_payroll_detail as _get_payroll_detail,
    get_payroll_info as _get_payroll_info,
    analyze_payroll_anomaly as _analyze_payroll_anomaly,
    export_payroll_csv as _export_payroll_csv,
    get_payroll_file as _get_payroll_file,
    create_payroll_report_pdf as _create_payroll_report_pdf,
    send_payroll_email as _send_payroll_email
)

load_dotenv()

# Initialize MCP Server (using stdio transport as per user request)
mcp = FastMCP("HRAgentMCP")


# ============================================================================
# EMPLOYEE TOOLS
# ============================================================================

@mcp.tool()
def search_employees(
    query: Optional[str] = None,
    position: Optional[str] = None,
    department: Optional[str] = None,
    status: Optional[str] = None,
    min_salary: Optional[float] = None,
    max_salary: Optional[float] = None,
    limit: int = 20
) -> dict:
    """
    Mencari dan memfilter data karyawan secara fleksibel.
    Gunakan tool ini jika user memberikan nama, email, nomor telepon (parsial atau lengkap) 
    atau ingin memfilter berdasarkan jabatan (position), departemen, status kepegawaian, 
    atau range gaji (min_salary, max_salary).
    """
    return _search_employees(query, position, department, status, min_salary, max_salary, limit)


@mcp.tool()
def get_employee_by_id(emp_id: int) -> dict:
    """
    Mengambil DETAIL LENGKAP satu karyawan spesifik.
    Gunakan ini setelah mendapatkan ID dari `search_employees`.
    Output mencakup: Gaji, data pribadi, tanggal bergabung, status pernikahan, BPJS, dll.
    
    PENTING: Output juga menyertakan:
    - `CV_FILE_PATH`: path absolut file CV karyawan (gunakan langsung untuk extract_data_from_file atau manage_cv_file)
    - `cv_info`: data profil CV lengkap (pendidikan, skill, sertifikasi, pengalaman kerja, dll)
    
    Gunakan `data.CV_FILE_PATH` dari hasil tool ini sebagai file_path di extract_data_from_file.
    """
    return _get_employee_by_id(emp_id)


@mcp.tool()
def get_all_employees(limit: int = 100) -> dict:
    """
    Mengambil daftar semua karyawan (Listing).
    Berguna untuk melihat ringkasan populasi karyawan.
    Hanya gunakan jika user meminta "semua karyawan" atau "daftar karyawan".
    """
    return _get_all_employees(limit)


@mcp.tool()
def create_employee(name: str) -> dict:
    """
    Membuat data karyawan BARU (Onboarding).
    Menerima nama lengkap dan otomatis menghasilkan Employee Code unik.
    Setelah dibuat, sarankan user untuk melengkapi data lain menggunakan `update_employee_by_id`.
    """
    return _create_employee(name)


@mcp.tool()
def update_employee_by_id(emp_id: int, updates: Any) -> dict:
    """
    Memperbarui/Edit data profil karyawan yang sudah ada di database.
    Tool ini sangat fleksibel dan secara otomatis memperbarui data personal (tabel employees)
    maupun data profesional/CV (tabel employee_cv) dalam satu transaksi tunggal.
    Dukungan field mencakup: name, email, phone, department, position, status, basic_salary,
    address, remaining_leave, sp_level, skills, education_level, certifications, dll.
    """
    return _update_employee_by_id(emp_id, updates)


@mcp.tool()
def delete_employee_by_id(emp_id: int) -> dict:
    """
    MENGHAPUS karyawan secara permanen (Hard Delete).
    Hati-hati: Aksi ini tidak bisa dibatalkan.
    Biasanya memerlukan konfirmasi user sebelum eksekusi.
    """
    return _delete_employee_by_id(emp_id)


@mcp.tool()
def get_employee_files(emp_id: int) -> dict:
    """
    Ambil daftar semua file penting milik satu karyawan:
    file CV (employee_cv.file_path) dan slip gaji (payroll_slips.file_path).
    
    Mengembalikan abs_path dan server_url untuk setiap file.
    WAJIB dipanggil sebelum extract_data_from_file agar path file akurat.
    """
    return _get_employee_files(emp_id)


# ============================================================================
# ATTENDANCE TOOLS
# ============================================================================

@mcp.tool()
def get_attendance(
    date: Optional[str] = None,
    status: Optional[str] = None,
    work_location: Optional[str] = None,
    limit: int = 100
) -> dict:
    """
    Mengambil data absensi karyawan dengan filter opsional tanggal, status, dan lokasi kerja.
    Gunakan tool ini jika user menanyakan absensi hari ini, kemarin, keterlambatan, atau WFH/WFO.
    date: Tanggal absensi dalam format YYYY-MM-DD (opsional, default: hari ini).
    status: Status kehadiran karyawan, misal 'late', 'ontime' (opsional).
    work_location: Lokasi kerja karyawan, misal 'Office' (WFO) atau 'Remote' (WFH) (opsional).
    """
    return _get_attendance(date, status, work_location, limit)





@mcp.tool()
def update_absensi(absen_id: int, updates: dict) -> dict:
    """
    Koreksi data absensi manual.
    Gunakan jika ada kesalahan data check-in/check-out atau perubahan status kehadiran.
    Memerlukan ID Absensi (bukan ID Karyawan).
    """
    return _update_absensi(absen_id, updates)



# ============================================================================
# CV TOOLS
# ============================================================================

@mcp.tool()
def get_employee_cv(emp_id: int) -> dict:
    """
    Ambil data CV/profil lengkap karyawan dari database.
    Mencakup pendidikan, pengalaman kerja, skill, sertifikasi, dan file CV.
    Gunakan ini untuk melihat profil profesional karyawan secara mendalam.
    """
    return _get_employee_cv(emp_id)


@mcp.tool()
def analyze_employee_cv(emp_id: int, focus: str = "general") -> dict:
    """
    Analisa mendalam CV karyawan menggunakan AI.
    Focus options: "general", "skills", "career", "compensation", "performance".
    Menghasilkan insight, rekomendasi, dan evaluasi berdasarkan data CV.
    """
    return _analyze_employee_cv(emp_id, focus)


from typing import Optional

@mcp.tool()
def summarize_employee_cv(emp_id: int, question: Optional[str] = None) -> dict:
    """
    Rangkum CV karyawan atau jawab pertanyaan spesifik tentang CV.
    Jika question=None, menghasilkan rangkuman umum.
    Contoh question: "Apa skill utama karyawan ini?", "Berapa lama pengalaman kerjanya?"
    """
    return _summarize_employee_cv(emp_id, question)


@mcp.tool()
def manage_cv_file(emp_id: int, action: str, file_path: Optional[str] = None) -> dict:
    """
    Kelola file CV karyawan: upload, replace, atau delete.
    action: "upload" (tambah baru), "replace" (ganti file lama), "delete" (hapus file).
    file_path wajib untuk action upload/replace.
    """
    return _manage_cv_file(emp_id, action, file_path)


# ============================================================================
# ANALYSIS TOOLS
# ============================================================================

@mcp.tool()
def analyze_attendance_with_policy(
    query: str,
    emp_id: int = None,
    period: str = "monthly"
) -> dict:
    """
    Analisa data absensi/kehadiran berdasarkan kebijakan perusahaan (RAG-based).
    Menggabungkan data real-time dari database dengan dokumen kebijakan perusahaan.
    Gunakan untuk pertanyaan seperti "Apakah kehadiran karyawan X sesuai kebijakan?"
    period: "daily", "weekly", "monthly", atau "yearly".
    """
    return _analyze_attendance_with_policy(query, emp_id, period)


# ============================================================================
# SQL TOOLS
# ============================================================================

@mcp.tool()
def get_schema_context() -> dict:
    """
    Mengambil skema database Oracle (tabel + kolom + deskripsi) sebagai konteks untuk generate_and_execute_sql.
    
    WAJIB dipanggil SEBELUM generate_and_execute_sql. Hasilnya (field 'schema') harus
    diteruskan sebagai parameter schema_context ke generate_and_execute_sql.
    """
    return _get_schema_context()


@mcp.tool()
def generate_and_execute_sql(
    natural_query: str,
    execute: bool = True,
    limit: int = 100,
    schema_context: str = None
) -> dict:
    """
    Generator & Eksekutor SQL Oracle Otomatis.
    
    Konversi natural language ke SQL dan eksekusi ke database Oracle.
    
    WAJIB: Panggil get_schema_context terlebih dahulu, lalu oper field 'schema'-nya
    ke parameter schema_context di sini agar SQL generator tahu nama kolom yang tepat.
    """
    return _generate_and_execute_sql(natural_query, execute, limit, schema_context)


# ============================================================================
# EMAIL TOOLS
# ============================================================================

@mcp.tool()
def send_warning_letter(
    emp_id: int, 
    reason: Optional[str] = "", 
    issued_by: int = 1,
    attachments: Optional[Any] = None
) -> dict:
    """
    Kirim Surat Peringatan (SP) ke karyawan via email dan increment level SP.
    SP1 = Peringatan Pertama, SP2 = Peringatan Kedua, SP3 = Peringatan Ketiga.
    Memerlukan konfirmasi user sebelum eksekusi karena berdampak pada rekam jejak karyawan.
    
    attachments: File tunggal atau daftar file (path lokal, URL, atau nama file temp) untuk dilampirkan.
    """
    return _send_warning_letter(emp_id, reason, issued_by, attachments)


@mcp.tool()
def send_email_to_employee(
    emp_id: int, 
    subject: Optional[str] = "", 
    message: Optional[str] = "",
    attachments: Optional[Any] = None,
    auto_polish: bool = True
) -> dict:
    """
    Kirim email kustom ke satu karyawan tertentu dengan opsi pemolesan profesional otomatis dan lampiran file.
    Gunakan untuk komunikasi personal: pengumuman, reminder, atau informasi khusus.
    
    attachments: File tunggal atau list file (path lokal, URL server, atau nama file temp) untuk dilampirkan.
    auto_polish: Jika True (default), pesan kasual akan dipoles secara otomatis menggunakan AI agar terdengar sangat profesional dalam bahasa Indonesia.
    """
    return _send_email_to_employee(emp_id, subject, message, attachments, auto_polish)


@mcp.tool()
def send_broadcast_email(
    subject: Optional[str] = "",
    message: Optional[str] = "",
    department: Optional[str] = None,
    attachments: Optional[Any] = None,
    auto_polish: bool = True
) -> dict:
    """
    Kirim email broadcast ke semua karyawan aktif dengan opsi pemolesan profesional otomatis dan lampiran file.
    Jika department diisi, hanya dikirim ke karyawan departemen tersebut.
    Gunakan untuk pengumuman perusahaan, kebijakan baru, atau informasi massal.
    
    attachments: File tunggal atau list file (path lokal, URL server, atau nama file temp) untuk dilampirkan.
    auto_polish: Jika True (default), pesan kasual akan dipoles secara otomatis menggunakan AI agar terdengar sangat profesional dalam bahasa Indonesia.
    """
    return _send_broadcast_email(subject, message, department, attachments, auto_polish)


@mcp.tool()
def reset_sp_level(emp_id: int, reason: str = "Pemutihan SP") -> dict:
    """
    Reset level Surat Peringatan (SP) karyawan kembali ke 0.
    Gunakan untuk pemutihan SP setelah masa pembinaan selesai.
    Memerlukan konfirmasi user karena mengubah rekam jejak karyawan.
    """
    return _reset_sp_level(emp_id, reason)


@mcp.tool()
def generate_email_content(recipient_name: Optional[str] = "", context: Optional[str] = "") -> dict:
    """
    Gunakan LLM untuk menyusun konten email (subjek & pesan) agar lebih profesional, padat, dan jelas berdasarkan konteks yang diberikan.
    Hasil dari tool ini bisa di-pass ke `send_email_to_employee` atau `send_broadcast_email`.
    """
    return _generate_email_content(recipient_name, context)


# ============================================================================
# EXPORT TOOLS
# ============================================================================

@mcp.tool()
def export_employee_personal_data(department: str = None) -> dict:
    """
    Export data pribadi karyawan ke file CSV.
    Mencakup: employee_code, name, email, phone, department, position, status, address, dll.
    Jika department diisi, hanya mengexport karyawan departemen tersebut.
    """
    return _export_employee_personal_data(department)


@mcp.tool()
def export_employee_operational_data(
    period: str = "all",
    year: int = None,
    month: int = None
) -> dict:
    """
    Export data operasional karyawan ke file CSV.
    Mencakup: sisa cuti, total absensi (ontime, terlambat, absen, remote).
    period: "all", "yearly", atau "monthly".
    """
    return _export_employee_operational_data(period, year, month)


# ============================================================================
# FILESYSTEM TOOLS
# ============================================================================

@mcp.tool()
def read_file(file_path: str, encoding: str = "utf-8") -> dict:
    """
    Baca isi file teks (txt, md, csv, json, log, html, yaml).
    File PDF/DOCX tidak bisa dibaca langsung — gunakan extract_data_from_file untuk itu.
    """
    return _read_file(file_path, encoding)


@mcp.tool()
def write_file(file_path: str, content: str, overwrite: bool = False) -> dict:
    """
    Buat atau timpa file teks dalam direktori yang diizinkan.
    overwrite=False (default) mencegah penimpaan file yang sudah ada secara tidak sengaja.
    """
    return _write_file(file_path, content, overwrite)


@mcp.tool()
def rename_file(file_path: str, new_name: str) -> dict:
    """
    Ganti nama file dalam direktori yang sama.
    Tidak bisa memindahkan file ke folder berbeda, hanya rename.
    Contoh new_name: 'RafaelRichieCurriculumVitae.pdf'
    """
    return _rename_file(file_path, new_name)


@mcp.tool()
def delete_file(file_path: str) -> dict:
    """
    Hapus file dari direktori yang diizinkan. Hanya file individual, bukan folder.
    HATI-HATI: Aksi ini tidak bisa dibatalkan.
    """
    return _delete_file(file_path)


# ============================================================================
# PAYROLL TOOLS
# ============================================================================

@mcp.tool()
def get_payroll_detail(
    emp_id: int,
    month: int = None,
    year: int = None
) -> dict:
    """
    Ambil detail slip gaji karyawan.
    Jika month/year kosong, menampilkan semua periode yang tersedia.
    """
    return _get_payroll_detail(emp_id, month, year)


@mcp.tool()
def get_payroll_info(
    emp_id: int,
    month: int = None,
    year: int = None
) -> dict:
    """
    Ambil informasi detail penggajian termasuk rincian tunjangan dan potongan.
    Lebih detail dari get_payroll_detail — mencakup breakdown komponen gaji.
    """
    return _get_payroll_info(emp_id, month, year)


@mcp.tool()
def analyze_payroll_anomaly(
    emp_id: int = None,
    period_count: int = 6
) -> dict:
    """
    Analisa anomali penggajian menggunakan AI.
    Mendeteksi kenaikan/penurunan gaji yang tidak wajar dari periode ke periode.
    emp_id=None untuk analisa semua karyawan, isi emp_id untuk satu karyawan spesifik.
    """
    return _analyze_payroll_anomaly(emp_id, period_count)


@mcp.tool()
def export_payroll_csv(
    department: str = None,
    month: int = None,
    year: int = None
) -> dict:
    """
    Export laporan payroll ke file CSV.
    Bisa difilter per departemen, bulan, atau tahun.
    """
    return _export_payroll_csv(department, month, year)


@mcp.tool()
def get_payroll_file(
    emp_id: int,
    month: int = None,
    year: int = None
) -> dict:
    """
    Ambil file slip gaji PDF yang sudah ada untuk karyawan tertentu.
    Lebih cepat dari create_payroll_report_pdf karena tidak membuat ulang PDF.
    """
    return _get_payroll_file(emp_id, month, year)


@mcp.tool()
def create_payroll_report_pdf(
    emp_id: int,
    month: int = None,
    year: int = None
) -> dict:
    """
    Buat slip gaji PDF untuk karyawan.
    Menghasilkan file PDF baru yang bisa diunduh atau dikirim via email.
    """
    return _create_payroll_report_pdf(emp_id, month, year)


@mcp.tool()
def send_payroll_email(
    emp_id: int,
    month: int = None,
    year: int = None
) -> dict:
    """
    Kirim email slip gaji ke karyawan.
    Otomatis mencari atau membuat file PDF slip gaji sebelum mengirim email.
    """
    return _send_payroll_email(emp_id, month, year)


# ============================================================================
# UTILITY TOOLS
# ============================================================================

@mcp.tool()
def get_current_time() -> dict:
    """Mengambil waktu dan tanggal saat ini."""
    return _get_current_time()


@mcp.tool()
def extract_data_from_file(file_path: str, instruction: str) -> dict:
    """
    Ekstrak data secara fleksibel dan universal dari dokumen (PDF, DOCX, TXT)
    menggunakan AI berdasarkan instruksi/kebutuhan spesifik yang diberikan.
    Gunakan tool ini untuk mengekstrak informasi apa pun dari file yang diunggah.
    
    file_path: Path absolut file dokumen atau URL server.
    instruction: Petunjuk/kriteria data apa saja yang ingin diekstrak (contoh: "ekstrak CV lengkap", "ambil no KTP dan NPWP").
    """
    return _extract_data_from_file(file_path, instruction)


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="HR Agent MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="sse",          # Default: SSE so Flask backend can connect via HTTP
        help="Transport type: sse (default for backend integration) or stdio (for Claude Desktop)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for SSE transport (default: 8000)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host for SSE transport (default: 0.0.0.0)"
    )
    args = parser.parse_args()
    
    if args.transport == "sse":
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        print(f"[MCP Server] Starting HR Agent MCP Server via SSE on http://{args.host}:{args.port}/sse")
    else:
        print(f"[MCP Server] Starting HR Agent MCP Server via stdio (Claude Desktop mode)")
    
    mcp.run(transport=args.transport)

