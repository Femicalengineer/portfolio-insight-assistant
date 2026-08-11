# Portfolio Insight Assistant

A multi-agent investment analysis system built on LangGraph and Claude — combining a real advanced-RAG pipeline, deterministic portfolio math, and a live brokerage integration over MCP. Grounded in real content (a Modern Portfolio Theory coursework deck) and a real Questrade practice account, not a toy demo.

**Live MCP server:** [portfolio-insight-assistant.onrender.com/health](https://portfolio-insight-assistant.onrender.com/health)

---

## What this is

An assistant that can answer three different kinds of investing questions, each handled by a specialist with a genuinely different mechanism underneath:

- **"What's a Sharpe ratio?"** → retrieved and answered from a real course deck via a full advanced-retrieval RAG pipeline
- **"What's the optimal allocation between these two assets?"** → computed with real portfolio-optimization math (tangency portfolio, Sharpe-ratio maximization), not an LLM guessing numbers
- **"What's AAPL trading at right now?"** → a live quote from a real brokerage (Questrade), fetched through a deployed MCP server

A top-level orchestrating agent routes each question to the right specialist — or several, if a question spans more than one — and combines their answers.

```
main_portfolio_agent
 ├─ consult_concepts_specialist      → RAG over an MPT deck (Chroma + SelfQuery + MultiQuery + re-ranking)
 ├─ consult_portfolio_analyst        → real math: expected return, σ, Sharpe ratio, optimal allocation
 └─ consult_market_trading_specialist → Subagent whose own tools come from a deployed MCP server
                                          └─ get_quote → Questrade's live practice-account API
```

## Why this architecture

The `consult_market_trading_specialist` branch is a deliberate **nested-agent-layers exercise**: the main agent calls a specialist, which calls a tool sourced from an independently-deployed MCP server, which calls a real external brokerage API. Each layer's internal state is *not* automatically visible to the layer above it — anything needed has to be explicitly propagated up, the same way it would in a real production multi-service system.

This is a **Subagents** pattern (as opposed to Router, Handoffs, or Skills) — the main agent stays in charge and calls specialists as tools, rather than transferring control to them.

Every non-trivial design decision along the way — why Questrade over other brokerages, why this RAG technique and not a simpler one, why the deployment is two separate services instead of one, why the portfolio math uses given inputs rather than fetched historical data — is written up with real reasoning in [`DECISIONS.md`](DECISIONS.md).

## Architecture: two independently deployed services

```
012_app/
  mcp_server/           # FastMCP server — its own Docker image, its own Render deployment
    questrade_mcp_server.py
  agent_service/        # The multi-agent system itself
    main_portfolio_agent.py
    consult_concepts_specialist.py
    consult_portfolio_analyst.py
    consult_market_trading_specialist.py
    build_concepts_vectorstore.py
    data/mpt_deck_content.json
```

The MCP server and the agent system deploy independently — the point being that an MCP-exposed tool should be genuinely reachable by anything, not just the one agent that happens to call it today.

## Tech stack

- **LangGraph / `create_agent`** for the agent graph
- **Claude** (Haiku 4.5 for specialists, Sonnet 4.5 for the orchestrator)
- **MCP** (FastMCP, HTTP transport) for the live brokerage integration
- **Chroma + HuggingFace embeddings** for the vector store, with `SelfQueryRetriever` (metadata filtering) → `MultiQueryRetriever` (query expansion) → cross-encoder re-ranking layered on top
- **Docker + Render** for deployment
- **Questrade API** (practice/demo account — no real money yet, see status below)

## Status

**Phase 1 (012a) — complete.** MCP server built, Dockerized, and deployed live; all three specialists built and individually verified; the full multi-agent system wired together and confirmed working end-to-end (a single question exercising all three specialists at once, every number hand-verified correct).

**Phase 2 (012b) — in progress.** Remaining: deploying the full agent service (not just the MCP server), a two-layer human-approval gate on trade execution, PII/jailbreak/financial-disclaimer guardrails, LangSmith tracing + a proper eval suite (retrieval metrics, ground-truth math checks), and — only once all of that is solid — flipping from the practice account to a real $10 trade.

Full build log, gotchas, and reasoning for every decision: [`PLAN.md`](PLAN.md) (what/when), [`DECISIONS.md`](DECISIONS.md) (why), [`RUNBOOK.md`](RUNBOOK.md) (how).

## Running it locally

Each service needs its own `.env` (never committed — see `.gitignore`):

```
# mcp_server/
QUESTRADE_REFRESH_TOKEN=...

# agent_service/
ANTHROPIC_API_KEY=...
```

```bash
# MCP server
cd 012_app/mcp_server
pip install -r requirements.txt
python3 questrade_mcp_server.py

# Agent service (in a separate terminal, once the MCP server's running)
cd 012_app/agent_service
python3 main_portfolio_agent.py
```
