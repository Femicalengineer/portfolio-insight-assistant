# Runbook — Portfolio Insight Assistant

Practical "how do I actually do X" reference for this project — the concrete commands and procedures, as opposed to `PLAN.md` (what to build, in what order) or `DECISIONS.md` (why each choice was made). Each section also notes how to sanity check that step actually worked before moving on.

---

## Questrade practice account setup

- Sign up at `questrade.com/api/free-practice-account` (a distinct signup flow from "Questrade Global," which is a separate forex/CFD product with its own unrelated practice account).
- Account type: **Margin** — no tax-advantaged distinctions matter for a practice account, and Margin has no registered-account trading restrictions.
- Generate an API refresh token: log in to the practice account → account dropdown → **API Centre** → **Register a personal app**:
  - Name and description are both mandatory
  - OAuth scopes: check both (market data + balances/positions/orders) up front, so you don't have to re-register later when adding trading
  - Callback URL: must be **HTTPS** — a placeholder like `https://example.com/callback` is fine, since the manual token flow below never actually redirects there
- On the app's page: **New manual authorization** → **Generate new token** → **Copy token** before closing the popup (Questrade never shows it again).
- The token shown is a **refresh token**, not the access token used to actually authenticate. It expires in **7 days** and is **single-use** — every exchange issues a new refresh token that replaces it.

**Sanity check:** the account dashboard should show an explicit "Practice"/"Demo" label.

## Local secrets setup

- `.env` lives at the project root (`012_capstone_portfolio_insight_assistant/.env`), not inside `012_app/mcp_server/`.
- `.gitignore` at the project root excludes it.
- Format: `QUESTRADE_REFRESH_TOKEN=<value>`.

**Sanity check, without ever printing the secret itself:** line count (`wc -l .env` should be 1), and the value's length/absence of stray quotes or whitespace — enough to rule out file corruption without exposing anything sensitive.

## OAuth token exchange (`get_access_token`)

- Endpoint: `https://login.questrade.com/oauth2/token`, with `grant_type=refresh_token` and `refresh_token=<token>` sent as **query parameters** (`params=` in `requests`), not a request body (`data=`) — despite it being a POST.
- Response JSON contains: `access_token`, `refresh_token` (the new, rotated one), `token_type`, `expires_in`, `api_server` (the host to send all subsequent API calls to — not a fixed domain).
- **Persistence across runs:** because the refresh token is single-use, the newly-issued one has to be saved back to `.env`, or the next run will use the now-dead old value.
  - `find_dotenv()` gets the actual resolved path `load_dotenv()` used (don't hardcode `.env` as a literal string — that's resolved relative to wherever the script happens to be *run from*, not where the script file lives).
  - `set_key(path, "QUESTRADE_REFRESH_TOKEN", new_value)` rewrites that file.
  - `load_dotenv(override=True)` is required (not just `load_dotenv()`) for a later call in the same process to pick up a value that changed on disk since the last load.

**Sanity check:** confirm the returned dict has all five fields (`access_token`, `refresh_token`, `token_type`, `expires_in`, `api_server`), and check `.env`'s modification time and structure after the call to confirm the rotated token actually got written back.

## `get_quote`

- Questrade quotes are keyed by an internal numeric **symbol ID**, not the ticker string — two calls needed:
  1. `GET {api_server}v1/symbols/search?prefix=<ticker>` → pull `symbols[0]["symbolId"]`
  2. `GET {api_server}v1/markets/quotes?ids=<symbolId>` → pull `quotes[0]["askPrice"]`
- Both authenticated via header: `Authorization: Bearer <access_token>` (not a query param, unlike the OAuth exchange itself).
- Return type hints matter specifically for MCP tools: FastMCP builds a schema from the function's declared return type and validates the actual return value against it at call time — `askPrice` is a `float`, so the tool's signature needs to say `-> float`.

**Sanity check:** call it directly as a plain function first (outside MCP entirely) with a real ticker and confirm a real numeric price comes back, before wrapping it as a tool.

## Wrapping as an MCP tool

- `@mcp.tool()` — the function signature becomes the schema an agent can actually call with. Anything the tool needs that an agent *can't* supply (like auth tokens) has to be fetched internally inside the function, not received as a parameter.
- Progression: `stdio` first (`mcp.run(transport="stdio")`), then `http` (`mcp.run(transport="http", port=..., host="0.0.0.0")`).
- Testing requires an actual MCP client — curl can't call `@mcp.tool()` functions, since they only speak the MCP protocol. Use a small separate script:
  ```python
  from fastmcp import Client
  client = Client("questrade_mcp_server.py")        # stdio: points at the file directly
  client = Client("http://localhost:8765/mcp")       # http: needs the /mcp path suffix
  async with client:
      result = await client.call_tool("get_quote", {"symbol": "AAPL"})
  ```

**Sanity check:** the test script above, run against a real symbol, should return `is_error=False` and a real numeric `data` value.

## `/health` endpoint

- `@mcp.custom_route(path="/health", methods=["GET"])` registers a plain HTTP route alongside the MCP protocol — reachable by anything that speaks ordinary HTTP (curl, a browser, Render's health monitor), not gated behind MCP at all.
- The handler accepts the incoming request as a parameter, and returns a Starlette `JSONResponse` (`from starlette.responses import JSONResponse`) — not a plain dict the way a `@mcp.tool()` function can.

**Sanity check:** with the server running, either `curl http://localhost:8765/health` in a second terminal, or just open `http://localhost:8765/health` directly in a browser's address bar — both work identically for a plain GET endpoint.

## Dockerizing

- `Dockerfile` pattern (same shape as 010): base image → `WORKDIR` → copy + install `requirements.txt` → copy the actual app file → `CMD`.
- `CMD` is the literal command used to start the app (`["python", "questrade_mcp_server.py"]`) — the same thing typed in a terminal to run it locally.
- `requirements.txt` only lists third-party packages actually installed via `pip` — standard-library modules (`os`, `asyncio`) don't belong in it, and the package name isn't always the same as the import name (`pip install python-dotenv`, but `from dotenv import ...`).
- Never `COPY .env` into the image — secrets get forwarded at `docker run` time instead.

**Sanity check:** `docker build -t <name> .` should complete without error before moving on to `docker run`.

## Running and testing the container

1. **Forward the secret in** — a container has no access to your local `.env` file or shell environment unless explicitly passed. Full copy-paste sequence, in one terminal, run start to finish without anything else in between (a local non-Docker run or another test in the middle will rotate the token and leave the shell's exported copy stale):
   ```bash
   # if a previous container is still running, stop and remove it first
   # (--name below means it's always called "questrade-mcp", not a random Docker-generated name)
   docker stop questrade-mcp 2>/dev/null
   docker rm questrade-mcp 2>/dev/null

   # load the current refresh token into this shell session
   cd "/Users/Sarah/Documents/Programming/MMAI Python Bootcamp/2026_Upskill/Projects/012_capstone_portfolio_insight_assistant"
   set -a
   source .env
   set +a

   # build and run
   cd 012_app/mcp_server
   docker build -t questrade-mcp-server .
   docker run --name questrade-mcp -p 8080:8765 -e QUESTRADE_REFRESH_TOKEN="$QUESTRADE_REFRESH_TOKEN" questrade-mcp-server
   ```
   In a **second terminal**, once the container's running:
   ```bash
   # plain HTTP route -- curl or a browser both work
   curl http://localhost:8080/health

   # MCP tool -- needs the actual client script, not curl
   # (test_servers.py's Client URL should point at http://localhost:8080/mcp)
   python3 test_servers.py
   ```

2. **Port mapping (`-p host:container`)** — the two sides mean different things:
   - The **right side** (container port) must match whatever the app actually binds to inside the code (`8765`).
   - The **left side** (host port) is an arbitrary number chosen for what you type on your own machine (`8080` here) — doesn't need to match anything in the code.
   - Curl/test scripts always target the **host** side.

3. **`host="0.0.0.0"` in `mcp.run(...)` is required for Docker.** `127.0.0.1` only accepts connections that originate from the same machine, and traffic Docker forwards in from outside the container doesn't count as "the same machine" from the container's point of view — `0.0.0.0` means "accept connections on any interface." Works fine for local (non-Docker) testing too, so there's no downside to always setting it.

4. **Refresh-token persistence inside a container is a known open item, not yet fully solved** (see `DECISIONS.md`): there's no `.env` file inside a container to write the rotated token back to, so `get_access_token` currently just skips that step gracefully when none exists. This means a container can successfully call `get_quote` once per token it was started with; a second call or a restart needs a fresh one. The real fix (keeping a rotating credential valid across restarts on a real deployed service) is deferred to the actual Render deploy.

## Deploying to Render

- GitHub repo: `github.com/Femicalengineer/portfolio-insight-assistant` — pushed with `git add` / `git commit` / `git remote add origin <url>` / `git push -u origin main`.
- Render dashboard → **New** → **Web Service** → connect the GitHub repo.
- **Root Directory**: `012_app/mcp_server` — the Dockerfile isn't at the repo root, so Render needs to know where to actually find it and build its context from.
- **Dockerfile Path**: `012_app/mcp_server/Dockerfile` — per Render's own field description, this one is relative to the *repo root*, not the Root Directory above (a real, easy-to-miss distinction between the two fields).
- Environment variable: `QUESTRADE_REFRESH_TOKEN` set directly in Render's dashboard (not committed anywhere in the repo) — needs to be a **currently valid** token, checked directly against Questrade before pasting it in, since a stale one fails the exact same way it does locally.
- Deployed URL: `https://portfolio-insight-assistant.onrender.com`

**Sanity check:** same two-step check as local Docker testing, just against the real URL instead of `localhost` — `curl https://portfolio-insight-assistant.onrender.com/health`, then point `test_servers.py`'s `Client(...)` at `https://portfolio-insight-assistant.onrender.com/mcp` and confirm `get_quote` still works for real.

**Sanity check, in order:** `docker ps -a` confirms the container is running and shows its actual port mapping; `curl`/browser against `/health` on the **host**-side port confirms the server is reachable at all; the MCP test script (pointed at `http://localhost:<host_port>/mcp`) confirms `get_quote` works end-to-end through the container. If something fails, `docker logs <container name>` shows the real traceback happening inside the container — often more informative than whatever error message made it back to the client.

## Building `consult_market_trading_specialist` (step 4)

- Load the deployed MCP server's tools with `MultiServerMCPClient` (from `langchain_mcp_adapters.client` — a separate package, not `langchain.mcp_adapters`), `http` transport, pointed at the live URL's `/mcp` path:
  ```python
  client = MultiServerMCPClient({
      "questrade": {"transport": "http", "url": "https://portfolio-insight-assistant.onrender.com/mcp"}
  })
  tools = await client.get_tools()  # async -- needs await
  ```
- Build the specialist with `create_agent(model=..., system_prompt=..., tools=tools)`, same as any other agent in this curriculum.
- **Don't invoke the specialist inside its own definition file.** Matches 005's `hr_agent` pattern exactly: the agent is defined once, and only ever invoked either through a separate test script or (later) through a `@tool`-wrapped function that a supervisor calls — never a standalone `.invoke()` call sitting in the same file as the `create_agent(...)` call itself.
- Since building the agent requires an `await` (loading MCP tools is async), the definition file's entry point needs to be an `async def` function that **returns** the built agent, wrapped in `if __name__ == "__main__":` — not a bare `asyncio.run(...)` at module level, which would fire as a side effect the moment the file is *imported*, not just when run directly.
- **Invoking a `create_agent` result always takes a dict matching its State schema, never a bare string:** `agent.invoke({"messages": [{"role": "user", "content": "..."}]})` (or `await agent.ainvoke(...)` in an async context). This is because `create_agent` runs on a LangGraph `MessagesState` schema (`{"messages": [...]}`, using an `add_messages` reducer that appends rather than overwrites) — not a simple one-variable LCEL chain, which is the context where invoking with a plain string works.
- Result access is dict-style, not attribute-style: `result["messages"][-1].content`, never `result.messages`.
- **Debugging a tool error inside an agent:** `create_agent` catches tool errors and feeds them back to the model as a `ToolMessage`, which the model then paraphrases vaguely ("I encountered an error..."). The real error is inside `result["messages"]` — print the full list, not just the last message, to find the actual `ToolMessage` content.
- **The deployed service has its own separate copy of `QUESTRADE_REFRESH_TOKEN`, set in Render's dashboard — updating local `.env` alone does not fix a stale token there.** Both need updating independently when the token dies (which happens more often than expected — see `DECISIONS.md`'s note on the accepted in-memory-caching tradeoff). Updating an env var through Render's dashboard UI triggers an automatic redeploy; if it doesn't, there's a manual "Deploy" button.

**Sanity check:** ask the specialist a real question (e.g. "what is the price of AAPL stock?") and confirm it correctly chooses to call `get_quote` and returns a real answer — not just that the file runs without crashing.

## Extracting the MPT deck into a RAG-ready corpus

- The `Read` tool can't open `.pptx` files directly (binary format, unsupported) — use `python-pptx` (`pip install python-pptx`) instead.
- Per slide: `slide.shapes` gives you the text frames (`shape.text_frame.text`) and pictures (`shape.shape_type == 13`, then `shape.image.blob` to get the raw image bytes to save as a file); `slide.notes_slide.notes_text_frame.text` gives the speaker notes.
- **Don't assume text/notes alone capture the real content.** For this deck specifically, most of the substantive material is in charts/diagrams (efficient frontier plots, CAL diagrams), not slide text — extracted images were reviewed directly (via the `Read` tool's image support) and given a written description, folded into the same corpus entries the text/notes live in. See `DECISIONS.md` for why this was chosen over notes-only or full multimodal retrieval.
- **Not every image is a chart worth describing** — one slide in this deck turned out to be an unrelated interactive quiz question (not a plot at all), and some "images" on a single slide are really animation fragments of one diagram, not distinct content. Worth actually looking before writing a description for each one, rather than assuming every embedded image is meaningful content.
- Final corpus is a structured list, one entry per slide (`{"slide": n, "title": ..., "text": [...], "notes": ..., "image_descriptions": [...]}`) — not a single flattened document — specifically so slide number/section metadata survives for `SelfQueryRetriever` later, per the retrieval techniques already committed to in `DECISIONS.md`.
- Output: `012_app/agent_service/data/mpt_deck_content.json`, scoped to slides 3–6 and 26–48 only (see `DECISIONS.md`'s knowledge-base-scope decision) — 27 slide entries, 10 with image descriptions.

**Sanity check:** spot-check a few entries against the actual deck — does the extracted text/notes match what's on the slide, and does the written image description actually match what the chart shows (numbers, axis labels, the specific relationship being illustrated), not just a generic "this is a chart about portfolio theory."

## Building `consult_portfolio_analyst` (step 5)

- Unlike `get_quote`, this specialist's tool (`analyze_portfolio`) is a **local `@tool`**, not MCP-sourced — no external server involved, just computation on given inputs. Same `create_agent`-wrapping-a-tool shape as `consult_market_trading_specialist`, just a local `@tool` instead of an MCP-loaded one.
- **Per-argument descriptions on a tool**, via a Pydantic `args_schema`, matter a lot once a tool has several parameters (this one has six, some structurally complex like a correlation matrix) — worth doing whenever a tool's inputs aren't self-explanatory from bare type hints alone:
  ```python
  from pydantic import BaseModel, Field
  from langchain_core.tools import tool

  class ArgsSchema(BaseModel):
      some_param: float = Field(..., description="...")

  @tool(args_schema=ArgsSchema)  # NOT arg_schema (no 's') -- and pass the class itself, not `.schema()`'s dict output
  def my_tool(some_param: float) -> dict:
      ...
  ```
- **Given/assumed inputs vs. computed outputs, a distinction worth keeping straight:** each asset's own expected return/volatility/correlation are facts about the assets (can't be derived by the tool, have to come from outside — historical data, estimates, or given inputs per the decision in `DECISIONS.md`). Portfolio *weights*, by contrast, are the decision variable this specific tool exists to solve for — supplying them as an input would be circular. Don't conflate "things that must be given" with "things the calculation produces."
- **Testing a `@tool`-decorated function directly (not through an agent) uses `.invoke({...})`, not a plain function call** — `@tool` turns the function into a LangChain tool object, so `my_tool(x=1, y=2)` doesn't work the way it did before decorating; `my_tool.invoke({"x": 1, "y": 2})` does. Same "test as a plain function first, decorate once the logic's proven" progression as `get_quote`, just with `.invoke()` as the test call once `@tool` is live, instead of reverting the decorator.
- **Validate against a real worked example with a known answer**, not just "it ran without an error" — the MPT deck's own slide 36 (Debt 8%/12%σ, Equity 13%/20%σ, correlation 0.30, risk-free 5%) has a stated final answer (~40/60 optimal risky-asset split) to check the code against directly, rather than trusting arbitrary placeholder numbers.

**Sanity check:** ask the specialist a real question with concrete numbers and confirm the tool's output matches a hand-calculated (or deck-verified) answer — not just that the agent responds fluently.

## Embedding the MPT deck corpus into Chroma (step 5, concepts specialist groundwork)

- Reuses 003's exact pattern: `HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")` (**keyword argument only** — passing the model name positionally raises `TypeError: takes 1 positional argument but 2 were given`), `Document(page_content=..., metadata={...})` objects, `Chroma.from_documents(documents=..., embedding=..., collection_name=..., ids=[...])`.
- **`page_content` needs to be joined plain text, not `str()` on a list.** The corpus's `text` and `image_descriptions` fields are `list[str]` — calling `str(some_list)` embeds the literal Python repr (brackets, quotes, commas) as text. Use `" ".join(...)` instead, so the embedding sees natural language.
- **`.persist()` is deprecated** (Chroma 0.4.x+ auto-persists) — the thing that actually matters is passing `persist_directory=...` directly to `Chroma.from_documents(...)`. Without it, the store is in-memory only regardless of any `.persist()` call afterward.
- A `None` value in Chroma document metadata (some slides have `title: None`, since they have no text frames) turned out not to cause any issue — confirmed by actually running it, not assumed.
- Output: `012_app/agent_service/data/chroma_mpt_deck_vectorstore/` (persisted Chroma collection, 27 documents, one per in-scope slide, metadata: `slide`, `title`, `section`).

**Sanity check:** confirm the persist directory actually contains a real `chroma.sqlite3` file with a nonzero size after running — "no errors printed" isn't proof anything was actually written to disk.
