import asyncio
from fastmcp import Client

async def main():
    client = Client("http://localhost:8080/mcp")  # Replace with the actual URL of your FastMCP server
    async with client:
        result = await client.call_tool("get_quote", {"symbol": "AAPL"})
        print(result)


asyncio.run(main())
