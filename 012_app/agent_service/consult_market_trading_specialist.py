import os
import getpass
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent



if not os.environ.get("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = getpass.getpass("Enter your Anthropic API key: ")

async def get_agent():
    client = MultiServerMCPClient({
        "get_quote": {"transport": "http",
                      "url": "https://portfolio-insight-assistant.onrender.com/mcp"}
    })
    tools = await client.get_tools()

    agent = create_agent(
        model= 'claude-haiku-4-5',
        system_prompt = "You are a helpful assistant with access to a tool that will get a quote for a given ticker symbol. If you do not have the information you need to call the tool correctly, don't speculate using your own knowledge -- instead respond saying you don't know. Additionally, if you don't have the knowledge you need after calling the tool, also don't speculate.",
        tools=tools,
    )
    
    return agent

def main():
    agent = asyncio.run(get_agent())
    return agent

if __name__ == '__main__':
    agent = main()
