# consult_portfolio_analyst.py
# Unlike get_quote, this tool's data comes from the caller (or the model's
# own knowledge/assumptions), not an external API -- no MCP server involved.


import os
import getpass
from langchain.agents import create_agent
from langchain_core.tools import tool

from pydantic import BaseModel, Field




if not os.environ.get("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = getpass.getpass("Enter your Anthropic API key: ")

def optimal_risky_weights(returns: list[float], volatilities: list[float], covariance: float, risk_free_rate: float) -> tuple[float, float]:
    """Tangency portfolio weights for two risky assets (maximizes Sharpe ratio).
    This is done by calculating the derivative because..."""
    excess_return_1 = returns[0] - risk_free_rate
    excess_return_2 = returns[1] - risk_free_rate
    variance_1 = volatilities[0] ** 2
    variance_2 = volatilities[1] ** 2

    numerator = excess_return_1 * variance_2 - excess_return_2 * covariance
    denominator = (
        excess_return_1 * variance_2
        + excess_return_2 * variance_1
        - (excess_return_1 + excess_return_2) * covariance
    )

    weight_1 = numerator / denominator
    weight_2 = 1 - weight_1
    return weight_1, weight_2


def optimal_risky_share(portfolio_return: float, portfolio_volatility: float, risk_free_rate: float, risk_aversion: float) -> float:
    """Fraction to allocate to the risky portfolio P vs. the risk-free asset, given risk aversion A."""
    return (portfolio_return - risk_free_rate) / (risk_aversion * portfolio_volatility ** 2)




class ArgsSchema(BaseModel):
    tickers: list[str] = Field(..., description="List of stock tickers in the portfolio")  # labels only -- not used in any calculation
    expected_returns: list[float] = Field(..., description="List of expected returns for each stock in the portfolio")  # E(r_i): mean/average return assumed for each asset
    volatilities: list[float] = Field(..., description="List of volatilities for each stock in the portfolio")  # sigma_i: standard deviation of each asset's returns
    correlations: list[list[float]] = Field(..., description="Matrix of correlations between stocks in the portfolio")  # how each pair of assets moves together: -1 to +1, diagonal always 1
    risk_free_rate: float = Field(..., description="The risk-free rate")  # r_f: return of a theoretically riskless asset (e.g. a T-bill) -- the baseline everything else is measured against
    risk_aversion: float = Field(..., description="The risk aversion parameter")  # A: higher = more risk-averse (safer split), lower = more risk-tolerant (leans into more risk/leverage)




@tool(args_schema=ArgsSchema)
def analyze_portfolio(tickers: list[str], expected_returns: list[float], volatilities: list[float], correlations: list[list[float]], risk_free_rate: float, risk_aversion: float) -> dict:
    """
    Given a set of assets and their expected-return/volatility/correlation assumptions, find the
    optimal portfolio: the allocation among the risky assets that maximizes the Sharpe ratio (the
    tangency portfolio), that portfolio's own expected return/volatility/Sharpe ratio, and the
    optimal split between that risky portfolio and the risk-free asset given the caller's risk aversion.
    """

    covariance_matrix = [[c * v1 * v2 for c, v2 in zip(row, volatilities)] for row, v1 in zip(correlations, volatilities)]

    # step 1: find the allocation of risky assets that makes the CAL tangent to the risky-asset
    # opportunity set, i.e. maximizes the Sharpe ratio (the tangency/optimal risky portfolio)
    optimal_risky_weights_output = optimal_risky_weights(expected_returns, volatilities, covariance_matrix[0][1], risk_free_rate)

    # portfolio-level stats, evaluated at the optimal weights (not a caller-supplied portfolio)
    portfolio_expected_return = sum(w * r for w, r in zip(optimal_risky_weights_output, expected_returns))
    portfolio_volatility = (sum(w1 * w2 * covariance_matrix[i][j] for i, w1 in enumerate(optimal_risky_weights_output) for j, w2 in enumerate(optimal_risky_weights_output))) ** 0.5
    sharpe_ratio = (portfolio_expected_return - risk_free_rate) / portfolio_volatility if portfolio_volatility != 0 else 0

    # step 2: allocation of risky vs. risk-free assets based on risk aversion, i.e. where the CAL is tangent to the investor's own utility/indifference curve
    optimal_risky_share_output = optimal_risky_share(portfolio_expected_return, portfolio_volatility, risk_free_rate, risk_aversion)

    result = {
        'tickers': tickers,
        'optimal_risky_weights': optimal_risky_weights_output,
        'optimal_risky_share': optimal_risky_share_output,
        'portfolio_expected_return': portfolio_expected_return,
        'portfolio_volatility': portfolio_volatility,
        'sharpe_ratio': sharpe_ratio
    }

    return result



def main():
    """
    This function will return an agent with access to the tool. Note only the agent is retuned so in future steps the agent will be embedded in a sepereate tool and .invoke will be called there. This format works so that a supervisor agent can call that parent tool while not performing a handoff. 
    """

    agent = create_agent(
        model= 'claude-haiku-4-5',
        system_prompt = "You are a helpful assistant with access to a tool that will analyze a portfolio of risky assets and determine the optimal allocation among them and between the risky portfolio and a risk-free asset. If you do not have the information you need to call the tool correctly (expected returns, volatilities, correlations, risk-free rate, or risk aversion), ask the user for the missing values -- don't speculate using your own knowledge. Additionally, if you don't have the knowledge you need after calling the tool, also don't speculate.",
        tools=[analyze_portfolio],
    )
    return agent


if __name__ == "__main__":
    agent = main()
    # result = analyze_portfolio.invoke({ "tickers": ["AAPL", "MSFT"], "expected_returns": [0.1, 0.15], "volatilities": [0.2, 0.25], "correlations": [[1, 0.3], [0.3, 1]], "risk_free_rate": 0.05, "risk_aversion": 1.0 })  # sanity check the tool
    result = agent.invoke({"messages":[{"role":"user", "content":"Analyze a portfolio with tickers AAPL and MSFT, expected returns of 0.1 and 0.15, volatilities of 0.2 and 0.25, correlations of [[1, 0.3], [0.3, 1]], a risk-free rate of 0.05, and a risk aversion of 1.0."}]})
    print(result['messages'][-1].content)
