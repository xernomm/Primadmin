"""
Utility tools for HR Agent.
Provides helper functions like time, date, and general utilities.
"""
from datetime import datetime
from typing import Dict, Any


def get_current_time() -> Dict[str, Any]:
    """
    Get current date and time.
    Useful for context when answering questions about "hari ini", "sekarang", etc.
    
    Returns:
        Dict with current datetime information
    """
    now = datetime.now()
    return {
        "success": True,
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "day_name": now.strftime("%A"),
        "day_name_id": ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"][now.weekday()],
        "is_weekend": now.weekday() >= 5
    }


def extract_data_from_file(file_path: str, instruction: str) -> Dict[str, Any]:
    """
    Ekstrak data secara fleksibel dan universal dari dokumen (PDF, DOCX, TXT)
    menggunakan AI berdasarkan instruksi/kebutuhan spesifik yang diberikan.
    
    Args:
        file_path: Path absolut file dokumen atau URL server
        instruction: Petunjuk/kriteria data apa saja yang ingin diekstrak
        
    Returns:
        Dict hasil ekstraksi data dalam format JSON
    """
    import os
    import json
    import re
    from pathlib import Path
    from agent.gemini_client import gemini_generate
    from .cv_tools import _read_file_content
    
    # Clean up path
    file_path = str(file_path).strip('\'"')
    
    # Resolve server URL if needed
    if file_path.startswith("http://") or file_path.startswith("https://"):
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
            from config import url_to_abs_path
            resolved = url_to_abs_path(file_path)
            if resolved:
                file_path = str(resolved)
            else:
                return {"success": False, "error": f"Tidak bisa resolve server URL ke path: {file_path}"}
        except Exception as e:
            return {"success": False, "error": f"Error resolving URL: {str(e)}"}
            
    # Verify file exists
    file_path_obj = Path(file_path).resolve()
    if not file_path_obj.exists() or not file_path_obj.is_file():
        return {"success": False, "error": f"File tidak ditemukan atau path adalah direktori: {file_path}"}
        
    file_path = str(file_path_obj)
    
    try:
        # Read content
        content = _read_file_content(file_path)
        if not content or content.startswith("[Error"):
            return {"success": False, "error": f"Gagal membaca isi file: {content}"}
            
        # Truncate to avoid context window overhead if extremely large
        if len(content) > 20000:
            content = content[:20000] + "\n... [dipotong karena terlalu panjang]"
            
        # Call Gemini
        ANALYSIS_MODEL = os.getenv("ANALYSIS_MODEL", "gemini-2.5-flash")
        
        prompt = f"""Kamu adalah AI asisten HR yang sangat teliti dan profesional.
Tugas kamu adalah mengekstrak data dari isi dokumen di bawah ini sesuai dengan instruksi yang diberikan.

ISI DOKUMEN:
\"\"\"
{content}
\"\"\"

INSTRUKSI EKSTRAKSI:
{instruction}

## KETENTUAN EKSTRAKSI:
1. Ekstrak HANYA informasi yang benar-benar ada/ditemukan di isi dokumen di atas.
2. Jangan pernah mengarang, mengasumsikan, atau menambahkan data yang tidak tertera di dokumen.
3. Strukturkan hasil ekstraksi ke dalam JSON key-value yang logis, bersih, dan sesuai dengan instruksi di atas.
4. Jika suatu data tidak ditemukan di dokumen, jangan masukkan key tersebut ke dalam JSON.

## FORMAT OUTPUT:
Keluarkan HANYA JSON object. Jangan sertakan penjelasan atau markdown formatting selain JSON mentah.
Contoh format output:
{{"nama": "Rafael", "email": "rafael@example.com"}}

PENTING: Output HANYA berupa JSON valid, tanpa teks penjelasan tambahan."""

        llm_output = gemini_generate(
            model=ANALYSIS_MODEL,
            prompt=prompt,
            temperature=0.1,
            response_mime_type="application/json"
        )
        
        # Parse JSON
        json_match = re.search(r'\{[\s\S]*\}', llm_output)
        if not json_match:
            return {"success": False, "error": "AI tidak menghasilkan JSON yang valid.", "raw_output": llm_output}
            
        extracted_data = json.loads(json_match.group())
        return {
            "success": True,
            "data": extracted_data,
            "file_path": file_path
        }
    except Exception as e:
        import traceback
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


# Tool definitions for agent
UTILITY_TOOLS = [
    {
        "name": "get_current_time",
        "description": "Mengambil waktu dan tanggal saat ini. Gunakan ketika pertanyaan berkaitan dengan 'hari ini', 'sekarang', 'besok', atau konteks waktu lainnya.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "extract_data_from_file",
        "description": "Ekstrak data secara fleksibel dan universal dari dokumen (PDF, DOCX, TXT) menggunakan AI berdasarkan instruksi/kebutuhan spesifik yang diberikan. Sangat berguna untuk membaca data pribadi karyawan, data absensi, data CV, atau berkas tertulis lainnya dan mengubahnya menjadi format data terstruktur JSON.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path absolut file dokumen di server atau URL server (misal: 'C:/uploads/cv.pdf')"
                },
                "instruction": {
                    "type": "string",
                    "description": "Instruksi data apa saja yang ingin diekstrak (misal: 'Ekstrak nama, email, no_hp, pendidikan terakhir')"
                }
            },
            "required": ["file_path", "instruction"]
        }
    }
]

