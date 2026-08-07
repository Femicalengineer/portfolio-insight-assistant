import os
import getpass
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent



if not os.environ.get("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = getpass.getpass("Enter your Anthropic API key: ")

async def main():
    client = MultiServerMCPClient({
        "get_quote": {"transport": "http",
                      "url": "https://portfolio-insight-assistant.onrender.com/mcp"}
    })
    tools = await client.get_tools()

    agent = create_agent(
        model= 'claude-haiku-4-5',
        system_prompt = "You are a helpful assistant with access to a tool that will get a quote for a given ticker symbol.",
        tools=tools,
    )
    
    return agent

if __name__ == '__main__':
    asyncio.run(main())
