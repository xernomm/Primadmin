// TypeScript interfaces for HR Agent Frontend

// User types
export interface User {
    id: number;
    username: string;
    email: string;
    full_name: string;
    role: 'hr_staff' | 'hr_manager' | 'admin';
    is_active: boolean;
    last_login: string | null;
}

export interface LoginRequest {
    username: string;
    password: string;
}

export interface RegisterRequest {
    username: string;
    email: string;
    password: string;
    full_name: string;
}

export interface AuthResponse {
    message: string;
    user: User;
    access_token: string;
    refresh_token: string;
}

export interface RefreshResponse {
    access_token: string;
}

// Chat types
export interface Message {
    id?: number;
    conversation_id?: number;
    role: 'user' | 'assistant';
    content: string;
    token_count?: number;
    tool_calls?: ToolCall[];
    thinking?: string;
    metadata?: MessageMetadata;
    file_attachment?: FileAttachment;
    created_at?: string;
}

export interface FileAttachment {
    filename: string;
    size: number;
    type: string;  // file extension or MIME
}

export interface ToolCall {
    tool: string;
    arguments: Record<string, unknown>;
    result: unknown;
}

// Stage data for processing block
export interface StageLog {
    stage: number;
    name: string;
    content: string;
    status: 'processing' | 'complete' | 'error';
}

// Widget data for download buttons, etc.
export interface WidgetData {
    type: 'download';
    filename: string;
    size: string;
    icon?: 'csv' | 'excel' | 'pdf' | 'file';
    download_url: string;
}

export interface MessageMetadata {
    rag_used?: boolean;
    model?: string;
    error?: boolean;
    thinking?: string;
    stage_logs?: StageLog[];
    total_tool_calls?: number;
    widget?: WidgetData;
}

export interface Conversation {
    id: number;
    user_id: number;
    title: string;
    is_active: boolean;
    created_at: string;
    updated_at: string;
}

export interface ChatRequest {
    message: string;
    conversation_id?: number;
}

export interface ChatResponse {
    response: string;
    conversation_id: number;
    tool_calls?: ToolCall[];
    thinking?: string;
    error?: boolean;
    metadata?: {
        rag_used: boolean;
        rag_chunks: number;
        history_count: number;
        total_tokens: number;
        model: string;
    };
}

// Employee types
export interface Employee {
    id: number;
    employee_code: string;
    name: string;
    email: string;
    phone: string | null;
    department: string;
    position: string;
    status: 'active' | 'resigned' | 'suspended' | 'terminated';
    joined_at: string;
    created_at: string;
}

// Attendance types
export interface Attendance {
    id: number;
    employee_id: number;
    employee_name: string;
    date: string;
    check_in: string | null;
    check_out: string | null;
    work_location: 'WFO' | 'WFH' | 'field';
    status: 'present' | 'absent' | 'sick' | 'leave' | 'half_day';
    notes: string | null;
}

// Warning types
export interface Warning {
    id: number;
    employee_id: number;
    employee_name: string;
    warning_type: 'SP1' | 'SP2' | 'SP3';
    reason: string;
    issued_date: string;
    issued_by: string;
    email_sent: boolean;
    email_sent_at: string | null;
}

// API Error
export interface ApiError {
    error: string;
    message?: string;
}
