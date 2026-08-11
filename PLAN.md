# Capstone Plan — Portfolio Insight Assistant

Planning conversation from 2026-07-31/08-01. Not yet built — this is the agreed-on shape before implementation starts.

## Context for a fresh Claude session (read this first)

**What happened 2026-08-07, worth knowing before touching the Concepts specialist:** while prepping to build `consult_portfolio_analyst`, reviewing the MPT deck surfaced two things that reshaped `consult_concepts_specialist`'s scope. First, most of the deck's real content turned out to be in plots/diagrams, not slide text — a text-only RAG corpus would have silently lost most of the substance, so each image-bearing slide's chart was manually reviewed and given a written description, folded into the same text corpus rather than building separate multimodal retrieval infrastructure (see `DECISIONS.md`). Second, on reviewing the content, the CAPM/Single Index Model/Fama-French sections turned out to serve no actual use case in this system (none of the specialists estimate returns via a pricing model — Portfolio Analyst uses given/assumed inputs) — so the knowledge base was permanently scoped down to just rate-of-return + capital-allocation/optimal-portfolio content (slides 3–6, 26–48), not the full deck. The extracted, structured corpus is at `012_app/agent_service/data/mpt_deck_content.json`, ready for chunking/embedding whenever `consult_concepts_specialist` actually gets built.

**This project has three companion docs, read together:** `PLAN.md` (this file) — what's being built and in what order, including a running "Notes queued for `012_capstone.ipynb`" list further down; `DECISIONS.md` — why each nontrivial choice was made, kept so Sarah can explain her reasoning in an interview; `RUNBOOK.md` — practical "how do I actually do X" reference (exact commands, gotchas, how each piece was sanity-checked), covering things like Questrade account setup, the OAuth token exchange, MCP tool wrapping, and Docker. If picking up mid-build, check `RUNBOOK.md` before re-deriving a procedure from scratch — it's very likely already documented there.

**Who Sarah is, and the goal:** Sarah is self-teaching to become an **LLM Application Engineer**, building her own curriculum of numbered Jupyter notebooks rather than following a pre-made course. By her own direct statement, her LLM/ML knowledge is scoped entirely to what these notebooks have covered — don't assume outside professional background; explain genuinely new tools/concepts ground-up rather than assuming familiarity (this has been direct, confirmed feedback across the project).

**Where the curriculum lives:** `Phase 2/03_Anthropic_Notes/` in this repo (`2026_Upskill/`), which is its own standalone git repo (`llm-application-engineer-notes`, pushed to GitHub), separate from the rest of this "Upskill" folder. Full history and design rationale for every notebook lives in that folder's `Roadmap.md` — read it for authoritative, up-to-date state before assuming anything below is still current.

**The numbered sequence (theory → applied), all completed as of 2026-07-31:**
- `000a`/`000b`/`000c` — theory precursors (RLHF/DPO/Constitutional AI, prompting techniques, inference optimization — copied into the repo from an older `Phase_1/` location)
- `001` — LangChain/Anthropic fundamentals (chat models, messages, structured output, RAG, memory, LCEL, tools & agents)
- `002` — RAG + conversational memory
- `003` — Vector databases deep dive (embeddings, ANN search, Chroma, chunking, hybrid search/re-ranking)
- `004` — LangGraph fundamentals: what `create_agent` hides underneath (`StateGraph`, nodes/edges, checkpointer)
- `005` — **Multi-agent orchestration** — five patterns built and compared: **Router** (classify-then-dispatch), **Handoffs** (one agent transfers control to another), **Subagents** (a main agent calls specialists as tools and *stays in charge* — the main agent never automatically sees a specialist's internal state; anything needed has to be deliberately propagated up, e.g. via an `.artifact` field), **Skills** (no second agent at all, just a loaded capability), and **Reflection/Reflexion** (a critique-revise loop). This notebook is the one the Capstone's own agent-graph choice draws from.
- `006` — Advanced retrievers (MultiQueryRetriever, SelfQueryRetriever, re-ranking)
- `007` — Evaluation for LLM apps (retrieval metrics, LLM-as-judge, LangSmith tracing/datasets/regression testing)
- `008` — Production reliability (idempotency, tracing, retry/fallback middleware, guardrails — PII + jailbreak checks, secrets via `.env`, cost/latency optimization, testing/mocking)
- `009` — Gradio UI (chat interface, streaming, per-user session state, LangGraph `Store`) — deliberately left the frontend calling `create_agent` directly rather than a real backend, flagged as a gap for the Capstone to close
- `010` — FastAPI + Docker fundamentals (wrapping an agent as a real HTTP service, async endpoints, Dockerizing it, secrets in a container — never bake a `.env` into the image)
- `011` — **MCP fundamentals** — building/consuming MCP servers (FastMCP), STDIO vs. HTTP transports, `langchain-mcp-adapters`' `MultiServerMCPClient` to load MCP tools into `create_agent(tools=[...])` as ordinary `StructuredTool` objects, and MCP's own permission/approval model (a server can require consent before a consequential tool call executes, *independently* of whatever guardrails the calling agent has — this is the direct precedent for the Capstone's two-layer trade-approval design below)

**Also separate from the numbered sequence:** a completed midterm project (`Projects/midterm_throne_of_glass_companion.ipynb`) built using 001–007's mechanisms — a multi-agent RAG companion app for a book series. Sarah specifically liked one thing about debugging it: a main agent calling nested specialist agents (`main_agent → consult_character_agent → character_agent → character_bio_specialist`), where inner agent state does *not* automatically surface to the outer agent — she had to manually propagate the right data up through each layer via an `.artifact` field. She asked, while building notebook 010, for the Capstone to deliberately recreate that same "propagate the right thing up through each boundary" experience, but with an **MCP server call** as the new outermost boundary instead of just another nested `create_agent`. That request is why this Capstone's architecture (below) specifically uses the Subagents pattern with an MCP-sourced tool at the innermost layer, rather than any other multi-agent pattern.

**What "the Capstone" is:** the final planned notebook in the sequence (numbered `012`), meant to be an end-to-end system combining everything above — Chroma + advanced retrievers, multi-agent LangGraph, MCP integration, an eval suite proving it actually works, production reliability practices, a FastAPI backend, Docker, and a Gradio frontend that finally calls that backend over HTTP instead of `create_agent` directly (closing 009's deliberately-left-open gap). It should also include a real cloud/PaaS deployment and light monitoring, since 010's Docker container never left Sarah's laptop.

**Why this specific project (Portfolio Insight Assistant) was chosen as the Capstone's content:** Sarah wanted the Capstone to be about investing/finance ("something related to money or increasing money somehow"), and specifically wants to connect it to a **real brokerage and trade a real $10** for fun, not just build something purely educational. The rest of this document is the concrete plan that resulted from that conversation.

## Domain

A multi-agent investment analysis assistant, grounded in real content: the `2.0 MMAI 823 Modern Portfolio Theory.pptx` deck (63 slides + speaker notes; covers rate of return, utility/risk aversion, Capital Allocation Line, Sharpe ratio, CAPM, Single Index Model, Fama-French factor models). **The system's actual knowledge base is a permanently scoped subset of this deck** — slides 3–6 (rate of return) and 26–48 (capital allocation / optimal portfolio construction) only, not CAPM/Single Index Model/Fama-French — see `DECISIONS.md`'s "Concepts specialist knowledge base" entry for why, and `012_app/agent_service/data/mpt_deck_content.json` for the extracted, structured corpus (text + speaker notes + written descriptions of each slide's charts/diagrams, since much of the deck's real content is visual).

**Why this domain, over reusing the midterm's book-companion theme or picking something generic:** Sarah wants something "related to investing... something related to money or increasing money somehow" — chosen over a generic professional demo (e.g. a DevOps assistant) specifically because it's grounded in her own real coursework and gives real financial teeth (actual portfolio math, actual market data, actual small real-money trades) rather than being purely educational Q&A.

**Real-money component, and the safety reasoning behind it:** Sarah wants to "play with $10 for fun" by connecting to a live brokerage. Wealthsimple has no official public trading API — unofficial community libraries exist but require handing real login/2FA credentials to unvetted third-party code and violate Wealthsimple's Terms of Service (real risk of account suspension). **Questrade was chosen instead** (her decision, from a 3-way choice against Alpaca and "paper trading only, decide later") — it has an official public API explicitly built for third-party apps, and offers a **free practice/demo account** (separate practice login, fake money, identical API) that lets the whole system be built and proven safe before any real money is involved.

## Agent graph

Uses the **Subagents pattern** (005), not Router or Handoffs — deliberately chosen to recreate the midterm's "main agent doesn't automatically see specialist internals, state has to be deliberately propagated up" experience Sarah specifically asked to have recreated here (see Roadmap.md's 012 addendum, added 2026-07-23).

```
main_portfolio_agent
 ├─ consult_concepts_specialist(question)      → RAG over MPT deck (Chroma), with real advanced-retrieval depth:
                                                    - MultiQueryRetriever (compound questions spanning multiple concepts)
                                                    - SelfQueryRetriever (real section/topic metadata as filters)
                                                    - re-ranking (adjacent concepts close in embedding space, e.g. CAL vs. Optimal Risky Portfolio vs. Optimal CAL and the Optimal Risky Portfolio)
 ├─ consult_portfolio_analyst(tickers, weights) → real math: expected return, σ, Sharpe ratio, optimal allocation
 └─ consult_market_trading_specialist(request) → Subagent whose OWN tools come from the Questrade MCP server:
                                                    - get_quote (unguarded)
                                                    - get_positions (unguarded)
                                                    - place_order (requires approval — both layers, see below)
```

**Why the Concepts specialist gets real retrieval depth, not naive single-query search:** RAG is one of the highest-frequency, most consistently interviewed-about skills for the LLM Application Engineer role, so it's worth doing well here — but each technique above is chosen because the MPT deck's actual content justifies it, not to demonstrate techniques for their own sake (unjustified complexity reads as not knowing when to stop, a bad interview signal in itself). See `DECISIONS.md` for the full reasoning per technique.

The `consult_market_trading_specialist` branch is the required nested-agent-layers exercise: `main_portfolio_agent → consult_market_trading_specialist → MCP tool call → Questrade's own API execution`. The eval suite (007-style) must inspect something that only exists at that innermost layer — specifically, confirming the live Questrade price actually flowed into a downstream Portfolio Analyst calculation, not just that the quote call succeeded.

**Two-layer approval for `place_order`, a genuine payoff of 011 §7's distinction:** `HumanInTheLoopMiddleware` at the LangGraph level (protects against *this agent* acting without review) **and** the MCP server's own consent step (protects against the tool itself being called by any client, regardless of trust) — both must independently block an unapproved trade, tested for real rather than left hypothetical the way 011 left it.

## File layout

**Its own standalone git repo**, initialized at `Projects/012_capstone_portfolio_insight_assistant/` (decided 2026-08-04, see `DECISIONS.md`) — separate from both the curriculum repo (`Phase 2/03_Anthropic_Notes/`) and the rest of the ungoverned `2026_Upskill/` folder. `PLAN.md` and `DECISIONS.md` already live here; the notebook and app code below join them in the same repo, not inside `Phase 2/03_Anthropic_Notes/` as originally sketched.

Internally, still mirrors 010/011's own app-layout conventions. **Two separate deployable services, not one** — decided so the MCP server is genuinely reachable independently of the agent calling it (011 §1's actual N+M argument), rather than reducing MCP to an implementation detail bundled inside the agent's own container:

```
012_capstone_portfolio_insight_assistant/   (own git repo)
  PLAN.md
  DECISIONS.md
  .env                         # gitignored — Questrade refresh token, etc.
  012_capstone.ipynb
  012_app/
    mcp_server/
      questrade_mcp_server.py   # FastMCP server, HTTP transport: get_quote, get_positions, place_order
      Dockerfile                # its OWN image/deploy, separate from the agent
      requirements.txt
    agent_service/
      fastapi_app.py            # wraps main_portfolio_agent, exposes /chat; connects to the MCP server over HTTP via MultiServerMCPClient
      Dockerfile
      requirements.txt
      gradio_frontend.py        # calls the FastAPI backend over HTTP — 009's deferred frontend/backend split, finally built for real
```

## Build order

Split into two checkpoints (Sarah's call, deferred to "whatever's best from a hiring-manager perspective" — recommended because shipping a thin deployed slice first de-risks the deploy step before investing in the full system, and gives two demonstrable milestones instead of one all-or-nothing push).

### 012a — build the multi-agent system locally, top-down, with one early isolated deploy proof (Questrade practice account only, no real money)

Internal order revised 2026-08-03 (see `DECISIONS.md`, "012a internal build order"): deploy the MCP server alone, in isolation, early — to prove the Docker/Render mechanic works before investing time in the rest — then build all three specialists and `main_portfolio_agent` top-down and iterate locally. The agent service itself deploys once, at the start of 012b, once the full local system works — not as a thin slice deployed twice.

1. Sign up for the Questrade practice/demo account, generate the manual refresh token from the App Hub
2. Build `questrade_mcp_server.py` with just `get_quote` first — same STDIO-then-HTTP progression 011 used — prove it works locally against the practice API
3. Add a `/health` endpoint to the MCP server (returns something like `{"status": "ok"}`, no real logic exercised), then Dockerize and deploy it **as its own service** to **Render** (recommended: connects directly to the GitHub repo, auto-builds the Dockerfile, free tier, no new CLI tool needed for a first cloud deploy — final choice still open if Sarah wants to compare against Fly.io/Railway/Cloud Run) — this is the early, isolated deploy-risk proof: no agent wired in yet, just confirming the MCP server itself runs live on Render
4. Build `consult_market_trading_specialist` locally, wired to the MCP server via `MultiServerMCPClient` (can point at either the local process or the now-deployed Render URL); confirm it can answer a real "what's AAPL trading at right now" question over HTTP
5. Build `consult_concepts_specialist` (RAG over the MPT deck) and `consult_portfolio_analyst` (real portfolio math) as standalone local components, same as the market trading specialist
6. Wrap all three specialists as tools and build `main_portfolio_agent` (Subagents pattern) on top, iterating locally until the full multi-agent system behaves correctly end-to-end against the practice account. **For each specialist (and the main agent), deliberately decide and justify the system prompt** as part of this step — not just default to something reasonable-sounding: does the Portfolio Analyst need a few-shot worked example to anchor its calculation format, or is zero-shot with clear instructions enough; how tightly should each specialist's prompt scope its role (e.g. explicitly telling the Concepts specialist to only answer from retrieved context, not speculate); does the financial-disclaimer guardrail also belong partly in the main agent's system prompt as a first line of defense, not just as a post-hoc check. Log the actual choices in `DECISIONS.md`.

### 012b — deploy the full agent service, then flip to live money

7. Wrap `main_portfolio_agent` in FastAPI (`fastapi_app.py`), add the same kind of `/health` endpoint, then Dockerize and deploy it **as a second, separate Render service**, pointed at the already-deployed MCP server's public URL. Confirm the deployed agent service answers the same quote question (and the other specialists' questions) by calling out to the deployed MCP service over the network — two real deployed services talking to each other, not two local processes. Note the refresh-token rotation behavior (single-use, expires in 3 days — see the 012a kickoff conversation) means the token value in Render's env config has to be whatever it last rotated to, not the original signup value — resolve this as part of this step, not an afterthought.
8. Add `place_order` to the MCP server with the two-layer approval gate described above; test that both layers independently block an unapproved trade
9. Guardrails: reuse PII + jailbreak checks from 008, add a **new, domain-specific financial-disclaimer guardrail** — flags/appends "not financial advice" framing on recommendation-shaped outputs (a genuinely new guardrail type, not just a repeat of 008's two)
10. Observability, two distinct layers (see `DECISIONS.md`): **structured application logging** in both services (so `docker logs`/Render's log dashboard show meaningful events — requests received, errors, key state transitions — not silence) for the infra-level "is this thing alive and doing what I expect" question, plus **LangSmith tracing** (008-style, ground-up) for the "what did the agent actually decide and why" question. Combined with the eval suite (007-style): retrieval metrics on the Concepts specialist; **ground-truth assertion checks, not LLM-as-judge**, on the Portfolio Analyst's math (correctness here is deterministic/computable, so a judge model is the wrong tool); the required check confirming the live Questrade price reached a downstream calculation. A real trace showing `main_portfolio_agent → consult_market_trading_specialist → MCP tool call → Questrade's response` is the concrete artifact for the nested-agent-layers exercise — something to actually pull up and walk through, not just describe.
11. Secrets: Questrade refresh token (MCP service) + Anthropic API key (agent service) via `.env`/`python-dotenv` locally, passed as environment variables to each respective deployed service — never baked into either image (010's lesson, reused directly)
12. Only once 1–11 are solid and reviewed: point the deployed MCP service at the **live** Questrade account, fund it with the real $10, and place one real, human-approved trade through the deployed system

## Open decisions not yet locked in

- Exact eval-set design for the Portfolio Analyst's ground-truth math checks
- Whether the Gradio frontend gets its own deploy target or stays local-only for the demo

## Notes queued for `012_capstone.ipynb`

Lessons/concepts that came up *while building* the capstone and are genuinely new (or newly-deepened) material — belongs in the capstone notebook's own write-up once it exists, not retroactively injected into already-completed notebooks 010/011. Running list, add to it as more come up:

- **FastMCP `@mcp.custom_route`**: plain HTTP routes (like `/health`) living alongside `@mcp.tool()`-decorated MCP tools in the same server — and that curl/a browser can hit `custom_route`s directly since they don't go through the MCP protocol, unlike tools. (Surfaced building `questrade_mcp_server.py`'s `/health` endpoint.)
- **`asyncio.run()` can't be called from inside an already-running event loop.** Concretely: a sync-wrapped async function (`def main(): return asyncio.run(get_agent())`) is safe to call from plain sync code, but not from inside another async context that's already running inside its own `asyncio.run(...)` — that needs a direct `await` on the raw async function instead, skipping `asyncio.run()` entirely. (Surfaced wiring `consult_market_trading_specialist_agent` as an async tool inside `main_portfolio_agent.py`, since it has to reach down to the async-only `get_quote` MCP tool.)
- **Considerations when actually writing a system prompt** (surfaced reviewing all four agents' prompts in `main_portfolio_agent.py`/step 6): (1) explicitly guard against the model answering from its own training knowledge instead of its tool — especially important for anything time-sensitive/"live" (a stock price) where the model can be confidently wrong, less important for something like pure math where there's nothing to "know" without the tool; (2) that guard needs to cover *two* separate moments, not one — before calling the tool (missing inputs, so don't guess plausible-sounding values) and after calling it (if the tool's result still doesn't answer the question, don't speculate to fill the gap); (3) few-shot vs. zero-shot depends on how variable/free-form the expected output format is; (4) a guardrail (e.g. a financial disclaimer) can live at more than one layer — the specialist's own prompt, the orchestrating agent's prompt, or both as layered defense — worth deciding deliberately rather than picking one by default.

## Status

As of 2026-08-06, 012a steps 1–2 are done, and step 3 is nearly done:

- **Step 1** (Questrade practice account + refresh token) — done.
- **Step 2** (`get_quote` built and proven locally) — done: OAuth token exchange with rotation/persistence handled, symbol lookup + quote fetch working, wrapped as an `@mcp.tool()`, confirmed working over both stdio and http transports locally.
- **Step 3** (`/health` + Dockerize + deploy to Render) — **done.** `/health` working (`@mcp.custom_route`), Dockerized (including the `host="0.0.0.0"` binding fix and port-mapping gotchas), refresh-token persistence solved with in-memory access-token caching (see `DECISIONS.md`), pushed to GitHub (`github.com/Femicalengineer/portfolio-insight-assistant`), and deployed live on Render — `/health` and `get_quote` both confirmed working against the actual deployed public URL, not just locally. This is the 012a isolated deploy-risk proof, fully closed out.

- **Step 4** (`consult_market_trading_specialist`, wired to the deployed MCP server) — done. Built in `012_app/agent_service/consult_market_trading_specialist.py` using `MultiServerMCPClient` (http transport, pointed at the live Render URL) to load `get_quote` as a real tool, then `create_agent` on top — matching 005's `hr_agent` shape (the specialist is only ever invoked through a test script or, later, a tool wrapper, never inside its own definition file). Confirmed working end-to-end: asked "what is the price of AAPL stock?", the agent correctly chose to call `get_quote`, reached the deployed server, and answered with a real price.

- **Step 5** (`consult_concepts_specialist` + `consult_portfolio_analyst`) — **both done, step 5 complete.**
  - `consult_portfolio_analyst`: built in `012_app/agent_service/consult_portfolio_analyst.py` as a local `@tool` (`analyze_portfolio`, with a Pydantic `ArgsSchema` giving the model per-field descriptions — no MCP server involved, unlike the market trading specialist) wrapped in a `create_agent` specialist, same `hr_agent`-shaped pattern as `consult_market_trading_specialist`. Takes each asset's expected return/volatility/correlation (given/assumed inputs, not fetched — see `DECISIONS.md`) and computes the tangency (Sharpe-maximizing) portfolio weights, that portfolio's own expected return/volatility/Sharpe ratio, and the optimal risky-vs-risk-free split given a risk aversion input. Confirmed working end-to-end, numbers hand-verified correct.
  - `consult_concepts_specialist`: built in `012_app/agent_service/consult_concepts_specialist.py`. Full advanced-retrieval pipeline per `DECISIONS.md` — `SelfQueryRetriever` (real `slide`/`section` metadata filtering) wrapped by `MultiQueryRetriever` (query expansion), then cross-encoder re-ranking, all over the MPT deck corpus embedded in Chroma (`012_app/agent_service/build_concepts_vectorstore.py`, `012_app/agent_service/data/mpt_deck_content.json`, scoped to slides 3–6 and 26–48). Wrapped as a `@tool(response_format='content_and_artifact')` and a `create_agent` specialist, same shape as the other two. Confirmed working end-to-end — real debugging along the way is captured in `RUNBOOK.md` (a genuine `MultiQueryRetriever` default-prompt bug, an `AttributeInfo` type-enforcement limitation, and the retriever `.invoke()` interface).

- **Step 6** (`main_portfolio_agent`) — **done. 012a fully complete.** Built in `012_app/agent_service/main_portfolio_agent.py` using the Subagents pattern: each specialist wrapped in a small `@tool` function that invokes it and returns just its answer (`consult_hr_agent`'s shape from 005), so `main_portfolio_agent` never sees a specialist's internal state directly. All four system prompts (three specialists + main agent) deliberately reviewed and decided, not left as whatever was quick to write — see `DECISIONS.md` for the reasoning behind each (speculation guardrails for market trading and portfolio analyst, confirming the concepts specialist's existing scoping was already sufficient, and deferring financial-disclaimer language to step 9 rather than deciding it piecemeal). Real async/sync plumbing issue hit and fixed along the way: `consult_market_trading_specialist_agent` has to be an async tool reaching down to the async-only `get_quote`, which means `main_agent` itself has to be invoked via `asyncio.run(main_agent.ainvoke(...))`, not plain `.invoke()` — captured in `RUNBOOK.md` and queued for the capstone notebook in the section above. **Confirmed working end-to-end**, single combined question exercising all three specialists at once (live AAPL price, correct hand-verified portfolio optimization math, RAG-sourced Sharpe ratio explanation) — genuinely closes out the nested-agent-layers exercise this Capstone was built around.

Full practical detail on everything done so far is in `RUNBOOK.md`.
