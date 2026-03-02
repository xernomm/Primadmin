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

import ollama

load_dotenv()

ORACLE_USER = os.getenv("ORACLE_USER")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD")
ORACLE_HOST = os.getenv("ORACLE_HOST")
ORACLE_PORT = os.getenv("ORACLE_PORT")
ORACLE_SERVICE = os.getenv("ORACLE_SERVICE_NAME")

dsn = cx_Oracle.makedsn(ORACLE_HOST, ORACLE_PORT, service_name=ORACLE_SERVICE)
db_url = f"oracle+cx_oracle://{ORACLE_USER}:{ORACLE_PASSWORD}@{dsn}"
engine = create_engine(db_url)

# SQL generation model (qwen2.5-coder for better SQL understanding)
SQL_MODEL = "qwen2.5-coder:latest"

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
    
    # Check if query references any valid table
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
            
    if not table_found:
        return False, f"Query does not reference any known tables. Allowed: {', '.join(valid_tables[:3])}..."
    
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
10. **USE ONLY EXISTING TABLES**: Only reference tables shown in the schema above. Do NOT invent or hallucinate table names like 'warning_letters', 'leave_requests', etc.

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

Request: "Kurangi gaji Rafael Richie 15%"
Response: UPDATE employees SET basic_salary = basic_salary * 0.85 WHERE UPPER(name) LIKE '%RAFAEL RICHIE%'

Now generate the SQL query for the user's request. Return ONLY the SQL query:"""


def generate_sql_with_llm(natural_query: str, model: str = None, schema_context: str = None) -> Dict[str, Any]:
    """
    Generate SQL query using LLM with full Oracle schema context.
    
    Args:
        natural_query: Natural language query
        model: LLM model to use (default: qwen2.5-coder:latest)
        schema_context: Optional pre-fetched schema string. If None, fetches internally.
        
    Returns:
        Dict with generated SQL and metadata
    """
    if model is None:
        model = SQL_MODEL
    
    # Use provided schema or fetch from DB
    if not schema_context:
        schema_context = get_oracle_schema_context()
    
    # Build prompt
    prompt = SQL_GENERATION_PROMPT.format(
        schema=schema_context,
        natural_query=natural_query
    )
    
    try:
        # Call LLM
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={
                "temperature": 0.1,  # Low temperature for deterministic SQL
                "top_p": 0.9,
                "num_predict": 500
            }
        )
        
        content = response.get("message", {}).get("content", "")
        
        # Clean up the response
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


def generate_and_execute_sql(
    natural_query: str,
    execute: bool = True,
    limit: int = 100,
    schema_context: str = None
) -> Dict[str, Any]:
    """
    Convert natural language to SQL using LLM and optionally execute.
    
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

    # Generate SQL using LLM
    generation_result = generate_sql_with_llm_with_schema(natural_query, schema_context)
    
    if not generation_result.get("success"):
        return generation_result
    
    generated_sql = generation_result["generated_sql"]
    
    # Prepare result
    result = {
        "natural_query": natural_query,
        "generated_sql": generated_sql,
        "model": generation_result.get("model")
    }
    
    # Execute if requested
    if execute:
        execution_result = execute_safe_sql(generated_sql, limit)
        result.update(execution_result)
    else:
        result["executed"] = False
        result["message"] = "SQL generated but not executed. Set execute=True to run."
    
    return result


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
