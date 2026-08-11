# main_portfolio_agent.py
#


import os
import getpass
import asyncio
from langchain_core.tools import tool
from langchain.agents import create_agent


import consult_market_trading_specialist
import consult_portfolio_analyst
import consult_concepts_specialist

if not os.environ.get("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = getpass.getpass("Enter your Anthropic API key: ")



@tool
def consult_portfolio_analyst_agent(question: str) -> str:
    '''Consult the portfolio analyst agent with a question and return the answer.'''
    result = consult_portfolio_analyst.main().invoke({"messages": [{'role': 'user', 'content': question}]})
    return result["messages"][-1].content


@tool
async def consult_market_trading_specialist_agent(question: str) -> str:
    '''Consult the market trading specialist agent with a question and return the answer.'''
    result = await (await consult_market_trading_specialist.get_agent()).ainvoke({"messages": [{'role': 'user', 'content': question}]})
    return result["messages"][-1].content

@tool
def consult_concepts_specialist_agent(question: str) -> str:
    '''Consult the concepts specialist agent with a question and return the answer.'''
    result = consult_concepts_specialist.main().invoke({"messages": [{'role': 'user', 'content': question}]})
    return result["messages"][-1].content


main_agent = create_agent(
    model = 'claude-sonnet-4-5',
    tools = [
        consult_portfolio_analyst_agent,
        consult_market_trading_specialist_agent,
        consult_concepts_specialist_agent
    ],
    system_prompt = "You are a helpful assistant that can answer questions about finance and investing. You have access to three tools: consult_portfolio_analyst_agent, consult_market_trading_specialist_agent, and consult_concepts_specialist_agent. Use these tools to answer questions accurately and concisely. If they don't answer what you need, do not use your own knowldge or speculate. Instead, respond with 'I don't know.' If a question spans multiple tools, use them in sequence and combine their answers.",
    name = "main_portfolio_agent"

)


def main():
    result = asyncio.run(main_agent.ainvoke({"messages": [{'role': 'user', 'content': "What is the current price of AAPL, and given AAPL has an expected return of 12% and volatility of 25%, and Microsoft has an expected return of 15% and volatility of 22%, with a correlation of 0.4, a risk-free rate of 4%, and a risk aversion of 2, what's the optimal allocation between them? Also, what does the Sharpe ratio measure"}]}))
    print(result["messages"][-1].content)


if __name__ == "__main__":
    main()
