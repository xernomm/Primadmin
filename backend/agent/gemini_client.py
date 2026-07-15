"""
Gemini Client Module — Centralized Google Gemini API interface.

Replaces ollama.chat / ollama.generate with Gemini equivalents.
Provides drop-in helper functions for all pipeline stages and MCP tools.
"""
import os
import json
import traceback
import time
import random
from typing import List, Dict, Any, Optional, Tuple

from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON CLIENT
# ══════════════════════════════════════════════════════════════════════════════

_client: Optional[genai.Client] = None


def get_gemini_client() -> genai.Client:
    """Get or create Gemini client singleton."""
    global _client
    if _client is None:
        api_key = os.getenv("GOOGLE_AI_API")
        if not api_key:
            raise ValueError(
                "GOOGLE_AI_API not found in environment variables. "
                "Please set it in your .env file."
            )
        _client = genai.Client(api_key=api_key)
        print(f"[GEMINI] Client initialized successfully.")
    return _client


# ══════════════════════════════════════════════════════════════════════════════
# MESSAGE CONVERSION
# ══════════════════════════════════════════════════════════════════════════════

def _convert_messages_to_gemini(
    messages: List[Dict[str, str]]
) -> Tuple[Optional[str], list]:
    """
    Convert OpenAI/Ollama-style messages to Gemini format.
    
    Separates system messages into system_instruction,
    and converts user/assistant messages to Gemini Content objects.
    
    Args:
        messages: List of {"role": "system"|"user"|"assistant", "content": "..."}
    
    Returns:
        (system_instruction, contents) tuple
    """
    system_parts = []
    contents = []
    
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        
        if not content:
            continue
        
        if role == "system":
            system_parts.append(content)
        elif role == "user":
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=content)]
                )
            )
        elif role in ("assistant", "model"):
            contents.append(
                types.Content(
                    role="model",
                    parts=[types.Part.from_text(text=content)]
                )
            )
        elif role == "tool":
            # Tool responses → user message in Gemini
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=f"[Tool Result]: {content}")]
                )
            )
    
    system_instruction = "\n\n".join(system_parts) if system_parts else None
    
    return system_instruction, contents


# ══════════════════════════════════════════════════════════════════════════════
# TOOL DEFINITION CONVERSION
# ══════════════════════════════════════════════════════════════════════════════

_TYPE_MAP = {
    "string": "STRING",
    "integer": "INTEGER",
    "number": "NUMBER",
    "boolean": "BOOLEAN",
    "array": "ARRAY",
    "object": "OBJECT",
}


def _convert_schema(schema: Dict) -> Dict:
    """Convert JSON Schema types to Gemini uppercase types recursively."""
    if not isinstance(schema, dict):
        return schema
    
    result = {}
    for key, value in schema.items():
        if key == "type" and isinstance(value, str):
            result[key] = _TYPE_MAP.get(value.lower(), value.upper())
        elif key == "properties" and isinstance(value, dict):
            result[key] = {k: _convert_schema(v) for k, v in value.items()}
        elif key == "items" and isinstance(value, dict):
            result[key] = _convert_schema(value)
        elif key == "default":
            # Skip 'default' — not supported by Gemini Schema
            continue
        elif key == "enum":
            result[key] = value
        else:
            result[key] = value
    
    return result


def convert_tools_to_gemini(ollama_tools: List[Dict]) -> list:
    """
    Convert Ollama/OpenAI-format tool definitions to Gemini FunctionDeclarations.
    
    Args:
        ollama_tools: List of {"type": "function", "function": {"name": ..., "parameters": ...}}
    
    Returns:
        List of Gemini Tool objects
    """
    declarations = []
    
    for tool in ollama_tools:
        func = tool.get("function", tool)  # Handle both wrapped and unwrapped formats
        name = func.get("name", "")
        description = func.get("description", "")
        parameters = func.get("parameters", {})
        
        # Convert JSON Schema types to Gemini types
        converted_params = _convert_schema(parameters)
        
        declarations.append(
            types.FunctionDeclaration(
                name=name,
                description=description,
                parameters=converted_params if converted_params.get("type") else None,
            )
        )
    
    if not declarations:
        return []
    
    return [types.Tool(function_declarations=declarations)]


# ══════════════════════════════════════════════════════════════════════════════
# RETRY UTILITY FOR TRANSIENT ERRORS
# ══════════════════════════════════════════════════════════════════════════════

def _retry_on_exception(func, *args, **kwargs):
    """
    Retry a function call with exponential backoff if a transient error is encountered.
    Handles 503 UNAVAILABLE (high demand/overload) and 429 RESOURCE_EXHAUSTED (rate limits).
    """
    max_retries = 5
    base_delay = 2.0  # start with 2 seconds
    
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            err_msg = str(e)
            is_transient = any(msg in err_msg.lower() for msg in [
                "503", "unavailable", "demand", "overloaded", "temporary", 
                "resource_exhausted", "429", "quota", "rate limit"
            ])
            
            if is_transient and attempt < max_retries - 1:
                # Exponential backoff with random jitter to prevent thundering herd
                delay = base_delay * (2 ** attempt) + random.uniform(0.1, 1.0)
                print(f"[GEMINI] Warning: Transient error encountered ({err_msg}). Retrying in {delay:.2f}s... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
            else:
                # Raise the error if we are out of retries or if it's a non-transient error
                raise e


# ══════════════════════════════════════════════════════════════════════════════
# MAIN API FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def gemini_chat(
    messages: List[Dict[str, str]],
    model: str = "gemini-2.5-flash",
    temperature: float = 0.3,
    max_output_tokens: int = None,
    response_mime_type: str = None,
) -> str:
    """
    Send chat messages to Gemini and return the response text.
    
    Drop-in replacement for:
        response = ollama.chat(model=..., messages=..., options={...})
        content = response.get("message", {}).get("content", "")
    
    Becomes:
        content = gemini_chat(messages=..., model=..., temperature=...)
    
    Args:
        messages: OpenAI/Ollama-style messages list
        model: Gemini model name
        temperature: Generation temperature
        max_output_tokens: Maximum output tokens
        response_mime_type: Optional MIME type (e.g. "application/json")
    
    Returns:
        Response text string
    """
    client = get_gemini_client()
    system_instruction, contents = _convert_messages_to_gemini(messages)
    
    # If contents is empty, push system instruction as user message
    if not contents:
        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=system_instruction or "Hello")]
            )
        ]
        system_instruction = None
    
    # Build config
    config_kwargs = {"temperature": temperature}
    if max_output_tokens:
        config_kwargs["max_output_tokens"] = max_output_tokens
    if response_mime_type:
        config_kwargs["response_mime_type"] = response_mime_type
    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction
    
    config = types.GenerateContentConfig(**config_kwargs)
    
    response = _retry_on_exception(
        client.models.generate_content,
        model=model,
        contents=contents,
        config=config,
    )
    
    # Extract text safely
    try:
        return response.text or ""
    except Exception:
        # Fallback: try to get text from parts
        if response.candidates:
            parts = response.candidates[0].content.parts
            texts = [p.text for p in parts if hasattr(p, 'text') and p.text]
            return "\n".join(texts)
        return ""


def gemini_generate(
    prompt: str,
    model: str = "gemini-2.5-flash",
    temperature: float = 0.3,
    max_output_tokens: int = None,
    response_mime_type: str = None,
) -> str:
    """
    Simple text generation with Gemini.
    
    Drop-in replacement for:
        response = ollama.generate(model=..., prompt=..., options={...})
        text = response.get("response", "")
    
    Becomes:
        text = gemini_generate(prompt=..., model=..., temperature=...)
    
    Args:
        prompt: The text prompt
        model: Gemini model name
        temperature: Generation temperature
        max_output_tokens: Maximum output tokens
        response_mime_type: Optional MIME type
    
    Returns:
        Response text string
    """
    client = get_gemini_client()
    
    config_kwargs = {"temperature": temperature}
    if max_output_tokens:
        config_kwargs["max_output_tokens"] = max_output_tokens
    if response_mime_type:
        config_kwargs["response_mime_type"] = response_mime_type
    
    config = types.GenerateContentConfig(**config_kwargs)
    
    response = _retry_on_exception(
        client.models.generate_content,
        model=model,
        contents=prompt,
        config=config,
    )
    
    try:
        return response.text or ""
    except Exception:
        if response.candidates:
            parts = response.candidates[0].content.parts
            texts = [p.text for p in parts if hasattr(p, 'text') and p.text]
            return "\n".join(texts)
        return ""


def gemini_chat_with_tools(
    messages: List[Dict[str, str]],
    tools: List[Dict],
    model: str = "gemini-2.5-flash",
    temperature: float = 0.3,
) -> Dict[str, Any]:
    """
    Chat with function calling support.
    
    Drop-in replacement for Ollama's native function calling:
        response = ollama.chat(model=..., messages=..., tools=...)
        message = response.get("message", {})
        tool_calls = message.get("tool_calls", [])
    
    Returns:
        Dict with:
        - "content": text content (if model chose not to call tools)
        - "tool_calls": list of {"function": {"name": str, "arguments": dict}}
    """
    client = get_gemini_client()
    system_instruction, contents = _convert_messages_to_gemini(messages)
    
    if not contents:
        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=system_instruction or "")]
            )
        ]
        system_instruction = None
    
    # Convert tools to Gemini format
    gemini_tools = convert_tools_to_gemini(tools)
    
    config_kwargs = {"temperature": temperature}
    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction
    if gemini_tools:
        config_kwargs["tools"] = gemini_tools
    
    config = types.GenerateContentConfig(**config_kwargs)
    
    response = _retry_on_exception(
        client.models.generate_content,
        model=model,
        contents=contents,
        config=config,
    )
    
    # Parse response parts
    result = {"content": "", "tool_calls": []}
    
    if response.candidates:
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'function_call') and part.function_call:
                fc = part.function_call
                result["tool_calls"].append({
                    "function": {
                        "name": fc.name,
                        "arguments": dict(fc.args) if fc.args else {}
                    }
                })
            elif hasattr(part, 'text') and part.text:
                result["content"] += part.text
    
    return result


def append_tool_result_to_contents(
    contents: list,
    assistant_response,
    func_name: str,
    result: Any
) -> list:
    """
    Append a function call result to the contents list for multi-turn tool calling.
    
    Args:
        contents: Current Gemini contents list
        assistant_response: The raw response from Gemini (to include the function call)
        func_name: Name of the function that was called
        result: Result of the function execution
    
    Returns:
        Updated contents list
    """
    # Add the model's function call response
    if assistant_response.candidates:
        contents.append(assistant_response.candidates[0].content)
    
    # Add the function response
    contents.append(
        types.Content(
            role="user",
            parts=[
                types.Part.from_function_response(
                    name=func_name,
                    response={"result": json.dumps(result, ensure_ascii=False, default=str) if not isinstance(result, str) else result}
                )
            ]
        )
    )
    
    return contents
