"""
Agent Runner for HR Agent.
Bridges the Flask backend with the HRAgent core.
Supports both direct agent invocation and MCP client mode.
"""
import sys
import os
import asyncio
from typing import Optional, Callable

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.core import HRAgent, get_agent


async def run_agent(
    user_input: str,
    context: str = "",
    user_id: int = 1,
    conversation_id: Optional[int] = None,
    status_callback: Optional[Callable[[str], None]] = None,
    stage_callback: Optional[Callable[[dict], None]] = None,
    sub_status_callback: Optional[Callable[[dict], None]] = None,
    use_full_pipeline: bool = True,
    session_id: Optional[str] = None
) -> dict:
    """
    Run the HR Agent with the given input.
    
    Args:
        user_input: User's question or command
        context: Additional context (e.g., system prompt, previous messages)
        user_id: User ID for conversation tracking
        conversation_id: Optional existing conversation ID
        status_callback: Optional callback for status updates
        stage_callback: Optional callback for stage completion data
        use_full_pipeline: Whether to use full 4-stage pipeline (True) or simplified mode
        session_id: Socket session ID – used for abort/stop support
        
    Returns:
        Dict containing:
        - response: The final response string
        - conversation_id: The conversation ID used
        - metadata: Additional information about the execution
        - tool_results: Results from any tools called (if any)
        - stage_logs: Stage completion logs for Process tab
    """
    # Get or create agent instance
    agent = get_agent()
    
    # Reset stage logs for new conversation turn
    agent._stage_logs = []

    # Update callbacks if provided
    if status_callback:
        agent.status_callback = status_callback
    if stage_callback:
        agent.stage_callback = stage_callback
    if sub_status_callback:
        agent.sub_status_callback = sub_status_callback
    
    # Run the agent
    if use_full_pipeline:
        result = await agent.chat(
            query=user_input,
            user_id=user_id,
            conversation_id=conversation_id,
            skip_escalation=False,
            skip_planning=False,
            session_id=session_id
        )
    else:
        # Simplified mode: skip escalation and planning
        result = await agent.chat(
            query=user_input,
            user_id=user_id,
            conversation_id=conversation_id,
            skip_escalation=True,
            skip_planning=True,
            session_id=session_id
        )
    
    return result



async def run_agent_simple(user_input: str, context: str = "") -> str:
    """
    Simplified agent runner that only returns the response string.
    For backward compatibility with existing code.
    
    Args:
        user_input: User's question or command
        context: Additional context
        
    Returns:
        Response string
    """
    result = await run_agent(user_input, context)
    return result.get("response", "Tidak ada jawaban ditemukan.")


# Legacy function for backward compatibility
async def run_agent_legacy(user_input: str, context: str) -> str:
    """
    Legacy agent runner using MCP SSE client.
    Kept for backward compatibility.
    """
    try:
        from mcp import ClientSession
        from mcp.client.sse import sse_client
        from langchain_mcp_adapters.tools import load_mcp_tools
        from langgraph.prebuilt import create_react_agent
        from langchain_ollama import ChatOllama
        
        model = ChatOllama(model="qwen3:latest")
        
        async with sse_client(url="http://localhost:8000/sse") as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await load_mcp_tools(session)
                agent = create_react_agent(model, tools)
                
                messages = {"messages": [("human", context + user_input)]}
                result = await agent.ainvoke(messages)
                
                for msg in reversed(result["messages"]):
                    if msg.type == "ai" and msg.content:
                        return msg.content.strip()
                        
        return "Tidak ada jawaban ditemukan."
        
    except Exception as e:
        print(f"[AGENT ERROR] Legacy runner failed: {e}")
        # Fallback to new agent
        return await run_agent_simple(user_input, context)


# ============================================================================
# DIRECT TEST
# ============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test HR Agent Runner")
    parser.add_argument("query", nargs="?", default="Siapa yang telat hari ini?", help="Query to test")
    parser.add_argument("--simple", action="store_true", help="Use simplified mode")
    args = parser.parse_args()
    
    print(f"Testing query: {args.query}")
    print("-" * 50)
    
    async def main():
        if args.simple:
            result = await run_agent_simple(args.query)
            print(f"Response: {result}")
        else:
            result = await run_agent(args.query, use_full_pipeline=True)
            print(f"Response: {result.get('response', 'No response')}")
            print(f"\nMetadata: {result.get('metadata', {})}")
            if result.get('tool_results'):
                print(f"\nTools called: {len(result['tool_results'])}")
    
    asyncio.run(main())