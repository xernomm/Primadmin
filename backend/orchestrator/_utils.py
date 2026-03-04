"""
Shared utilities for all orchestrator modules.
Extracted from HRAgent._parse_json_response and HRAgent._log.
"""
import json
import re
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime, date
from dataclasses import dataclass, field


# ══════════════════════════════════════════════════════════════════════════════
# MODULE CONTEXT — shared dependencies passed to every stage module
# ══════════════════════════════════════════════════════════════════════════════

class ModuleContext:
    """Shared context for all orchestrator modules."""

    def __init__(
        self,
        prompt_builder,
        conversation_id=None,
        status_callback=None,
        stage_callback=None,
        sub_status_callback=None,
        session_id=None,
    ):
        self.prompt_builder = prompt_builder
        self.conversation_id = conversation_id
        self.status_callback = status_callback
        self.stage_callback = stage_callback
        self.sub_status_callback = sub_status_callback
        self.session_id = session_id
        self._stage_logs: list = []

    def update_status(self, message: str):
        """Send status update to frontend if callback registered."""
        if self.status_callback:
            self.status_callback(message)
        print(f"[AGENT STATUS] {message}")

    def emit_stage(self, stage_num: int, stage_name: str, content: str, status: str = "complete"):
        """Emit stage completion data for frontend processing block."""
        stage_data = {
            "stage": stage_num,
            "name": stage_name,
            "content": content,
            "status": status,
        }
        # Upsert: replace if same stage number exists
        existing_idx = next(
            (i for i, s in enumerate(self._stage_logs) if s["stage"] == stage_num), None
        )
        if existing_idx is not None:
            self._stage_logs[existing_idx] = stage_data
        else:
            self._stage_logs.append(stage_data)

        if self.stage_callback:
            self.stage_callback(stage_data)
        print(f"[STAGE {stage_num}] {stage_name}: {status}")

    def emit_stage_reset(self, retry_attempt: int):
        """Emit reset signal — verification failed, agent retrying."""
        reset_data = {
            "type": "reset",
            "retry_attempt": retry_attempt,
            "message": f"Verifikasi gagal, mencoba ulang (percobaan {retry_attempt})...",
        }
        self._stage_logs = []
        if self.stage_callback:
            self.stage_callback(reset_data)
        print(f"[STAGE RESET] Retry attempt {retry_attempt} — clearing stages")

    def emit_sub_status(self, data: dict):
        """Emit sub-step status (tool start/done, plan validation, etc.) to frontend."""
        if self.sub_status_callback:
            self.sub_status_callback(data)
        # Light console log
        event_type = data.get("type", "unknown")
        detail = data.get("tool", data.get("message", ""))
        print(f"[SUB_STATUS] {event_type}: {detail}")


# ══════════════════════════════════════════════════════════════════════════════
# DEBUG LOGGING
# ══════════════════════════════════════════════════════════════════════════════

def log_debug(title: str, content: Any):
    """Helper to log verbose output to terminal."""
    def json_serializer(obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    print(f"\n{'='*20} {title} {'='*20}")
    if isinstance(content, (dict, list)):
        try:
            print(json.dumps(content, indent=2, ensure_ascii=False, default=json_serializer))
        except Exception as e:
            print(f"[LOG ERROR] Could not serialize: {e}")
            print(str(content))
    else:
        print(str(content))
    print(f"{'='*50}\n")


# ══════════════════════════════════════════════════════════════════════════════
# JSON PARSING — handles markdown code blocks, <think> tags, LLM quirks
# ══════════════════════════════════════════════════════════════════════════════

def parse_json_response(content: str) -> Dict:
    """Parse JSON from LLM response. Identical to HRAgent._parse_json_response."""
    original_content = content

    # Strip <think>...</think> tags
    content = re.sub(r'<think>[\s\S]*?</think>', '', content, flags=re.IGNORECASE)
    content = re.sub(r'<think>[\s\S]*$', '', content, flags=re.IGNORECASE)

    # Extract from markdown code block
    json_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', content)
    if json_match:
        content = json_match.group(1)

    content = content.strip()

    def fix_json_quirks(text: str) -> str:
        text = re.sub(r',\s*([}\]])', r'\1', text)
        text = re.sub(r'\bTrue\b', 'true', text)
        text = re.sub(r'\bFalse\b', 'false', text)
        text = re.sub(r'\bNone\b', 'null', text)
        return text

    # Try direct parse
    for attempt_content in [content, fix_json_quirks(content)]:
        try:
            return json.loads(attempt_content)
        except json.JSONDecodeError:
            pass

    # Try to find JSON objects in content
    matches = re.finditer(r'\{', content)
    for m in matches:
        start_idx = m.start()
        brace_count = 0
        for i in range(start_idx, len(content)):
            if content[i] == '{':
                brace_count += 1
            elif content[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    extracted = content[start_idx:i+1]
                    for attempt_content in [extracted, fix_json_quirks(extracted)]:
                        try:
                            return json.loads(attempt_content)
                        except json.JSONDecodeError:
                            pass
                    break

    print(f"[JSON PARSE FAILED] Could not parse LLM response as JSON.")
    print(f"[JSON PARSE FAILED] Full content length: {len(original_content)}")
    return {}
