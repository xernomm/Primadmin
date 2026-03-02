"""
Filesystem tools for HR Agent.
Gives the agent safe, sandboxed access to read/write/list/delete files
within pre-approved directories (CV uploads, exports, documents, payroll).
"""
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

# ── Allowed base directories (imported from central config) ──────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config import CV_DIR, EXPORTS_DIR, PAYROLL_EXPORTS_DIR, DOCUMENTS_DIR, BACKEND_DIR, UPLOADS_DIR

# Directories the agent is allowed to operate in.
# Paths are resolved to absolute so symlink tricks don't bypass the check.
ALLOWED_BASE_DIRS: List[Path] = [
    CV_DIR.resolve(),
    UPLOADS_DIR.resolve(),
    EXPORTS_DIR.resolve(),
    PAYROLL_EXPORTS_DIR.resolve(),
    DOCUMENTS_DIR.resolve(),
]

# File extensions the agent can READ as text
READABLE_TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".log", ".html", ".xml", ".yaml", ".yml"}

# Max file size for read_file (5 MB)
MAX_READ_BYTES = 5 * 1024 * 1024


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_and_validate(path_str: str, must_exist: bool = True) -> tuple[Path, str | None]:
    """
    Resolve path and verify it is inside an allowed directory.
    Returns (resolved_path, error_message_or_None).
    """
    try:
        p = Path(path_str).resolve()
    except Exception as e:
        return Path("."), f"Path tidak valid: {e}"

    # Check against allowed dirs
    allowed = any(
        str(p).startswith(str(base))
        for base in ALLOWED_BASE_DIRS
    )
    if not allowed:
        allowed_list = "\n".join(f"  - {d}" for d in ALLOWED_BASE_DIRS)
        return p, (
            f"Akses ditolak: '{p}' berada di luar direktori yang diizinkan.\n"
            f"Direktori yang diizinkan:\n{allowed_list}"
        )

    if must_exist and not p.exists():
        return p, f"File atau folder tidak ditemukan: {p}"

    return p, None


# ── Tool 2: Read File ─────────────────────────────────────────────────────────

def read_file(file_path: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """
    Baca isi file teks (txt, md, csv, json, log, html, yaml, dll).
    File PDF/DOCX tidak bisa dibaca langsung sebagai teks — gunakan extract_cv_from_file untuk itu.

    Args:
        file_path: Path absolut ke file yang akan dibaca.
        encoding: Encoding file (default: utf-8). Gunakan 'latin-1' jika utf-8 gagal.

    Returns:
        Dict berisi konten file sebagai string.
    """
    try:
        p, err = _resolve_and_validate(file_path)
        if err:
            return {"success": False, "error": err}

        if not p.is_file():
            return {"success": False, "error": f"Bukan file: {p}"}

        ext = p.suffix.lower()
        if ext not in READABLE_TEXT_EXTENSIONS:
            return {
                "success": False,
                "error": (
                    f"Ekstensi '{ext}' tidak didukung untuk pembacaan teks langsung. "
                    f"Ekstensi yang didukung: {', '.join(sorted(READABLE_TEXT_EXTENSIONS))}. "
                    f"Untuk CV PDF/DOCX gunakan tool extract_cv_from_file."
                )
            }

        size = p.stat().st_size
        if size > MAX_READ_BYTES:
            return {
                "success": False,
                "error": f"File terlalu besar ({_human_size(size)}). Maksimal {_human_size(MAX_READ_BYTES)}."
            }

        content = p.read_text(encoding=encoding, errors="replace")

        return {
            "success": True,
            "file_path": str(p),
            "filename": p.name,
            "size": _human_size(size),
            "lines": content.count("\n") + 1,
            "content": content,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


# ── Tool 3: Write File ────────────────────────────────────────────────────────

def write_file(file_path: str, content: str, overwrite: bool = False) -> Dict[str, Any]:
    """
    Buat atau timpa sebuah file teks dengan konten yang diberikan.

    Args:
        file_path: Path absolut ke file yang akan dibuat/diperbarui.
                   Harus berada di dalam direktori yang diizinkan.
        content: Konten yang akan ditulis ke file.
        overwrite: Jika True, timpa file yang sudah ada. Default False (aman).

    Returns:
        Dict dengan status keberhasilan dan info file.
    """
    try:
        p, err = _resolve_and_validate(file_path, must_exist=False)
        if err:
            return {"success": False, "error": err}

        if p.exists() and not overwrite:
            return {
                "success": False,
                "error": (
                    f"File sudah ada: {p}. "
                    "Set overwrite=True untuk menimpa file yang sudah ada."
                )
            }

        # Ensure parent directory exists
        p.parent.mkdir(parents=True, exist_ok=True)

        p.write_text(content, encoding="utf-8")

        return {
            "success": True,
            "message": f"File berhasil {'ditimpa' if p.exists() else 'dibuat'}: {p.name}",
            "file_path": str(p),
            "size": _human_size(p.stat().st_size),
        }
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


# ── Tool 4: Delete File ───────────────────────────────────────────────────────

def rename_file(file_path: str, new_name: str) -> Dict[str, Any]:
    """
    Ganti nama sebuah file. File tetap berada di folder yang sama.
    Tidak bisa memindahkan file ke folder berbeda — gunakan untuk rename saja.

    Args:
        file_path: Path absolut ke file yang ingin diganti namanya.
        new_name:  Nama baru file (hanya nama + ekstensi, bukan path penuh).
                   Contoh: 'RafaelRichieCurriculumVitae.pdf'

    Returns:
        Dict dengan status keberhasilan dan path baru.
    """
    try:
        p, err = _resolve_and_validate(file_path)
        if err:
            return {"success": False, "error": err}

        if not p.is_file():
            return {"success": False, "error": f"Bukan file: {p}"}

        # Reject path separators in new_name to prevent directory traversal
        if any(sep in new_name for sep in ("/", "\\", "..")):
            return {"success": False, "error": "new_name harus berupa nama file saja, bukan path. Contoh: 'NamaFile.pdf'"}

        dest = p.parent / new_name
        if dest.exists():
            return {
                "success": False,
                "error": f"File dengan nama '{new_name}' sudah ada di folder yang sama. Hapus dulu atau pilih nama lain."
            }

        # Validate destination is still within allowed dirs
        _, dest_err = _resolve_and_validate(str(dest), must_exist=False)
        if dest_err:
            return {"success": False, "error": dest_err}

        old_name = p.name
        p.rename(dest)

        return {
            "success": True,
            "message": f"File berhasil diganti nama: '{old_name}' → '{new_name}'",
            "old_path": str(p),
            "new_path": str(dest),
            "new_filename": new_name,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


# ── Tool 5: Delete File ───────────────────────────────────────────────────────

def delete_file(file_path: str) -> Dict[str, Any]:
    """
    Hapus sebuah file dari direktori yang diizinkan.
    Tidak bisa menghapus direktori — hanya file individual.

    Args:
        file_path: Path absolut ke file yang akan dihapus.

    Returns:
        Dict dengan status keberhasilan.
    """
    try:
        p, err = _resolve_and_validate(file_path)
        if err:
            return {"success": False, "error": err}

        if not p.is_file():
            return {"success": False, "error": f"Bukan file (atau sudah terhapus): {p}"}

        filename = p.name
        p.unlink()

        return {
            "success": True,
            "message": f"File berhasil dihapus: {filename}",
            "deleted_path": str(p),
        }
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


# ── Tool 6: List Directory ────────────────────────────────────────────────────

def list_dir(directory_path: str) -> Dict[str, Any]:
    """
    List isi sebuah direktori yang diizinkan.
    Mengembalikan daftar file dan folder di dalamnya.

    Args:
        directory_path: Path absolut ke direktori yang akan di-list.

    Returns:
        Dict berisi daftar item (name, type, size, modified).
    """
    try:
        p, err = _resolve_and_validate(directory_path)
        if err:
            return {"success": False, "error": err}

        if not p.is_dir():
            return {"success": False, "error": f"Bukan direktori: {p}"}

        items = []
        for x in p.iterdir():
            is_file = x.is_file()
            items.append({
                "name": x.name,
                "type": "file" if is_file else "directory",
                "size": _human_size(x.stat().st_size) if is_file else None,
                "modified": datetime.fromtimestamp(x.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            })

        return {
            "success": True,
            "directory": str(p),
            "items": items,
            "count": len(items)
        }
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


# ── Tool 7: Search Files ──────────────────────────────────────────────────────

def search_files(directory_path: str, pattern: str = "*", recursive: bool = False) -> Dict[str, Any]:
    """
    Cari file berdasarkan pola nama (glob) di dalam direktori yang diizinkan.

    Args:
        directory_path: Direktori awal pencarian.
        pattern: Pola glob (contoh: '*.pdf', 'CV_*', '*Richie*'). Default: '*'.
        recursive: Jika True, cari hingga ke sub-folder. Default: False.

    Returns:
        Dict berisi daftar path file yang ditemukan.
    """
    try:
        p, err = _resolve_and_validate(directory_path)
        if err:
            return {"success": False, "error": err}

        if not p.is_dir():
            return {"success": False, "error": f"Bukan direktori: {p}"}

        matches = []
        glob_func = p.rglob if recursive else p.glob
        for match in glob_func(pattern):
            if match.is_file():
                # Re-validate each match for safety (especially if recursive)
                _, match_err = _resolve_and_validate(str(match))
                if not match_err:
                    matches.append({
                        "name": match.name,
                        "path": str(match.resolve()),
                        "size": _human_size(match.stat().st_size)
                    })

        return {
            "success": True,
            "directory": str(p),
            "pattern": pattern,
            "recursive": recursive,
            "matches": matches[:100],  # Limit results
            "count": len(matches)
        }
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


# ── Utility ───────────────────────────────────────────────────────────────────

def _human_size(size_bytes: int) -> str:
    """Convert bytes to human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / 1024 ** 2:.1f} MB"
    return f"{size_bytes / 1024 ** 3:.1f} GB"


# ── Tool Definitions (MCP schema) ─────────────────────────────────────────────

FILESYSTEM_TOOLS = [
    {
        "name": "read_file",
        "description": (
            "Baca isi file teks (txt, md, csv, json, log, html, yaml). "
            "TIDAK mendukung PDF/DOCX — gunakan extract_cv_from_file untuk CV. "
            "Gunakan ini untuk membaca log, konfigurasi, atau file teks lainnya."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path absolut ke file yang akan dibaca."
                },
                "encoding": {
                    "type": "string",
                    "description": "Encoding file. Default: utf-8. Gunakan latin-1 jika ada error encoding."
                }
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "write_file",
        "description": (
            "Buat atau perbarui file teks. Digunakan untuk membuat catatan, "
            "menyimpan laporan teks, atau file konfigurasi. "
            "Hanya bisa menulis ke direktori yang diizinkan."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path absolut ke file yang akan dibuat/diperbarui."
                },
                "content": {
                    "type": "string",
                    "description": "Konten yang akan ditulis ke file."
                },
                "overwrite": {
                    "type": "boolean",
                    "description": "Jika true, timpa file yang sudah ada. Default: false."
                }
            },
            "required": ["file_path", "content"]
        }
    },
    {
        "name": "rename_file",
        "description": (
            "Ganti nama file dalam direktori yang diizinkan. "
            "Gunakan ini ketika user ingin rename file CV atau file lainnya. "
            "new_name hanya nama file saja (contoh: 'NamaFile.pdf'), bukan path lengkap."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path absolut ke file yang ingin diganti namanya."
                },
                "new_name": {
                    "type": "string",
                    "description": "Nama baru file saja (bukan path). Contoh: 'RafaelRichieCurriculumVitae.pdf'"
                }
            },
            "required": ["file_path", "new_name"]
        }
    },
    {
        "name": "delete_file",
        "description": (
            "Hapus file dari direktori yang diizinkan. "
            "Hanya bisa menghapus file individual, bukan folder."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path absolut ke file yang akan dihapus."
                }
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "list_dir",
        "description": (
            "List isi sebuah direktori. Gunakan ini untuk melihat file apa saja "
            "yang tersedia di folder uploads, exports, atau documents."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "directory_path": {
                    "type": "string",
                    "description": "Path absolut ke direktori yang ingin dilihat isinya."
                }
            },
            "required": ["directory_path"]
        }
    },
    {
        "name": "search_files",
        "description": (
            "Cari file dengan pola tertentu (glob) di folder yang diizinkan. "
            "Contoh pattern: '*.pdf' untuk semua PDF, 'CV_*' untuk file berawalan CV."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "directory_path": {
                    "type": "string",
                    "description": "Direktori awal pencarian."
                },
                "pattern": {
                    "type": "string",
                    "description": "Pola nama file (glob). Default: '*'"
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Cari ke dalam sub-folder. Default: false."
                }
            },
            "required": ["directory_path"]
        }
    },
]
