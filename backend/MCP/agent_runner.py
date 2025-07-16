
from mcp import ClientSession
from mcp.client.sse import sse_client
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent
from langchain_ollama import ChatOllama

model = ChatOllama(model="qwen3:latest")

async def run_agent(user_input: str, context: str):
    async with sse_client(url="http://localhost:8000/sse") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await load_mcp_tools(session)
            print(tools)

            agent = create_react_agent(model, tools)

            messages = {"messages": [("human", context + user_input)]}
            
            # 📋 Logging prompt
            print(messages)
            result = await agent.ainvoke(messages)
            for msg in reversed(result["messages"]):
                if msg.type == "ai" and msg.content:
                    return msg.content.strip()
            return "Tidak ada jawaban ditemukan."