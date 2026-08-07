# questrade_mcp_server.py


from fastmcp import Client, FastMCP
import asyncio
from dotenv import load_dotenv, set_key, find_dotenv
import os
import time
import requests
from starlette.responses import JSONResponse
from starlette.requests import Request


mcp = FastMCP("Questrade")

# In-memory cache for the current access token, so we don't burn the single-use
# refresh token on every call -- an access token is valid for expires_in seconds
# (30 min), so we only re-exchange once it's actually close to expiring.
_token_cache = {"access_token": None, "api_server": None, "expires_at": 0}


def get_access_token() -> dict:
   """
   Returns a valid access token + api_server, reusing a cached one if it's
   still fresh, and only exchanging the refresh token when actually needed.

   Like logging in: the access token is short-lived and used to
   authenticate actual API requests, while the refresh token is
   longer-lived and used to get a new access token without a full
   re-login. Refresh tokens are single-use and rotate on every exchange,
   so this always reloads the current value from .env first (never a
   stale in-memory copy) and persists the newly-issued refresh token
   back to .env afterward, so the next call keeps working.

   Returns a dict with at least access_token and api_server (the host to
   send subsequent API requests to).
   """

   # Reuse the cached access token if it hasn't expired yet (60s safety buffer).
   if _token_cache["access_token"] and time.time() < _token_cache["expires_at"] - 60:
       return _token_cache

   load_dotenv(override=True)
   token = os.environ.get("QUESTRADE_REFRESH_TOKEN")

   response = requests.post(url="https://login.questrade.com/oauth2/token", params={"grant_type": "refresh_token", "refresh_token": token}).json()

   # overwrite the old refresh token with the new one in the .env file, if one exists --
   # e.g. inside a container with no .env file, there's nowhere to persist it, so the
   # rotated token is just discarded (known limitation, see DECISIONS.md)
   path = find_dotenv()
   if path:
       set_key(path, "QUESTRADE_REFRESH_TOKEN", response["refresh_token"])

   _token_cache["access_token"] = response["access_token"]
   _token_cache["api_server"] = response["api_server"]
   _token_cache["expires_at"] = time.time() + response["expires_in"]

   return response



@mcp.tool()
async def get_quote(symbol: str) -> float:
    """
    Looks up a live ask price for a ticker symbol from the practice account.

    Questrade quotes are keyed by an internal numeric symbol ID, not the
    ticker string itself, so this first resolves the symbol via the
    symbols search endpoint, then fetches the quote for that ID.
    """

    response = get_access_token()
    access_token, api_server = response['access_token'], response['api_server']

    # Convert ticker to ID
    response = requests.get(url=f"{api_server}v1/symbols/search", params={"prefix": symbol}, headers={"Authorization": f"Bearer {access_token}"}).json()
    symbol = response["symbols"][0]["symbolId"]

    # Get quote for ID
    response = requests.get(url=f"{api_server}v1/markets/quotes", params={"ids": symbol}, headers={"Authorization": f"Bearer {access_token}"}).json()

    quote = response['quotes'][0]['askPrice']

    return quote


@mcp.custom_route(path="/health", methods=["GET"])
def health_check(Request):
    """
    Health check endpoint for the FastMCP server.
    Returns a simple JSON response indicating the server is running.
    """
    return JSONResponse(content={"status": "healthy"}, status_code=200)
   


if __name__ == "__main__":
   mcp.run(transport="http", port=8765, host="0.0.0.0")  # http transport for local testing
