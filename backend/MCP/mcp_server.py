"""
MCP Server for HR Agent - Stdio Transport.
Provides tools for HR management operations via MCP protocol.
All tool implementations are imported from the modular tools/ directory.
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

# Import tool functions from modular tools
from tools.employee_tools import (
    search_employees as _search_employees,
    get_employee_by_id as _get_employee_by_id,
    get_all_employees as _get_all_employees,
    create_employee as _create_employee,
    update_employee_by_id as _update_employee_by_id,
    delete_employee_by_id as _delete_employee_by_id,
    filter_employees_by_position as _filter_employees_by_position,
    filter_employees_by_status as _filter_employees_by_status,
    filter_employees_salary_above as _filter_employees_salary_above,
    filter_employees_salary_below as _filter_employees_salary_below
)
from tools.attendance_tools import (
    get_today_attendance as _get_today_attendance,
    get_today_late_employees as _get_today_late_employees,
    get_today_remote_employees as _get_today_remote_employees,
    get_today_onsite_employees as _get_today_onsite_employees,
    update_absensi as _update_absensi
)
from tools.leave_tools import (
    get_employee_leave_by_id as _get_employee_leave_by_id,
    get_all_employee_leaves as _get_all_employee_leaves,
    update_leaves as _update_leaves
)
from tools.sql_generator import (
    generate_and_execute_sql as _generate_and_execute_sql
)
from tools.utility_tools import (
    get_current_time as _get_current_time
)

load_dotenv()

# Initialize MCP Server (using stdio transport as per user request)
mcp = FastMCP("HRAgentMCP")


# ============================================================================
# EMPLOYEE TOOLS
# ============================================================================

@mcp.tool()
def search_employees(query: str, limit: int = 20) -> dict:
    """
    Mencari data karyawan secara fleksibel (Fuzzy Search).
    Gunakan tool ini jika user memberikan nama, email, atau nomor telepon (parsial atau lengkap).
    Output mencakup: ID, nama, departemen, posisi, dan kontak dasar.
    """
    return _search_employees(query, limit)


@mcp.tool()
def get_employee_by_id(emp_id: int) -> dict:
    """
    Mengambil DETAIL LENGKAP satu karyawan spesifik.
    Gunakan ini setelah mendapatkan ID dari `search_employees`.
    Output mencakup: Gaji, data pribadi, tanggal bergabung, status pernikahan, BPJS, dll.
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
def update_employee_by_id(emp_id: int, updates: dict) -> dict:
    """
    Memperbarui/Edit data karyawan yang sudah ada.
    Dukungan field: name, email, phone, department, position, status, salary, address, dll.
    Pastikan emp_id valid sebelum memanggil ini.
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
def filter_employees_by_position(position: str, limit: int = 50) -> dict:
    """Filter karyawan berdasarkan jabatan/posisi."""
    return _filter_employees_by_position(position, limit)


@mcp.tool()
def filter_employees_by_status(status: str, limit: int = 50) -> dict:
    """Filter karyawan berdasarkan status kepegawaian (tetap, kontrak, magang)."""
    return _filter_employees_by_status(status, limit)


@mcp.tool()
def filter_employees_salary_above(min_salary: float, limit: int = 50) -> dict:
    """Filter karyawan dengan gaji di atas threshold."""
    return _filter_employees_salary_above(min_salary, limit)


@mcp.tool()
def filter_employees_salary_below(max_salary: float, limit: int = 50) -> dict:
    """Filter karyawan dengan gaji di bawah threshold."""
    return _filter_employees_salary_below(max_salary, limit)


# ============================================================================
# ATTENDANCE TOOLS
# ============================================================================

@mcp.tool()
def get_today_attendance(limit: int = 100) -> dict:
    """
    Melihat log absensi HARI INI (Real-time).
    Menampilkan siapa saja yang sudah Check-in, Check-out, atau sedang istirahat hari ini.
    """
    return _get_today_attendance(limit)


@mcp.tool()
def get_today_late_employees(limit: int = 100) -> dict:
    """
    Mencari karyawan yang TERLAMBAT (Late) hari ini.
    Gunakan untuk monitoring kedisiplinan harian.
    """
    return _get_today_late_employees(limit)


@mcp.tool()
def get_today_remote_employees(limit: int = 100) -> dict:
    """
    Mencari karyawan yang bekerja REMOTE (WFH) hari ini.
    """
    return _get_today_remote_employees(limit)


@mcp.tool()
def get_today_onsite_employees(limit: int = 100) -> dict:
    """
    Mencari karyawan yang bekerja di KANTOR (WFO/Onsite) hari ini.
    """
    return _get_today_onsite_employees(limit)





@mcp.tool()
def update_absensi(absen_id: int, updates: dict) -> dict:
    """
    Koreksi data absensi manual.
    Gunakan jika ada kesalahan data check-in/check-out atau perubahan status kehadiran.
    Memerlukan ID Absensi (bukan ID Karyawan).
    """
    return _update_absensi(absen_id, updates)


# ============================================================================
# LEAVE TOOLS
# ============================================================================

@mcp.tool()
def get_employee_leave_by_id(emp_id: int) -> dict:
    """Mengambil data cuti karyawan berdasarkan ID karyawan."""
    return _get_employee_leave_by_id(emp_id)


@mcp.tool()
def get_all_employee_leaves(limit: int = 100) -> dict:
    """Mengambil data cuti semua karyawan untuk monitoring HR."""
    return _get_all_employee_leaves(limit)


@mcp.tool()
def update_leaves(emp_id: int, updates: dict) -> dict:
    """Memperbarui data cuti karyawan."""
    return _update_leaves(emp_id, updates)


# ============================================================================
# SQL GENERATOR TOOL
# ============================================================================

@mcp.tool()
def generate_and_execute_sql(
    natural_query: str,
    execute: bool = True,
    limit: int = 100
) -> dict:
    """
    [ADVANCED] Generator & Eksekutor SQL Oracle Otomatis.
    Gunakan tool ini sebagai "Senjata Pamungkas" jika tool spesifik lain tidak tersedia. 
    Sangat ampuh untuk:
    1. Query Agregasi: Count, Sum, Avg (e.g., "Total gaji per departemen", "Rata-rata cuti").
    2. Cross-Table Joins: Menghubungkan karyawan dengan absensi, cuti, atau peringatan.
    3. Filter Kompleks: Kondisi WHERE yang rumit (e.g., "Karyawan tetap yang join > 2 tahun lalu").
    4. Bulk Updates/Deletes: "Ubah status semua karyawan magang menjadi kontrak".
    
    Jangan gunakan untuk query simpel yang sudah ada tool-nya (seperti search employee by name).
    """
    return _generate_and_execute_sql(natural_query, execute, limit)


# ============================================================================
# UTILITY TOOLS
# ============================================================================

@mcp.tool()
def get_current_time() -> dict:
    """Mengambil waktu dan tanggal saat ini."""
    return _get_current_time()


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="HR Agent MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport type: stdio (default) or sse"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for SSE transport (default: 8000)"
    )
    args = parser.parse_args()
    
    print(f"[MCP Server] Starting HR Agent MCP Server with {args.transport} transport...")
    
    if args.transport == "sse":
        mcp.settings.host = "0.0.0.0"
        mcp.settings.port = args.port
        print(f"[MCP Server] SSE mode on port {args.port}")
    
    mcp.run(transport=args.transport)
