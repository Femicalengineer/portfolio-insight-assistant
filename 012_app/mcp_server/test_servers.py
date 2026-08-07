import asyncio
from fastmcp import Client

async def main():
    client = Client("https://portfolio-insight-assistant.onrender.com/mcp")  # Replace with the actual URL of your FastMCP server
    async with client:
        result = await client.call_tool("get_quote", {"symbol": "AAPL"})
        print(result)


asyncio.run(main())
