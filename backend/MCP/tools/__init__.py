"""
Tools module for HR Agent.
Exports all tool functions and definitions for MCP server and agent.
"""
from .employee_tools import (
    search_employees,
    get_employee_by_id,
    get_all_employees,
    create_employee,
    update_employee_by_id,
    delete_employee_by_id,
    get_employee_files,
    EMPLOYEE_TOOLS
)
from .attendance_tools import (
    get_attendance,
    update_absensi,
    ATTENDANCE_TOOLS
)
from .sql_generator import (
    generate_and_execute_sql,
    generate_sql_with_llm,
    execute_safe_sql,
    SQL_TOOLS
)
from .utility_tools import (
    get_current_time,
    extract_data_from_file,
    UTILITY_TOOLS
)
from .email_tools import (
    send_warning_letter,
    send_broadcast_email,
    reset_sp_level,
    generate_email_content,
    EMAIL_TOOLS
)
from .analysis_tools import (
    analyze_attendance_with_policy,
    ANALYSIS_TOOLS
)
from .export_tools import (
    export_employee_personal_data,
    export_employee_operational_data,
    EXPORT_TOOLS
)
from .payroll_tools import (
    get_payroll_detail,
    get_payroll_info,
    analyze_payroll_anomaly,
    export_payroll_csv,
    get_payroll_file,
    create_payroll_report_pdf,
    send_payroll_email,
    PAYROLL_TOOLS
)
from .cv_tools import (
    get_employee_cv,
    analyze_employee_cv,
    summarize_employee_cv,
    manage_cv_file,
    CV_TOOLS
)
from .filesystem_tools import (
    read_file,
    write_file,
    rename_file,
    delete_file,
    FILESYSTEM_TOOLS
)

# Collect all tool definitions
ALL_TOOLS = []
ALL_TOOLS.extend(EMPLOYEE_TOOLS)
ALL_TOOLS.extend(ATTENDANCE_TOOLS)
ALL_TOOLS.extend(SQL_TOOLS)
ALL_TOOLS.extend(UTILITY_TOOLS)
ALL_TOOLS.extend(EMAIL_TOOLS)
ALL_TOOLS.extend(ANALYSIS_TOOLS)
ALL_TOOLS.extend(EXPORT_TOOLS)
ALL_TOOLS.extend(PAYROLL_TOOLS)
ALL_TOOLS.extend(CV_TOOLS)
ALL_TOOLS.extend(FILESYSTEM_TOOLS)

__all__ = [
    # Employee tools
    'search_employees',
    'get_employee_by_id',
    'get_all_employees',
    'create_employee',
    'update_employee_by_id',
    'delete_employee_by_id',
    'get_employee_files',
    'EMPLOYEE_TOOLS',
    
    # Attendance tools
    'get_attendance',
    'update_absensi',
    'ATTENDANCE_TOOLS',
    
    # SQL tools
    'generate_and_execute_sql',
    'generate_sql_with_llm',
    'execute_safe_sql',
    'SQL_TOOLS',
    
    # Utility tools
    'get_current_time',
    'extract_data_from_file',
    'UTILITY_TOOLS',
    
    # Email tools
    'send_warning_letter',
    'send_broadcast_email',
    'reset_sp_level',
    'generate_email_content',
    'EMAIL_TOOLS',
    
    # Analysis tools
    'analyze_attendance_with_policy',
    'ANALYSIS_TOOLS',
    
    # Export tools
    'export_employee_personal_data',
    'export_employee_operational_data',
    'EXPORT_TOOLS',
    
    # Payroll tools
    'get_payroll_detail',
    'get_payroll_info',
    'analyze_payroll_anomaly',
    'export_payroll_csv',
    'get_payroll_file',
    'create_payroll_report_pdf',
    'send_payroll_email',
    'PAYROLL_TOOLS',
    
    # CV tools
    'get_employee_cv',
    'analyze_employee_cv',
    'summarize_employee_cv',
    'manage_cv_file',
    'CV_TOOLS',
    
    # Filesystem tools
    'read_file',
    'write_file',
    'rename_file',
    'delete_file',
    'FILESYSTEM_TOOLS',
    
    # Combined
    'ALL_TOOLS'
]

