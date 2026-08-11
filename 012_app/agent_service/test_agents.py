from consult_market_trading_specialist import main as consult_market_trading_specialist

import asyncio

async def main():

    agent = await consult_market_trading_specialist()
    result = await agent.ainvoke({'messages':[{'role':'user', 'content':'What is the price of AAPL stock?'}]})
    print(result['messages'][-1].content)
    # print(result['messages'])


asyncio.run(main())