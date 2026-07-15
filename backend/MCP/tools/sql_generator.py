"""
SQL generator tool for HR Agent.
Converts natural language to SQL using LLM with full Oracle schema awareness.
Supports full CRUD operations (SELECT, INSERT, UPDATE, DELETE).
"""
import os
import re
import json
import traceback
from typing import Dict, Any, Tuple
import cx_Oracle
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from agent.gemini_client import gemini_chat

load_dotenv()

ORACLE_USER = os.getenv("ORACLE_USER")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD")
ORACLE_HOST = os.getenv("ORACLE_HOST")
ORACLE_PORT = os.getenv("ORACLE_PORT")
ORACLE_SERVICE = os.getenv("ORACLE_SERVICE_NAME")

dsn = cx_Oracle.makedsn(ORACLE_HOST, ORACLE_PORT, service_name=ORACLE_SERVICE)
db_url = f"oracle+cx_oracle://{ORACLE_USER}:{ORACLE_PASSWORD}@{dsn}"
engine = create_engine(db_url)

# SQL generation model
SQL_MODEL = "gemini-2.5-flash"

# Allowed tables for queries
ALLOWED_TABLES = [
    'employees',
    'hr_users',
    'attendance',
    'warnings',
    'conversations',
    'messages',
    'documents'
]

# Dangerous patterns that should be blocked
DANGEROUS_PATTERNS = [
    r'\bDROP\s+TABLE\b',
    r'\bDROP\s+DATABASE\b',
    r'\bTRUNCATE\b',
    r'\bALTER\s+TABLE\b',
    r'\bCREATE\s+TABLE\b',
    r'\bGRANT\b',
    r'\bREVOKE\b',
    r'--',  # SQL comment (could hide malicious code)
    r';.*;',  # Multiple statements
]


def get_allowed_tables() -> list[str]:
    """Get list of allowed tables dynamically from schema discovery."""
    try:
        try:
            from database.schema_discovery import get_schema_discovery
        except ImportError:
            from backend.database.schema_discovery import get_schema_discovery
        
        tables = get_schema_discovery().get_table_names()
        return tables if tables else ALLOWED_TABLES
    except Exception:
        return ALLOWED_TABLES


def is_safe_query(sql: str) -> Tuple[bool, str]:
    """
    Check if a SQL query is safe to execute.
    Allows SELECT, INSERT, UPDATE, DELETE but blocks dangerous operations.
    Must reference at least one valid table.
    
    Args:
        sql: SQL query string
        
    Returns:
        Tuple of (is_safe, reason)
    """
    sql_upper = sql.upper().strip()
    
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, sql_upper, re.IGNORECASE):
            return False, f"Query contains forbidden pattern: {pattern}"
    
    allowed_starts = ['SELECT', 'INSERT', 'UPDATE', 'DELETE']
    if not any(sql_upper.startswith(op) for op in allowed_starts):
        return False, "Query must start with SELECT, INSERT, UPDATE, or DELETE"
    
    valid_tables = get_allowed_tables()
    table_found = False
    
    # Simple heuristic: check if table name appears in query
    # Note: This is not a perfect parser but catches hallucinated table names effectively
    # when coupled with limited context provided to LLM.
    for table in valid_tables:
        # Check for table name with word boundaries or as part of schema.table
        # e.g. " EMPLOYEES ", " SMARTBOT.EMPLOYEES ", ",EMPLOYEES,"
        if table.upper() in sql_upper:
            table_found = True
            break
        
    valid_tables_upper = [t.upper() for t in valid_tables]
    tables_in_query = set()
    
    # Extract table names following FROM and JOIN clauses
    matches = re.findall(r'\b(?:FROM|INTO|UPDATE|JOIN)\s+([A-Z0-9_]+)\b', sql_upper)
    for m in matches:
        if m not in ('SELECT', 'DUAL'):
            tables_in_query.add(m)
            
    if not tables_in_query:
        # Fallback to simple heuristic if regex misses
        table_found = any(table.upper() in sql_upper for table in valid_tables)
        if not table_found:
            return False, f"Query does not reference any known tables. Allowed: {', '.join(valid_tables[:3])}..."
    else:
        # Check if every extracted table is in the valid tables list
        for t in tables_in_query:
            if t not in valid_tables_upper:
                return False, f"Query references UNKNOWN table: '{t}'. You MUST ONLY use the allowed tables: {', '.join(valid_tables)}. DO NOT hallucinate tables!"
                
    return True, "Query is safe"


def execute_safe_sql(sql: str, limit: int = 100) -> Dict[str, Any]:
    """
    Execute a safe SQL query and return results.
    
    Args:
        sql: SQL query to execute
        limit: Maximum number of rows to return (for SELECT)
        
    Returns:
        Dict with results or error
    """
    # Safety check
    is_safe, reason = is_safe_query(sql)
    if not is_safe:
        return {
            "success": False,
            "error": reason,
            "query": sql,
            "executed": False
        }
    
    # Oracle doesn't like semicolons in dynamic SQL - strip them
    sql = sql.strip().rstrip(';').strip()
    sql_upper = sql.upper()
    
    # Detect unresolved bind parameters (LLM sometimes generates :param_name)
    bind_params = re.findall(r':([a-zA-Z_]\w*)', sql)
    # Filter out Oracle keywords that use colon syntax (e.g., timestamps)
    real_bind_params = [p for p in bind_params if p.upper() not in ('TIMESTAMP', 'DATE', 'NUMBER', 'VARCHAR2', 'CLOB')]
    if real_bind_params:
        return {
            "success": False,
            "error": f"Query contains unresolved bind parameters: {real_bind_params}. Rewrite using actual literal values instead of :param placeholders.",
            "query": sql,
            "executed": False
        }

    # Detect unresolved {{step_...}} placeholders
    if "{{" in sql and "}}" in sql:
        placeholders = re.findall(r'{{.*?}}', sql)
        if placeholders:
            return {
                "success": False,
                "error": f"Query contains unresolved placeholders: {placeholders}. You must resolve them to actual values before executing.",
                "query": sql,
                "executed": False
            }
    
    try:
        with engine.begin() as conn:
            if sql_upper.startswith('SELECT'):
                # Add FETCH FIRST for Oracle if not present
                if 'FETCH FIRST' not in sql_upper and 'ROWNUM' not in sql_upper:
                    sql = f"{sql.rstrip(';')} FETCH FIRST {limit} ROWS ONLY"
                
                # Strip semicolon for Oracle execution
                sql = sql.strip().rstrip(';')

                result = conn.execute(text(sql))
                columns = list(result.keys())
                rows = result.fetchall()
                data = [dict(zip(columns, row)) for row in rows]
                
                return {
                    "success": True,
                    "operation": "SELECT",
                    "query": sql,
                    "columns": columns,
                    "row_count": len(data),
                    "data": data
                }
            else:
                # INSERT, UPDATE, DELETE
                result = conn.execute(text(sql))
                affected = result.rowcount
                operation = sql_upper.split()[0]
                
                return {
                    "success": True,
                    "operation": operation,
                    "query": sql,
                    "rows_affected": affected,
                    "message": f"{operation} berhasil. {affected} baris terpengaruh."
                }
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "query": sql,
            "executed": False,
            "trace": traceback.format_exc()
        }


def get_oracle_schema_context() -> str:
    """
    Get Oracle database schema for LLM context.
    Reads actual schema from new relational tables using schema_discovery.
    
    Returns:
        Formatted schema string for LLM
    """
    try:
        # Try importing from local path first (if running from backend root)
        try:
            from database.schema_discovery import get_schema_context
        except ImportError:
            # Try importing with backend prefix (if running from project root)
            from backend.database.schema_discovery import get_schema_context
            
        return get_schema_context(format_type='sql')
    except Exception as e:
        # Fallback to hardcoded schema if discovery fails
        print(f"[SCHEMA DISCOVERY ERROR] Could not load dynamic schema: {e}")
        return """# DATABASE SCHEMA (Oracle)
[FALLBACK SCHEMA - DYNAMIC DISCOVERY FAILED]
Please refer to the fallback schema definition in schema_discovery.py or check database connection.
"""


def get_schema_context() -> dict:
    """
    Expose database schema as an MCP tool result.
    Returns the full Oracle schema (tables + columns + descriptions) as a string.
    ALWAYS call this tool BEFORE generate_and_execute_sql when planning SQL queries.
    """
    schema = get_oracle_schema_context()
    return {
        "success": True,
        "schema": schema,
        "usage": "Pass the 'schema' value to generate_and_execute_sql as the schema_context parameter."
    }


SQL_GENERATION_PROMPT = """You are an expert Oracle SQL query generator for an HR management system.

Your task: Generate a SAFE, EFFICIENT Oracle SQL query based on the user's request.
ALLOWED OPERATIONS: SELECT, INSERT, UPDATE, DELETE

{schema}

## VALID TABLES (ONLY use these — any other table name will be REJECTED)
{valid_tables}

## USER REQUEST
{natural_query}

## ORACLE SQL RULES (CRITICAL)
1. **NO LIMIT CLAUSE**: Use `FETCH FIRST n ROWS ONLY` instead of `LIMIT n`.
2. **Current Date/Time**: Use `SYSDATE` or `CURRENT_TIMESTAMP`. Do NOT use `NOW()`.
3. **String Concatenation**: Use `||` operator (e.g., `first_name || ' ' || last_name`).
4. **Date Comparison**: Use `TRUNC(date_column) = TRUNC(SYSDATE)` for today.
   - For string to date: `TO_DATE('2024-01-01', 'YYYY-MM-DD')`.
5. **Case Insensitivity**: Use `UPPER(col) LIKE '%VALUE%'` for text search.
6. **No Boolean Type**: Oracle SQL does not support `TRUE`/`FALSE`. Use `1`/`0` or `'Y'`/ `'N'` if applicable, but check schema constraints.
7. **Quotes**: Use single quotes `'` for string literals. Double quotes `"` are for identifiers only.
8. **NO SEMICOLONS**: Do NOT include semicolons at the end of queries. Oracle dynamic SQL rejects them.
9. **NO BIND PARAMETERS**: Do NOT use `:param_name` syntax (e.g., `:emp_id`, `:name`). Always use actual literal values directly in the query.
10. **TABLE NAMES — ZERO TOLERANCE**: You may ONLY use the tables listed in VALID TABLES above. Tables like 'leaves', 'leave_requests', 'warning_letters', 'cuti' DO NOT EXIST. If you use any table not in the valid list, the query WILL BE REJECTED.
11. **CUTI / LEAVE DATA**:
    - Data cuti (sisa saldo): kolom `REMAINING_LEAVE` di tabel `EMPLOYEES`.
    - Riwayat cuti (kapan/tanggal cuti): tabel `ATTENDANCE` dengan filter `STATUS = 'leave'`.
    - TABEL 'leaves' ATAU 'cuti' TIDAK ADA. JANGAN PERNAH MENGGUNAKANNYA.

## GENERAL RULES
1. Use proper JOINs (LEFT/INNER) with aliases (e.g., `e` for employees).
2. For INSERT: Specify columns explicitly.
3. For UPDATE/DELETE: **ALWAYS** include a WHERE clause.
4. Return **ONLY** the raw SQL query, no markdown formatting or explanations.

## EXAMPLES

Request: "Tampilkan semua karyawan aktif"
Response: SELECT id, name, position, status, email FROM employees WHERE status = 'active' FETCH FIRST 100 ROWS ONLY

Request: "Update gaji karyawan ID 5 menjadi 15 juta"
Response: UPDATE employees SET basic_salary = 15000000 WHERE id = 5

Request: "Hapus data absensi karyawan ID 10 tanggal kemarin"
Response: DELETE FROM attendance WHERE employee_id = 10 AND TRUNC(attendance_date) = TRUNC(SYSDATE - 1)

Request: "Berapa rata-rata gaji per status kepegawaian?"
Response: SELECT status, AVG(basic_salary) as avg_salary, COUNT(*) as count FROM employees GROUP BY status ORDER BY avg_salary DESC

Request: "Tampilkan sisa cuti karyawan departemen IT"
Response: SELECT id, name, department, remaining_leave FROM employees WHERE UPPER(department) LIKE '%IT%' FETCH FIRST 100 ROWS ONLY

Request: "Karyawan mana yang sudah izin/sakit bulan ini?"
Response: SELECT e.name, a.attendance_date, a.status, a.notes FROM employees e JOIN attendance a ON e.id = a.employee_id WHERE a.status IN ('sick', 'permit') AND TRUNC(a.attendance_date, 'MM') = TRUNC(SYSDATE, 'MM') FETCH FIRST 100 ROWS ONLY

{correction_context}
Now generate the SQL query for the user's request. Return ONLY the SQL query:"""

SQL_CORRECTION_PROMPT = """## ⚠️ PREVIOUS ATTEMPT FAILED
Your previous SQL query was REJECTED with this error:
```
{error}
```
Previous (invalid) SQL:
```sql
{previous_sql}
```
You MUST fix this error. Do NOT repeat the same mistake. Generate a CORRECTED query using ONLY the valid tables listed above."""


def _clean_sql_response(content: str) -> str:
    """Extract and clean SQL from LLM response text."""
    sql = content.strip()
    # Remove markdown code blocks if present
    sql = re.sub(r'^```sql\s*\n?', '', sql, flags=re.IGNORECASE)
    sql = re.sub(r'^```\s*\n?', '', sql)
    sql = re.sub(r'\n?```$', '', sql)
    sql = sql.strip()
    
    # Extract just the SQL statement
    lines = sql.split('\n')
    sql_lines = []
    in_query = False
    
    for line in lines:
        line_stripped = line.strip().upper()
        if any(line_stripped.startswith(op) for op in ['SELECT', 'INSERT', 'UPDATE', 'DELETE']):
            in_query = True
        if in_query:
            sql_lines.append(line)
            if line.strip().endswith(';'):
                break
    
    sql = '\n'.join(sql_lines).strip()
    
    # Ensure query ends with semicolon
    if sql and not sql.endswith(';'):
        sql += ';'
    
    return sql


def generate_sql_with_llm(natural_query: str, model: str = None, schema_context: str = None, correction_context: str = "") -> Dict[str, Any]:
    """
    Generate SQL query using LLM with full Oracle schema context.
    
    Args:
        natural_query: Natural language query
        model: LLM model to use (default: qwen2.5-coder:latest)
        schema_context: Optional pre-fetched schema string. If None, fetches internally.
        correction_context: Optional error feedback from a previous failed attempt.
        
    Returns:
        Dict with generated SQL and metadata
    """
    if model is None:
        model = SQL_MODEL
    
    # Use provided schema or fetch from DB
    if not schema_context:
        schema_context = get_oracle_schema_context()
    
    # Build valid tables list for explicit injection into prompt
    valid_tables = get_allowed_tables()
    valid_tables_str = ", ".join(valid_tables) if valid_tables else "(could not load tables)"
    
    # Build prompt
    prompt = SQL_GENERATION_PROMPT.format(
        schema=schema_context,
        natural_query=natural_query,
        valid_tables=valid_tables_str,
        correction_context=correction_context
    )
    
    try:
        # Call LLM using Gemini
        content = gemini_chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        sql = _clean_sql_response(content)
        
        return {
            "success": True,
            "natural_query": natural_query,
            "generated_sql": sql,
            "model": model
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to generate SQL: {str(e)}",
            "natural_query": natural_query,
            "trace": traceback.format_exc()
        }


# Alias: generate SQL with pre-fetched schema (no internal DB call needed)
def generate_sql_with_llm_with_schema(natural_query: str, schema_context: str) -> Dict[str, Any]:
    """Generate SQL using pre-provided schema string (skip internal schema discovery)."""
    return generate_sql_with_llm(natural_query, schema_context=schema_context)


MAX_SQL_RETRIES = 3


def generate_and_execute_sql(
    natural_query: str,
    execute: bool = True,
    limit: int = 100,
    schema_context: str = None
) -> Dict[str, Any]:
    """
    Convert natural language to SQL using LLM and optionally execute.
    Includes auto-retry: if the generated SQL is rejected (bad table, syntax error),
    the error is fed back to the LLM for self-correction (up to 3 attempts).
    
    Args:
        natural_query: Natural language query (e.g., "Tampilkan semua karyawan IT")
        execute: Whether to execute the generated SQL (default: True)
        limit: Maximum number of rows to return for SELECT (default: 100)
        schema_context: Optional pre-fetched schema string from get_schema_context tool.
                        If provided, skips internal schema discovery (faster + fresher).
        
    Returns:
        Dict with generated SQL and execution results
    """
    # Use provided schema_context if available, else fetch internally
    if not schema_context:
        schema_context = get_oracle_schema_context()

    correction_context = ""
    last_error = None
    last_sql = None

    for attempt in range(1, MAX_SQL_RETRIES + 1):
        print(f"[SQL_GENERATOR] Attempt {attempt}/{MAX_SQL_RETRIES} for: {natural_query[:80]}")

        # Generate SQL using LLM (with optional correction feedback)
        generation_result = generate_sql_with_llm(
            natural_query,
            schema_context=schema_context,
            correction_context=correction_context
        )

        if not generation_result.get("success"):
            return generation_result

        generated_sql = generation_result["generated_sql"]
        last_sql = generated_sql

        # --- Safety check BEFORE execution ---
        is_safe, safety_reason = is_safe_query(generated_sql)
        if not is_safe:
            last_error = safety_reason
            print(f"[SQL_GENERATOR] Safety check FAILED (attempt {attempt}): {safety_reason}")
            # Build correction context for next attempt
            correction_context = SQL_CORRECTION_PROMPT.format(
                error=safety_reason,
                previous_sql=generated_sql
            )
            continue  # retry with feedback

        # --- Execute if requested ---
        result = {
            "natural_query": natural_query,
            "generated_sql": generated_sql,
            "model": generation_result.get("model"),
            "attempt": attempt
        }

        if execute:
            execution_result = execute_safe_sql(generated_sql, limit)
            result.update(execution_result)

            # If execution failed (e.g. ORA-00942), retry with error feedback
            if not execution_result.get("success"):
                last_error = execution_result.get("error", "Unknown execution error")
                print(f"[SQL_GENERATOR] Execution FAILED (attempt {attempt}): {last_error}")
                correction_context = SQL_CORRECTION_PROMPT.format(
                    error=last_error,
                    previous_sql=generated_sql
                )
                continue  # retry with feedback

            # Success!
            print(f"[SQL_GENERATOR] SUCCESS on attempt {attempt}")
            return result
        else:
            result["executed"] = False
            result["message"] = "SQL generated but not executed. Set execute=True to run."
            return result

    # All retries exhausted
    print(f"[SQL_GENERATOR] All {MAX_SQL_RETRIES} attempts FAILED")
    return {
        "natural_query": natural_query,
        "generated_sql": last_sql,
        "success": False,
        "error": f"SQL generation failed after {MAX_SQL_RETRIES} attempts. Last error: {last_error}",
        "executed": False,
        "attempts": MAX_SQL_RETRIES
    }


# Tool definitions for agent
SQL_TOOLS = [
    {
        "name": "get_schema_context",
        "description": """Mengambil skema database Oracle (tabel + kolom + deskripsi) sebagai konteks untuk SQL generator.

⚠️ WAJIB dipanggil SEBELUM generate_and_execute_sql sebagai depends_on.
Output: field 'schema' berisi schema string yang harus dioper ke generate_and_execute_sql sebagai parameter schema_context.""",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "generate_and_execute_sql",
        "description": """[ADVANCED] Generator & Eksekutor SQL Oracle Otomatis.
Gunakan tool ini sebagai "Senjata Pamungkas" jika tool spesifik lain tidak tersedia. 
Sangat ampuh untuk:
1. Query Agregasi: Count, Sum, Avg (e.g., "Total gaji per departemen", "Rata-rata cuti").
2. Cross-Table Joins: Menghubungkan karyawan dengan absensi, cuti, atau peringatan.
3. Filter Kompleks: Kondisi WHERE yang rumit (e.g., "Karyawan tetap yang join > 2 tahun lalu").
4. Bulk Updates/Deletes: "Ubah status semua karyawan magang menjadi kontrak".

⚠️ WAJIB: Selalu tambahkan step get_schema_context sebelum tool ini dan gunakan hasilnya sebagai schema_context.
Jangan gunakan untuk query simpel yang sudah ada tool-nya (seperti search employee by name).
CATATAN PENTING: Jika user meminta data yang tidak ada detailnya (contoh: detail tabel cuti/leaves), GAGALKAN atau sesuaikan query dengan data yang ADA SAJA (misal hanya sisa cuti di tabel employees). Jangan berhalusinasi tabel.
""",
        "parameters": {
            "type": "object",
            "properties": {
                "natural_query": {
                    "type": "string",
                    "description": "Natural language description of what data you want to retrieve or modify. Be specific about tables, filters, columns, sorting, or grouping needed."
                },
                "execute": {
                    "type": "boolean",
                    "description": "Whether to execute the generated SQL. ALWAYS set to true if the user wants to see data/results. Set to false ONLY if the user explicitly asks to just 'generate SQL' without running it.",
                    "default": True
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of rows to return for SELECT queries (default: 100)",
                    "default": 100
                },
                "schema_context": {
                    "type": "string",
                    "description": "Schema string dari hasil get_schema_context (field 'schema'). Wajib diisi jika ada step get_schema_context sebelumnya."
                }
            },
            "required": ["natural_query"]
        }
    }
]
