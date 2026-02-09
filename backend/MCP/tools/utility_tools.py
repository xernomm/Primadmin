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
    }
]
