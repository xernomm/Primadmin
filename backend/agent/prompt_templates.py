"""
Prompt templates for HR Agent.
Contains system prompt and tool definitions.
"""
from typing import List, Dict
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ============================================================================
# STAGE 1: PROMPT ESCALATION TEMPLATE
# ============================================================================
PROMPT_ESCALATION_TEMPLATE = """Analisis query HR berikut dan ekstrak semua informasi yang dibutuhkan.

## Query User
{user_query}

## Konteks Percakapan
{conversation_context}

## Tools yang Tersedia
{tool_catalog}

## Aturan Ekstraksi

1. **JANGAN minta klarifikasi** — langsung ekstrak dan proses
2. **Ekstrak semua nilai** — nama, gaji, persentase, email, jabatan, dll
3. **Hitung multiplier** — "naik 15%" → salary_multiplier: 1.15 | "kurangi 10%" → 0.90
4. **File attachment** — jika ada path file dilampirkan, isi attachment_file_path
5. **recommended_tools** — sarankan tools dari atas sebanyak-banyaknya yang relevan dengan pertanyaan user.
6. **Waktu/tanggal nyata** — jika query menyebut "hari ini", "sekarang", "bulan ini", "minggu ini", atau konteks waktu apapun, WAJIB sertakan `get_current_time` di `recommended_tools`. JANGAN tebak tanggal.
7. **Data DB nyata** — jika query membutuhkan data yang belum jelas ada atau tidak (misal: file CV, slip gaji, daftar karyawan), sertakan `list_directory` atau `generate_and_execute_sql` di `recommended_tools` agar agent dapat mengkonfirmasi data nyata dari sistem, bukan mengarang.

## Output JSON

```json
{{
  "intent": "Deskripsi singkat apa yang diminta user dan untuk siapa",
  "action_type": "read/write/analyze/export/composite",
  "scope": {{
    "target": "single_employee/multiple_employees/department/company_wide",
    "specific_names": ["nama jika ada"]
  }},
  "entities": {{
    "employee_name": "nama karyawan",
    "salary_multiplier": "misal 1.15 untuk +15%, 0.85 untuk -15%",
    "new_salary": "angka gaji baru jika disebutkan langsung",
    "new_position": "jabatan baru jika ada",
    "new_department": "departemen baru jika ada",
    "new_email": "email baru jika ada",
    "new_phone": "nomor baru jika ada",
    "new_status": "status baru jika ada",
    "new_address": "alamat baru jika ada",
    "new_marital_status": "status pernikahan baru jika ada",
    "export_type": "personal/operational jika minta export",
    "warning_letter_type": "SP1/SP2/SP3 jika terkait SP",
    "leave_type": "annual/sick/emergency jika terkait cuti",
    "date_range": "range waktu jika ada",
    "attachment_file_path": "path absolut file jika ada lampiran",
    "cv_action": "upload/replace jika ada attachment"
  }},
  "temporal_context": {{
    "time_reference": "today/this_week/this_month/none",
    "requires_current_time": false
  }},
  "expected_output": {{
    "format": "table/list/summary/confirmation/export_file",
    "detail_level": "basic/detailed/comprehensive"
  }},
  "data_requirements": {{
    "basic_info": true,
    "salary_info": false,
    "leave_info": false,
    "attendance_info": false,
    "historical_data": false
  }},
  "needs_clarification": false,
  "clarification_question": null,
  "recommended_tools": ["search_employees", "update_employee_by_id"],
  "expanded_query": "Query detail yang menjelaskan: apa, siapa, data apa yang dibutuhkan, dan output format yang diharapkan. PENTING: JANGAN sebutkan nama kolom database spesifik — deskripsikan data yang dibutuhkan dalam bahasa alami (contoh: 'data status kehadiran, info keterlambatan, dan catatan' — BUKAN 'kolom status_kehadiran, keterlambatan, catatan_tambahan'). SQL generator yang akan menentukan kolom yang tepat berdasarkan schema database."
}}
```

Analisis query sekarang:"""

# ============================================================================
# STAGE 2: TOOL PLANNING TEMPLATE
# ============================================================================
TOOL_PLANNING_TEMPLATE = """Buat rencana eksekusi tool untuk request HR berikut.

## Context
Intent: {intent}
Entities: {entities}
Query Detail: {expanded_query}

## Tools
{tool_descriptions}

## Aturan Wajib
1. **Nama → ID**: Jika ada nama karyawan, SELALU mulai dengan `search_employees` untuk dapatkan `emp_id`
2. **emp_id bukan employee_id**: Parameter ID karyawan selalu `emp_id` (integer)
3. **Waktu**: Jika pertanyaan tentang "hari ini/sekarang", panggil `get_current_time` di awal
4. **Verifikasi write**: Setelah update/create, ambil data terbaru untuk konfirmasi
5. **Export**: Untuk request export/download/CSV → `export_employee_personal_data` atau `export_employee_operational_data`
6. **CV read**: Untuk profil/keahlian/pengalaman/sertifikasi → `get_employee_cv` atau `summarize_employee_cv`
7. **CV upload**: Jika ada `attachment_file_path` → `manage_cv_file` lalu `extract_cv_from_file`
8. **CEK vs AKSI**: Jangan kirim email/SP jika user hanya bertanya status
9. **LARANGAN CHAIN analyze→update**: `analyze_employee_cv` dan `summarize_employee_cv` hanya menghasilkan TEKS NARATIF — outputnya TIDAK BOLEH digunakan sebagai `updates` untuk `update_employee_by_id`. Jika user ingin update data CV, field dan nilainya HARUS diambil langsung dari query user (via entities), bukan dari hasil analisis. Jangan buat step `update_employee_by_id` dengan `updates: {{{{step_N.result.anything}}}}` jika step N adalah analyze/summarize.
10. **SQL SCHEMA WAJIB**: Jika plan menggunakan `generate_and_execute_sql`, WAJIB tambahkan step `get_schema_context` SEBELUMNYA dan jadikan sebagai `depends_on`. Argumen `schema_context` di `generate_and_execute_sql` harus diisi dengan `{{{{step_N.result.schema}}}}` dari step `get_schema_context`. Ini memastikan SQL generator mengetahui nama tabel dan kolom yang tepat. Contoh:
    ```
    {{"step": N, "name": "get_schema_context", "args": {{}}, "reason": "ambil schema DB untuk SQL generator", "depends_on": null}}
    {{"step": N+1, "name": "generate_and_execute_sql", "args": {{"natural_query": "...", "schema_context": "{{{{step_N.result.schema}}}}"}}, "depends_on": N}}
    ```
11. **CV FILE WORKFLOW WAJIB**: Untuk operasi yang melibatkan file CV karyawan (`extract_cv_from_file`), WAJIB susun chain berikut:
    ```
    Step A: search_employees → dapat emp_id
    Step B: get_employee_files(emp_id=step_A.result.id) → dapat abs_path file CV
    Step C: extract_cv_from_file(emp_id=step_A.result.id, file_path=step_B.result.files.cv.abs_path) → mengembalikan field 'data'
    Step D: update_employee_by_id(emp_id=step_A.result.id, updates={{step_C.result.data}})
    ```
    JANGAN hardcode path file. JANGAN gunakan list_directory (tool sudah dihapus). SELALU gunakan abs_path dari get_employee_files.
12. **LANGCHAIN COMPATIBILITY**: Selalu gunakan key `name` (untuk nama tool) dan `args` (untuk argument tool). Ini penting agar response mudah dipahami oleh LangChain MCP adapter.
13. **SCOPE TOOLS — LARANGAN KRITIS**: 
    - Plan HANYA boleh menggunakan tools yang ada dalam daftar tool yang tersedia.
    - DILARANG mereferensikan tool yang tidak ada dalam daftar (contoh: search_payroll, get_leaves_history, dll).
    - `completion_checklist` HANYA boleh berisi kondisi yang BISA diverifikasi dari output tools dalam plan ini.
    - DILARANG membuat checklist item yang memerlukan data yang tidak diambil oleh tools manapun dalam plan.

## Format Output JSON (SANGAT KETAT)
Kamu WAJIB mengembalikan JSON murni dengan struktur berikut. Perhatikan bahwa key untuk daftar langkah harus bernama `"plan"` dan isinya berupa **ARRAY of OBJECTS** (BUKAN array of strings).

```json
{{
  "reasoning": "alasan singkat memilih tools ini",
  "plan": [
    {{
      "step": 1,
      "name": "search_employees",
      "args": {{"query": "nama_karyawan"}},
      "reason": "dapatkan emp_id dari nama",
      "depends_on": null
    }},
    {{
      "step": 2,
      "name": "get_employee_files",
      "args": {{"emp_id": "{{{{step_1.result.id}}}}"}},
      "reason": "dapatkan path file CV",
      "depends_on": 1
    }},
    {{
      "step": 3,
      "name": "extract_cv_from_file",
      "args": {{"emp_id": "{{{{step_1.result.id}}}}", "file_path": "{{{{step_2.result.files.cv.abs_path}}}}"}},
      "reason": "ekstrak file cv",
      "depends_on": 2
    }},
    {{
      "step": 4,
      "name": "update_employee_by_id",
      "args": {{"emp_id": "{{{{step_1.result.id}}}}", "updates": "{{{{step_3.result.data}}}}"}},
      "reason": "simpan data hasil ekstrasi ke database karyawan",
      "depends_on": 3
    }}
  ],
  "can_execute": true,
  "completion_checklist": [
    "Kondisi spesifik yang harus terpenuhi agar intent user terjawab"
  ]
}}
```

Buat plan sekarang:"""


# ============================================================================
# STAGE 4: VERIFICATION TEMPLATE
# ============================================================================
VERIFICATION_TEMPLATE = """Kamu adalah Verification Agent. Tugasmu adalah mengecek apakah SEMUA kebutuhan user sudah terpenuhi berdasarkan hasil eksekusi tools.

## Pertanyaan Asli User
{original_query}

## Intent yang Diparsing
{intent}

## Hasil Eksekusi Tools
{tool_results}

## Retry Info
Retry ke: {retry_count} dari maksimal 2

## Instruksi Verifikasi

Lakukan analisis secara utuh terhadap hasil yang didapat dibandingkan dengan pertanyaan asli user:
1. Apakah informasi yang diminta oleh pertanyaan asli user SUDAH didapatkan dari hasil eksekusi tools?
2. Jika ada informasi yang terlewat (missing), apa sebenarnya yang masih di-request namun belum ada hasilnya?
3. Jangan pernah membuat asumsi kondisi baru di luar pertanyaan asli user.

### ⚠️ ATURAN PENTING — JANGAN ABAIKAN:

**A. Percayai \`updated_fields\` sebagai bukti nyata DB:**
- Jika tool update (update_employee_by_id, update_leaves, dll) mengembalikan `"success": true` DAN `"updated_fields": {{...}}`, nilai di `updated_fields` adalah nilai AKTUAL yang tersimpan di database.
- JANGAN hitung ulang atau ragukan nilai tersebut. `updated_fields` adalah sumber kebenaran (source of truth).

**B. Percayai \`success: true\` untuk operasi tulis:**
- Jika sebuah write tool mengembalikan `"success": true`, operasi SUDAH berhasil dieksekusi dan di-commit ke database.

**C. Jangan gagalkan karena data opsional atau field tambahan:**
- Jika SQL query mengembalikan field LEBIH dari yang diminta, itu VALID dan tidak perlu dipermasalahkan.
- Jangan jadikan sebuah proses FAIL untuk hal yang tidak secara eksplisit di-request user.

**D. SCOPE VERIFIKASI — HANYA evaluasi dari hasil tools yang ada saat ini:**
- Jika ada hal yang gagal, instruksikan pendekatan BEDA, BUKAN kembali mengulang tools yang sama jika terbukti hasilnya tidak berhasil atau sudah berhasil tapi datanya kurang.
- Kriteria PASS: Intent asli user terjawab.
- Kriteria FAIL: Intent utama user ada yang tidak terjawab atau write statement mengembalikan success: false.

## Format Output (JSON)
```json
{{
  "all_satisfied": true/false,
  "analysis": "Analisa naratif apakah hasil eksekusi tools sudah benar-benar menjawab intent user. Sebutkan apa yang berhasil didapatkan tanpa menggunakan poin-poin.",
  "missing_info": "Penjelasan konkrit informasi spesifik apa yang belum terjawab (isi dengan null jika all_satisfied: true)",
  "retry_instructions": "Hanya diisi jika all_satisfied: false. Berikan usulan tools alternatif spesifik atau cara BEDA agar kelemahan pada eksekusi sebelumnya dapat diatasi. Jangan sarankan mengulang hal yang sama. (isi dengan null jika all_satisfied: true)"
}}
```

Verifikasi sekarang:"""

# ============================================================================
# STAGE 5: RESPONSE GENERATION TEMPLATE
# ============================================================================
RESPONSE_GENERATION_TEMPLATE = """Buat respons HR yang tepat sasaran berdasarkan hasil tools berikut.

## Pertanyaan User
{original_query}

## Konteks Percakapan
{conversation_context}

## Hasil Tools
{tool_results}

## Aturan
1. **Gunakan HANYA data dari tool results** — jangan mengarang, **TAMPILKAN DATA SELENGKAP-LENGKAPNYA**
2. **Jawab langsung** pertanyaan user, bukan topik lain
3. **Format sesuai konteks**:
   - List karyawan → tabel markdown
   - Update/write → tampilkan data before/after sebagai konfirmasi (✅)
   - Statistik → angka bold
4. **Insight** — tambahkan jika ada pola menarik atau anomali
5. **Rekomendasi aksi** — jika relevan (1-3 item, skip jika hanya query informational)
6. **Bahasa** — Indonesia formal, gunakan emoji secukupnya (✅ ❌ 📊 🎯 ⚠️)

Tulis respons sekarang:"""


# ============================================================================
# MAIN SYSTEM PROMPT (For tool execution stage)
# ============================================================================
SYSTEM_PROMPT = """Kamu adalah HR Agent, asisten AI yang membantu tim HR dalam mengelola data karyawan dan operasional HR.

## Kemampuan Kamu:

1. **Manajemen Karyawan**
   - Mencari dan menampilkan data karyawan
   - Membuat, update, dan hapus data karyawan
   - Filter berdasarkan posisi, status, gaji
   
2. **Absensi & Kehadiran**
   - Cek kehadiran karyawan hari ini
   - Lihat siapa yang telat, remote, atau onsite
   - Update data absensi
   
3. **Cuti Karyawan**
   - Lihat sisa cuti per karyawan
   - Update data cuti
   
4. **SQL Generator**
   - Untuk query kompleks yang tidak bisa dijawab tools lain
   - Mendukung SELECT, INSERT, UPDATE, DELETE

## Panduan Respons:

1. **Bahasa**: Gunakan Bahasa Indonesia yang profesional dan sopan
2. **Context Awareness**: 
   - Selalu cek waktu (`get_current_time`) jika pertanyaan berkaitan dengan "hari ini", "sekarang", atau "besok".
3. **Format**: Gunakan format yang mudah dibaca (bullet points, tabel markdown)
4. **Privacy**: Jangan expose data sensitif tanpa diminta

## Strategi Penggunaan Tools (Chain-of-Thought):

Untuk permintaan yang kompleks, JANGAN RAGU menggunakan beberapa tools secara berurutan:
1. **Analisis Masalah**: Pahami apa yang diminta.
2. **Kumpulkan Konteks**: Cek waktu jika relevan.
3. **Cek Data**: Ambil data dari database.
4. **Sintesis**: Gabungkan semua informasi untuk menjawab.
5. **Eksekusi**: Jika perlu update/create, lakukan di langkah terakhir.

**Bedakan Read vs Write Tools**:
- Untuk pertanyaan "Cek status", "Lihat data", "Siapa saja": Gunakan Read Tools (get_*, search_*, sql SELECT).
- HANYA gunakan Write Tools (send_*, update_*, sql UPDATE) jika user secara eksplisit meminta perubahan atau pengiriman.

**Contoh**: "Siapa yang telat hari ini?" -> `get_current_time` -> `get_today_late_employees` -> Jawab.


## Tools yang Tersedia:

Kamu memiliki akses ke berbagai tools untuk membantu pekerjaan. Gunakan tools yang sesuai untuk menjawab pertanyaan user.

## Format Response:

- Berikan jawaban yang ringkas dan informatif
- Gunakan formatting markdown jika membantu (bold, list, tabel)
- Sertakan data yang relevan dari hasil query
- Jika ada tindakan yang dilakukan, jelaskan hasilnya

Mulai membantu user sekarang!
"""

# ============================================================================
# TOOL DEFINITIONS
# ============================================================================
def get_tool_definitions() -> List[Dict]:
    """Get all tool definitions for the agent."""
    try:
        from MCP.tools import (
            EMPLOYEE_TOOLS,
            ATTENDANCE_TOOLS,
            LEAVE_TOOLS,
            SQL_TOOLS,
            UTILITY_TOOLS,
            EMAIL_TOOLS,
            ANALYSIS_TOOLS,
            EXPORT_TOOLS,
            PAYROLL_TOOLS,
            CV_TOOLS,
            FILESYSTEM_TOOLS
        )
    except ImportError:
        # Fallback for different import paths
        from MCP.tools.employee_tools import EMPLOYEE_TOOLS
        from MCP.tools.attendance_tools import ATTENDANCE_TOOLS
        from MCP.tools.leave_tools import LEAVE_TOOLS
        from MCP.tools.sql_generator import SQL_TOOLS
        from MCP.tools.utility_tools import UTILITY_TOOLS
        from MCP.tools.email_tools import EMAIL_TOOLS
        from MCP.tools.analysis_tools import ANALYSIS_TOOLS
        from MCP.tools.export_tools import EXPORT_TOOLS
        from MCP.tools.payroll_tools import PAYROLL_TOOLS
        from MCP.tools.cv_tools import CV_TOOLS
        from MCP.tools.filesystem_tools import FILESYSTEM_TOOLS
    
    all_tools = []
    all_tools.extend(EMPLOYEE_TOOLS)
    all_tools.extend(ATTENDANCE_TOOLS)
    all_tools.extend(LEAVE_TOOLS)
    all_tools.extend(SQL_TOOLS)
    all_tools.extend(UTILITY_TOOLS)
    all_tools.extend(EMAIL_TOOLS)
    all_tools.extend(ANALYSIS_TOOLS)
    all_tools.extend(EXPORT_TOOLS)
    all_tools.extend(PAYROLL_TOOLS)
    all_tools.extend(CV_TOOLS)
    all_tools.extend(FILESYSTEM_TOOLS)
    
    # Format for Ollama
    formatted_tools = []
    for tool in all_tools:
        formatted_tools.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"]
            }
        })
    
    return formatted_tools


def get_tool_descriptions() -> str:
    """Get tool descriptions as text for prompt injection."""
    tools = get_tool_definitions()
    
    lines = ["## Available Tools:\n"]
    for tool in tools:
        func = tool["function"]
        lines.append(f"### {func['name']}")
        lines.append(f"{func['description']}\n")
        
        if func.get("parameters", {}).get("properties"):
            lines.append("Parameters:")
            for param_name, param_info in func["parameters"]["properties"].items():
                required = param_name in func["parameters"].get("required", [])
                req_str = " (required)" if required else " (optional)"
                lines.append(f"  - {param_name}{req_str}: {param_info.get('description', '')}")
            lines.append("")
    
    return "\n".join(lines)


def get_tool_summary(tool_hints: list = None) -> str:
    """
    Get tool descriptions for Stage 2 planning.
    
    If tool_hints is provided (list of tool names recommended by Stage 1),
    those tools get FULL schema+description. All other tools get name-only.
    If tool_hints is None/empty, all tools get full descriptions (legacy behavior).
    """
    tools = get_tool_definitions()
    
    if not tool_hints:
        # Legacy: show full schema for all tools
        lines = ["### Tool Schema Reference\n"]
        lines.append("**PENTING:** Gunakan nama parameter PERSIS seperti yang tertera di bawah!\n")
        
        for tool in tools:
            func = tool["function"]
            params = func.get("parameters", {}).get("properties", {})
            required = func.get("parameters", {}).get("required", [])
            
            param_parts = []
            for param_name, param_info in params.items():
                param_type = param_info.get("type", "any")
                is_required = param_name in required
                if is_required:
                    param_parts.append(f"{param_name}: {param_type}")
                else:
                    param_parts.append(f"{param_name}?: {param_type}")
            
            signature = ", ".join(param_parts) if param_parts else ""
            lines.append(f"**{func['name']}**({signature})")
            lines.append(f"  └─ {func['description'][:350]}")
            lines.append("")
        
        return "\n".join(lines)
    
    # Smart mode: full schema for hint tools, name-only for the rest
    hint_set = set(tool_hints)
    
    lines = ["### Tool Schema Reference\n"]
    lines.append("**PENTING:** Gunakan nama parameter PERSIS seperti yang tertera di bawah!\n")
    lines.append(f"**Stage 1 merekomendasikan tools berikut sebagai PRIORITAS UTAMA:** {', '.join(tool_hints)}\n")
    
    # --- Section 1: FULL schema for hinted tools ---
    lines.append("#### Tools Prioritas (full schema):")
    for tool in tools:
        func = tool["function"]
        if func["name"] not in hint_set:
            continue
        
        params = func.get("parameters", {}).get("properties", {})
        required = func.get("parameters", {}).get("required", [])
        
        param_parts = []
        for param_name, param_info in params.items():
            param_type = param_info.get("type", "any")
            is_required = param_name in required
            if is_required:
                param_parts.append(f"{param_name}: {param_type}")
            else:
                param_parts.append(f"{param_name}?: {param_type}")
        
        signature = ", ".join(param_parts) if param_parts else ""
        lines.append(f"**{func['name']}**({signature})")
        lines.append(f"  └─ {func['description'][:350]}")
        # Inline warning for analysis-only tools
        if func['name'] in ('analyze_employee_cv', 'summarize_employee_cv'):
            lines.append("  ⚠️ PERINGATAN: Tool ini hanya menghasilkan TEKS ANALISIS, bukan data terstruktur. JANGAN gunakan outputnya sebagai `updates` di update_employee_by_id.")
        lines.append("")
    
    # --- Section 2: Name-only for non-hinted tools ---
    non_hinted = [t for t in tools if t["function"]["name"] not in hint_set]
    if non_hinted:
        lines.append("#### Tools Tambahan (tersedia jika diperlukan, tanpa full schema):")
        for tool in non_hinted:
            func = tool["function"]
            lines.append(f"- **{func['name']}**: {func['description'][:100]}")
        lines.append("")
    
    return "\n".join(lines)


def get_compact_tool_catalog() -> str:
    """
    Returns a compact tool catalog for Stage 1 (escalation prompt).
    Each tool is shown as one line: name → short description.
    No parameter details — Stage 1 only needs to know WHAT each tool does
    so it can recommend the right tools for Stage 2.
    Also prints the catalog to terminal for debugging.
    """
    tools = get_tool_definitions()
    lines = []
    for tool in tools:
        func = tool["function"]
        name = func["name"]
        desc = func["description"][:120].rstrip()
        if len(func["description"]) > 120:
            desc += "..."
        lines.append(f"- `{name}`: {desc}")

    catalog = "\n".join(lines)

    # Print to terminal for visibility
    print("\n" + "=" * 60)
    print(f"[TOOL CATALOG] {len(tools)} tools tersedia untuk Stage 1:")
    print("=" * 60)
    for tool in tools:
        func = tool["function"]
        print(f"  {func['name']}: {func['description'][:80].rstrip()}")
    print("=" * 60 + "\n")

    return catalog

