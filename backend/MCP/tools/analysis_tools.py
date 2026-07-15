"""
Analysis tools for HR Agent.
Provides RAG-based analysis for attendance and leave policies.
Integrates policy documents with actual data for comprehensive analysis.
"""
import os
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import cx_Oracle
from dotenv import load_dotenv
from agent.gemini_client import gemini_generate

# Import RAG retriever
from rag.retriever import get_rag_context, search_documents

load_dotenv()

ORACLE_USER = os.getenv("ORACLE_USER")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD")
ORACLE_HOST = os.getenv("ORACLE_HOST")
ORACLE_PORT = os.getenv("ORACLE_PORT")
ORACLE_SERVICE = os.getenv("ORACLE_SERVICE_NAME")

dsn = cx_Oracle.makedsn(ORACLE_HOST, ORACLE_PORT, service_name=ORACLE_SERVICE)

# LLM Model for analysis
ANALYSIS_MODEL = os.getenv("ANALYSIS_MODEL", "gemini-2.5-flash")


def _get_connection():
    """Get Oracle database connection."""
    return cx_Oracle.connect(user=ORACLE_USER, password=ORACLE_PASSWORD, dsn=dsn)


def analyze_attendance_with_policy(
    query: str,
    emp_id: int = None,
    period: str = "monthly"
) -> Dict[str, Any]:
    """
    Analisa data absensi/kehadiran berdasarkan kebijakan perusahaan.
    
    Tool ini menggabungkan:
    1. Query data absensi dari database
    2. Retrieve kebijakan perusahaan dari dokumen RAG
    3. Membandingkan data dengan kebijakan
    4. Memberikan analisis dan rekomendasi
    
    Args:
        query: Pertanyaan atau topik analisis (misal: "keterlambatan bulan ini")
        emp_id: ID karyawan spesifik (opsional, None = semua karyawan)
        period: Periode analisis: "daily", "weekly", "monthly", "yearly"
        
    Returns:
        Dict with analysis results including policy context and recommendations
    """
    try:
        conn = _get_connection()
        cur = conn.cursor()
        
        # Step 1: Determine date range based on period
        today = datetime.now()
        if period == "daily":
            start_date = today.replace(hour=0, minute=0, second=0)
            end_date = today
        elif period == "weekly":
            start_date = today - timedelta(days=7)
            end_date = today
        elif period == "monthly":
            start_date = today.replace(day=1)
            end_date = today
        elif period == "yearly":
            start_date = today.replace(month=1, day=1)
            end_date = today
        else:
            start_date = today - timedelta(days=30)
            end_date = today
        
        # Step 2: Fetch attendance data
        if emp_id:
            # Single employee analysis
            cur.execute("""
                SELECT e.name, e.department, e.sp_level,
                       COUNT(a.id) as total_attendance,
                       SUM(CASE WHEN a.status = 'late' THEN 1 ELSE 0 END) as late_count,
                       SUM(CASE WHEN a.status = 'on-time' THEN 1 ELSE 0 END) as ontime_count,
                       SUM(CASE WHEN a.status = 'absent' THEN 1 ELSE 0 END) as absent_count,
                       SUM(CASE WHEN a.work_location = 'Remote' THEN 1 ELSE 0 END) as remote_count
                FROM employees e
                LEFT JOIN attendance a ON e.id = a.employee_id 
                    AND a.attendance_date BETWEEN :start_date AND :end_date
                WHERE e.id = :emp_id
                GROUP BY e.name, e.department, e.sp_level
            """, {
                "emp_id": emp_id,
                "start_date": start_date,
                "end_date": end_date
            })
            data = cur.fetchone()
            
            if not data:
                cur.close()
                conn.close()
                return {"success": False, "error": f"Karyawan dengan ID {emp_id} tidak ditemukan."}
            
            attendance_data = {
                "type": "individual",
                "employee_name": data[0],
                "department": data[1],
                "sp_level": data[2] or 0,
                "total_attendance": data[3] or 0,
                "late_count": data[4] or 0,
                "ontime_count": data[5] or 0,
                "absent_count": data[6] or 0,
                "remote_count": data[7] or 0
            }
        else:
            # Company-wide analysis
            cur.execute("""
                SELECT 
                    COUNT(DISTINCT e.id) as total_employees,
                    COUNT(a.id) as total_attendance_records,
                    SUM(CASE WHEN a.status = 'late' THEN 1 ELSE 0 END) as total_late,
                    SUM(CASE WHEN a.status = 'on-time' THEN 1 ELSE 0 END) as total_ontime,
                    SUM(CASE WHEN a.status = 'absent' THEN 1 ELSE 0 END) as total_absent,
                    SUM(CASE WHEN a.work_location = 'Remote' THEN 1 ELSE 0 END) as total_remote
                FROM employees e
                LEFT JOIN attendance a ON e.id = a.employee_id
                    AND a.attendance_date BETWEEN :start_date AND :end_date
                WHERE e.status = 'active'
            """, {"start_date": start_date, "end_date": end_date})
            data = cur.fetchone()
            
            # Get top late employees
            cur.execute("""
                SELECT e.name, e.department, COUNT(*) as late_count, e.sp_level
                FROM employees e
                JOIN attendance a ON e.id = a.employee_id
                WHERE a.status = 'late' 
                    AND a.attendance_date BETWEEN :start_date AND :end_date
                GROUP BY e.name, e.department, e.sp_level
                ORDER BY late_count DESC
                FETCH FIRST 5 ROWS ONLY
            """, {"start_date": start_date, "end_date": end_date})
            top_late = [{"name": r[0], "department": r[1], "late_count": r[2], "sp_level": r[3]} 
                        for r in cur.fetchall()]
            
            attendance_data = {
                "type": "company",
                "total_employees": data[0] or 0,
                "total_attendance_records": data[1] or 0,
                "total_late": data[2] or 0,
                "total_ontime": data[3] or 0,
                "total_absent": data[4] or 0,
                "total_remote": data[5] or 0,
                "top_late_employees": top_late
            }
        
        cur.close()
        conn.close()
        
        # Step 3: Get relevant policy context via RAG
        rag_query = f"absensi kehadiran terlambat {query}"
        policy_context = get_rag_context(rag_query)
        
        # Step 4: Use LLM to analyze data against policy
        analysis_prompt = f"""Analisa data absensi berikut berdasarkan kebijakan perusahaan:

## Data Absensi (Periode: {period})
{attendance_data}

## Kebijakan Perusahaan yang Relevan
{policy_context if policy_context else "Tidak ada dokumen kebijakan yang ditemukan."}

## Pertanyaan/Topik Analisis
{query}

## Instruksi
1. Bandingkan data absensi dengan kebijakan perusahaan
2. Identifikasi pelanggaran atau anomali
3. Berikan statistik ringkas
4. Berikan rekomendasi tindakan berdasarkan kebijakan SP:
   - SP1 untuk pelanggaran ringan/pertama
   - SP2 untuk pelanggaran berulang
   - SP3 sebagai peringatan terakhir sebelum PHK

Format output sebagai JSON:
{{
  "summary": "ringkasan singkat temuan",
  "statistics": {{}},
  "policy_violations": [],
  "recommendations": [],
  "risk_level": "low/medium/high"
}}"""

        # Call LLM for analysis
        analysis_text = gemini_generate(
            model=ANALYSIS_MODEL,
            prompt=analysis_prompt,
            temperature=0.3,
            response_mime_type="application/json"
        )
        
        # Try to parse JSON from response
        import json
        import re
        
        # Find JSON in response
        json_match = re.search(r'\{[\s\S]*\}', analysis_text)
        if json_match:
            try:
                analysis_result = json.loads(json_match.group())
            except json.JSONDecodeError:
                analysis_result = {"summary": analysis_text, "parse_error": True}
        else:
            analysis_result = {"summary": analysis_text, "parse_error": True}
        
        return {
            "success": True,
            "analysis": analysis_result,
            "raw_data": attendance_data,
            "period": period,
            "date_range": {
                "start": start_date.strftime("%Y-%m-%d"),
                "end": end_date.strftime("%Y-%m-%d")
            },
            "policy_context_found": bool(policy_context),
            "query": query
        }
        
    except Exception as e:
        return {"success": False, "error": str(e), "trace": traceback.format_exc()}


# Tool definitions for agent
ANALYSIS_TOOLS = [
    {
        "name": "analyze_attendance_with_policy",
        "description": "Analisa absensi/kehadiran karyawan berdasarkan KEBIJAKAN PERUSAHAAN. Tool ini menggunakan RAG untuk mengambil dokumen kebijakan dan membandingkan dengan data aktual. Gunakan untuk: analisa keterlambatan, evaluasi WFH, rekomendasi SP, pelanggaran kebijakan.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Topik atau pertanyaan analisis. Contoh: 'keterlambatan bulan ini', 'evaluasi WFH', 'siapa yang perlu SP'"
                },
                "emp_id": {
                    "type": "integer",
                    "description": "Database ID karyawan untuk analisis individual. Kosongkan untuk analisis seluruh perusahaan.",
                    "default": None
                },
                "period": {
                    "type": "string",
                    "enum": ["daily", "weekly", "monthly", "yearly"],
                    "description": "Periode analisis data (default: monthly)",
                    "default": "monthly"
                }
            },
            "required": ["query"]
        }
    }
]
