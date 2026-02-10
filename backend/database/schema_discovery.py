"""
Schema discovery module for Oracle Database.
Auto-reads database schema to generate context for LLM prompts.
"""
import os
from typing import Dict, List, Any
import cx_Oracle
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

load_dotenv()

ORACLE_USER = os.getenv("ORACLE_USER")
ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD")
ORACLE_HOST = os.getenv("ORACLE_HOST")
ORACLE_PORT = os.getenv("ORACLE_PORT")
ORACLE_SERVICE = os.getenv("ORACLE_SERVICE_NAME")
ORACLE_SCHEMA = os.getenv("ORACLE_SCHEMA", "SMARTBOT")

dsn = cx_Oracle.makedsn(ORACLE_HOST, ORACLE_PORT, service_name=ORACLE_SERVICE)
db_url = f"oracle+cx_oracle://{ORACLE_USER}:{ORACLE_PASSWORD}@{dsn}"
engine = create_engine(db_url)

# ============================================================================
# SEMANTIC DESCRIPTIONS for tables and columns
# These are injected into schema context to help LLM understand table purposes
# ============================================================================

TABLE_DESCRIPTIONS = {
    "EMPLOYEES": "Data master karyawan. Menyimpan info personal, jabatan, gaji, status SP (surat peringatan), dan sisa cuti.",
    "WARNINGS": "Riwayat surat peringatan (SP1/SP2/SP3) yang diberikan ke karyawan. Terhubung ke employees via employee_id. Gunakan tabel ini untuk cek berapa kali karyawan mendapat SP.",
    "ATTENDANCE": "Data absensi/kehadiran harian karyawan. Satu record per karyawan per hari.",
    "HR_USERS": "User akun HR yang login ke sistem (bukan karyawan). Menyimpan kredensial login.",
    "CONVERSATIONS": "Riwayat percakapan chat antara HR user dan assistant.",
    "MESSAGES": "Pesan individual dalam sebuah conversation.",
    "DOCUMENTS": "Dokumen yang di-upload untuk RAG system.",
    "PROCESSING_STAGES": "Internal: tahapan proses agent. JANGAN query tabel ini.",
}

COLUMN_DESCRIPTIONS = {
    "EMPLOYEES": {
        "SP_LEVEL": "Level Surat Peringatan saat ini (0=bersih, 1=SP1, 2=SP2, 3=SP3). SP3 = sebelum PHK/pemecatan.",
        "REMAINING_LEAVE": "Sisa jatah cuti tahunan (default 12 hari per tahun).",
        "EMPLOYMENT_STATUS": "Status kepegawaian: 'tetap', 'kontrak', 'magang'.",
        "STATUS": "Status aktif karyawan: 'active', 'inactive', 'terminated'.",
        "BASIC_SALARY": "Gaji pokok bulanan dalam Rupiah (IDR).",
        "EMPLOYEE_CODE": "Kode unik karyawan (e.g. EMP001).",
        "BPJS_NUMBER": "Nomor BPJS Kesehatan/Ketenagakerjaan.",
        "MARITAL_STATUS": "Status pernikahan: 'single', 'married', 'divorced'.",
    },
    "WARNINGS": {
        "WARNING_TYPE": "Tipe surat peringatan: 'SP1', 'SP2', atau 'SP3'.",
        "REASON": "Alasan pemberian surat peringatan.",
        "ISSUED_DATE": "Tanggal surat peringatan diterbitkan.",
        "ISSUED_BY": "ID HR user yang menerbitkan SP (FK ke hr_users.id).",
        "EMAIL_SENT": "Apakah email SP sudah terkirim (1=sudah, 0=belum).",
        "EMAIL_SENT_AT": "Timestamp kapan email terkirim.",
    },
    "ATTENDANCE": {
        "WORK_LOCATION": "Lokasi kerja: 'WFO' (Work From Office) atau 'WFH' (Work From Home).",
        "STATUS": "Status kehadiran: 'present', 'late', 'sick', 'absent', 'permit'.",
        "CHECK_IN": "Waktu jam masuk kerja.",
        "CHECK_OUT": "Waktu jam pulang kerja.",
        "ATTENDANCE_DATE": "Tanggal kehadiran (satu record per hari per karyawan).",
    },
}


class SchemaDiscovery:
    """
    Discovers and formats Oracle database schema for LLM context.
    Generates human-readable schema descriptions optimized for AI comprehension.
    """
    
    def __init__(self, db_engine: Engine = None, schema: str = None):
        self.engine = db_engine or engine
        self.schema = schema or ORACLE_SCHEMA
        self.inspector = inspect(self.engine)
    
    def get_table_names(self) -> List[str]:
        """Get all table names in the schema."""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT table_name FROM all_tables 
                    WHERE owner = :schema
                    ORDER BY table_name
                """), {"schema": self.schema})
                return [row[0] for row in result]
        except Exception:
            return []
    
    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """
        Get detailed schema for a specific table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Dict with columns, constraints, and relationships
        """
        try:
            with self.engine.connect() as conn:
                # Get columns
                columns = []
                col_result = conn.execute(text("""
                    SELECT column_name, data_type, data_length, nullable, data_default
                    FROM all_tab_columns
                    WHERE owner = :schema AND table_name = :table
                    ORDER BY column_id
                """), {"schema": self.schema, "table": table_name.upper()})
                
                for row in col_result:
                    col_info = {
                        'name': row[0],
                        'type': row[1],
                        'length': row[2],
                        'nullable': row[3] == 'Y',
                        'default': str(row[4]) if row[4] else None
                    }
                    columns.append(col_info)
                
                # Get primary key
                pk_result = conn.execute(text("""
                    SELECT cols.column_name
                    FROM all_constraints cons
                    JOIN all_cons_columns cols ON cons.constraint_name = cols.constraint_name
                    WHERE cons.owner = :schema 
                    AND cons.table_name = :table
                    AND cons.constraint_type = 'P'
                """), {"schema": self.schema, "table": table_name.upper()})
                pk_columns = [row[0] for row in pk_result]
                
                # Mark primary key columns
                for col in columns:
                    if col['name'] in pk_columns:
                        col['primary_key'] = True
                
                # Get foreign keys
                foreign_keys = []
                fk_result = conn.execute(text("""
                    SELECT a.column_name, c_pk.table_name as ref_table, b.column_name as ref_column
                    FROM all_cons_columns a
                    JOIN all_constraints c ON a.constraint_name = c.constraint_name
                    JOIN all_constraints c_pk ON c.r_constraint_name = c_pk.constraint_name
                    JOIN all_cons_columns b ON c_pk.constraint_name = b.constraint_name
                    WHERE c.constraint_type = 'R'
                    AND a.owner = :schema
                    AND a.table_name = :table
                """), {"schema": self.schema, "table": table_name.upper()})
                
                for row in fk_result:
                    foreign_keys.append({
                        'column': row[0],
                        'referred_table': row[1],
                        'referred_column': row[2]
                    })
                
                return {
                    'table_name': table_name,
                    'columns': columns,
                    'primary_keys': pk_columns,
                    'foreign_keys': foreign_keys
                }
        except Exception as e:
            return {'table_name': table_name, 'error': str(e)}
    
    def get_full_schema(self) -> Dict[str, Dict]:
        """Get schema for all tables in the schema."""
        schema = {}
        for table_name in self.get_table_names():
            schema[table_name] = self.get_table_schema(table_name)
        return schema
    
    def generate_schema_context(self, format_type: str = 'standard') -> str:
        """
        Generate human-readable schema description for LLM context.
        
        Args:
            format_type: 'standard' for general use, 'sql' for SQL generation
            
        Returns:
            Formatted schema string
        """
        schema = self.get_full_schema()
        
        if not schema:
            return self._generate_fallback_schema()
        
        if format_type == 'sql':
            return self._format_for_sql_generation(schema)
        else:
            return self._format_standard(schema)
    
    def _format_standard(self, schema: Dict[str, Dict]) -> str:
        """Standard formatting for general LLM context."""
        lines = [f"# Database Schema ({self.schema})\\n"]
        lines.append("Berikut adalah tabel-tabel yang tersedia di database HR:\\n")
        
        for table_name, table_info in schema.items():
            lines.append(f"\\n## Table: `{self.schema}.{table_name}`")
            
            # Add table description if available
            table_desc = TABLE_DESCRIPTIONS.get(table_name.upper(), "")
            if table_desc:
                lines.append(f"*{table_desc}*")
            
            if 'error' in table_info:
                lines.append(f"Error: {table_info['error']}")
                continue
            
            # Columns
            lines.append("\\n**Columns:**")
            col_descs = COLUMN_DESCRIPTIONS.get(table_name.upper(), {})
            for col in table_info.get('columns', []):
                nullable = "nullable" if col.get('nullable') else "NOT NULL"
                pk = " [PRIMARY KEY]" if col.get('primary_key') else ""
                default = f" (default: {col['default']})" if col.get('default') else ""
                col_desc = col_descs.get(col['name'], "")
                desc_str = f" -- {col_desc}" if col_desc else ""
                lines.append(f"- `{col['name']}`: {col['type']} - {nullable}{pk}{default}{desc_str}")
            
            # Foreign keys
            if table_info.get('foreign_keys'):
                lines.append("\\n**Relationships:**")
                for fk in table_info['foreign_keys']:
                    lines.append(f"- `{fk['column']}` → `{fk['referred_table']}.{fk['referred_column']}`")
        
        return "\\n".join(lines)
    
    def _format_for_sql_generation(self, schema: Dict[str, Dict]) -> str:
        """SQL-optimized formatting for SQL query generation with semantic descriptions."""
        lines = [f"# DATABASE SCHEMA ({self.schema}) - Oracle SQL"]
        lines.append("IMPORTANT: Only use tables listed below. Do NOT invent table names.\\n")
        
        for table_name, table_info in schema.items():
            # Add table description
            table_desc = TABLE_DESCRIPTIONS.get(table_name.upper(), "")
            if table_desc:
                lines.append(f"\\n## {self.schema}.{table_name} -- {table_desc}")
            else:
                lines.append(f"\\n## {self.schema}.{table_name}")
            
            if 'error' in table_info:
                lines.append(f"Error: {table_info['error']}")
                continue
            
            lines.append("```sql")
            col_lines = []
            col_descs = COLUMN_DESCRIPTIONS.get(table_name.upper(), {})
            for col in table_info.get('columns', []):
                parts = [f"  {col['name']} {col['type']}"]
                if col.get('primary_key'):
                    parts.append("PRIMARY KEY")
                if not col.get('nullable'):
                    parts.append("NOT NULL")
                # Add column description as SQL comment
                col_desc = col_descs.get(col['name'], "")
                if col_desc:
                    parts.append(f"/* {col_desc} */")
                col_lines.append(" ".join(parts))
            
            lines.append(",\\n".join(col_lines))
            lines.append("```")
            
            if table_info.get('foreign_keys'):
                lines.append("\\nForeign Keys:")
                for fk in table_info['foreign_keys']:
                    lines.append(f"- {fk['column']} → {fk['referred_table']}({fk['referred_column']})")
        
        return "\\n".join(lines)
    
    def _generate_fallback_schema(self) -> str:
        """Generate fallback schema if DB schema discovery fails."""
        return f"""# Database Schema ({self.schema})

## Table: {self.schema}.employees
- id: NUMBER PRIMARY KEY
- name: VARCHAR2(100) NOT NULL
- employee_code: VARCHAR2(50) UNIQUE
- email: VARCHAR2(100) UNIQUE
- phone: VARCHAR2(20)
- department: VARCHAR2(50)
- position: VARCHAR2(50)
- status: VARCHAR2(20) -- active, inactive
- marital_status: VARCHAR2(20) -- single, married, divorced
- basic_salary: NUMBER
- bpjs_number: VARCHAR2(50)
- remaining_leave: NUMBER
- employment_status: VARCHAR2(20) -- permanent, contract
- joined_at: DATE

## Table: {self.schema}.attendance
- id: NUMBER PRIMARY KEY
- employee_id: NUMBER REFERENCES employees(id)
- attendance_date: DATE
- check_in: TIMESTAMP
- check_out: TIMESTAMP
- work_location: VARCHAR2(20) -- WFO, WFH
- status: VARCHAR2(20) -- present, late, sick, absent
- notes: CLOB

## Table: {self.schema}.leaves
- id: NUMBER PRIMARY KEY
- employee_id: NUMBER REFERENCES employees(id)
- leave_type: VARCHAR2(50)
- start_date: DATE
- end_date: DATE
- reason: CLOB
- status: VARCHAR2(20) -- pending, approved, rejected

"""


# Singleton instance
_schema_discovery = None


def get_schema_discovery() -> SchemaDiscovery:
    """Get or create SchemaDiscovery singleton."""
    global _schema_discovery
    if _schema_discovery is None:
        _schema_discovery = SchemaDiscovery()
    return _schema_discovery


def get_schema_context(format_type: str = 'standard') -> str:
    """
    Convenience function to get schema context string.
    
    Args:
        format_type: 'standard' for general use, 'sql' for SQL generation
        
    Returns:
        Formatted schema string
    """
    return get_schema_discovery().generate_schema_context(format_type)
