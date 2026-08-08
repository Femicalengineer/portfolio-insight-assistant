# Decisions — Portfolio Insight Assistant

Two parts: a general, reusable framework of decision categories any LLM Application Engineer project runs into, and a running log of the actual decisions made for this specific Capstone, with reasoning — kept so Sarah can explain *why* each choice was made in an interview, not just *what* was built.

**How this gets used going forward:** before a nontrivial design/architecture/efficiency decision gets made during the build, it gets discussed here first — options and tradeoffs surfaced, Sarah weighs in, the decision and reasoning get logged. Not just decided and implemented silently. (See memory: `feedback_collaborative_decisions`.)

---

## Part 1 — General decision framework for LLM Application Engineer projects

A checklist of the categories of decisions this kind of project involves, independent of any one project. Roughly ordered from "shapes everything else" to "polish."

### 1. Model & prompting strategy
- Which model / model tier (cost vs. quality vs. latency) — and whether different tasks in the same system justify different tiers
- Prompting technique per task: zero-shot, few-shot, chain-of-thought, ReAct
- System prompt design and scope
- Structured output vs. tool use vs. free text, per task

### 2. Knowledge & retrieval architecture (if RAG is involved)
- Fine-tune vs. RAG vs. prompting — the foundational decision, made per capability, not once for the whole system
- Chunking strategy (size, overlap) and its tradeoff against "lost in the middle"
- Embedding model choice
- Vector store choice
- Single retrieval vs. advanced retrieval (multi-query, self-query, hybrid search + re-ranking) — and whether the added latency/complexity is justified by the query patterns actually expected

### 3. Agent architecture
- Single agent vs. multi-agent — is the task actually separable into specialties, or is this complexity for its own sake?
- If multi-agent: which pattern — Router (classify-then-dispatch), Handoffs (transfer control), Subagents (main agent stays in charge, calls specialists as tools), Skills (no second agent at all), Reflection/Reflexion (critique-revise loop)
- Tool granularity — one broad tool or several narrow ones; what's a `@tool` vs. a `Resource` vs. an MCP-exposed tool
- Local `@tool` vs. MCP server — is this tool only ever used by one agent, or does it need to be reachable by something else?
- State management: what's in short-term (thread/session) memory vs. long-term (cross-thread) store

### 4. Reliability & safety
- Idempotency — can any step run twice safely, and does it need to be?
- Retry/fallback strategy — which failures are worth retrying, which need a fallback model tier, which should just fail loudly
- Guardrails — what's actually sensitive here (PII, prompt injection, domain-specific risks like financial-advice framing), and where in the pipeline should each check live
- Human-in-the-loop — which actions are consequential enough to require approval before executing, and at which layer (the agent's own middleware, the tool/server boundary, or both)
- Secrets/config management — how secrets get loaded locally vs. at deploy time; the hard rule of never baking a secret into a build artifact

### 5. Evaluation
- What actually needs to be measured — retrieval quality, generation quality, task success, safety compliance?
- LLM-as-judge vs. deterministic/ground-truth checks — judge models are for judgment calls, not for anything with a computable right answer
- One-off testing vs. regression testing over time (tracing, datasets, re-running the same eval set as the system changes)

### 6. Cost & latency
- Prompt caching — is there repeated/shared context worth caching?
- Batching vs. real-time — does this need an answer now, or can it be processed later in bulk?
- Streaming — does the user need to see partial output as it's generated?
- Sync vs. async endpoints — is there real I/O wait to not waste, or is this pure computation?

### 7. Deployment & operations
- API framework and service boundary — what's actually exposed as an endpoint, what stays internal
- Containerization — what has to be in the image vs. what's supplied at runtime
- Deploy target — cloud/PaaS choice, and what that choice costs in money, complexity, and control
- Monitoring — what would you actually want to know if this broke in production, and how would you find out

### 8. Testing
- Mocking vs. hitting the real model/API — what needs to be deterministic and fast in CI vs. what needs the real thing
- What's actually worth testing — the glue code and validation logic, not the model's own behavior

---

## Part 2 — Decisions made so far, for this Capstone

Each entry: the decision, the options considered, and the reasoning.

### Domain: Portfolio Insight Assistant, not a generic professional demo
- **Options considered:** new unrelated domain, reuse/extend the midterm's book-companion domain, a generic "professional" demo (e.g. a DevOps/internal-docs assistant), or something investing/finance-related
- **Decision:** investing/finance, grounded in Sarah's real MMAI 823 Modern Portfolio Theory coursework, because she wanted something with real financial teeth ("increasing money somehow") rather than purely educational Q&A
- **Reasoning:** real content already exists (63 slides + notes, extracted and confirmed usable as a RAG knowledge base) and a finance-agent domain naturally supports every architectural piece already planned for the Capstone (specialists, HITL, MCP-sourced live data)

### Real-money integration: Questrade over Wealthsimple or Alpaca
- **Options considered:** Wealthsimple (Sarah's original idea), Alpaca, Questrade, or paper-trading-only with the broker decided later
- **Decision:** Questrade
- **Reasoning:** Wealthsimple has no official public trading API — the only options are unofficial, reverse-engineered libraries that require handing real login/2FA credentials to unvetted third-party code and violate Wealthsimple's own Terms of Service (real account-suspension risk). Questrade has an official API explicitly built for third-party apps, plus a free practice/demo account (identical API, fake money) to prove the system safe before any real money is involved. Sarah chose this directly when given the three options.

### Agent architecture: Subagents pattern, not Router or Handoffs
- **Options considered:** Router, Handoffs, Subagents, Skills (all four built and compared in notebook 005)
- **Decision:** Subagents
- **Reasoning:** Sarah specifically asked (while building notebook 010) for the Capstone to recreate the midterm's "main agent doesn't automatically see specialist internals" debugging experience. Subagents is the only one of the four patterns where the main agent stays in charge and calls specialists as tools without their internal state automatically surfacing — the exact shape needed to reproduce that experience, now with an MCP server call as the new outermost boundary instead of another nested `create_agent`.

### Trading tool approval: two independent layers, not one
- **Options considered:** a single approval layer (either just `HumanInTheLoopMiddleware` in the agent graph, or just consent at the MCP server), vs. both layers independently
- **Decision:** both layers, tested independently
- **Reasoning:** notebook 011 (§7) drew a real distinction between the two — `HumanInTheLoopMiddleware` protects against *this specific agent* acting without review, while an MCP server's own consent step protects against the tool being called by *any* client regardless of trust — but left it hypothetical. This Capstone has a real consequential action (placing a trade with real money) where that distinction actually matters, so both get built and both get verified to independently block an unapproved trade.

### Portfolio math evaluation: ground-truth assertions, not LLM-as-judge
- **Options considered:** LLM-as-judge (007's default pattern for generation quality), deterministic assertion checks against known-correct computed values
- **Decision:** ground-truth assertions
- **Reasoning:** correctness of expected return / Sharpe ratio / optimal allocation calculations is objectively computable — there's a single right answer given the inputs. An LLM judge is the right tool for subjective or open-ended quality questions (007's spoiler-leakage check, tone, relevance); it's the wrong tool when a plain equality/tolerance check against a known value is available and more reliable.

### Build order: split into 012a/012b checkpoints
- **Options considered:** one continuous build, vs. a thin deployable slice first (012a) then the full system (012b)
- **Decision:** split
- **Reasoning:** Sarah deferred this to "whatever's best from a hiring-manager perspective." Shipping a thin, actually-deployed slice first de-risks the deploy step (cloud/Docker friction) before investing time in the full multi-agent system, and produces two demonstrable milestones instead of one all-or-nothing push — itself a defensible engineering-practice story for an interview.

### MPT deck content extraction: vision-generated text descriptions for image-heavy slides, not notes-only or full multimodal retrieval
- **Options considered:** (A) extract only slide text + speaker notes, treat that as the full RAG corpus; (B) also generate text descriptions of each slide's images via a vision-capable model at prep time, and fold those descriptions into the same text corpus; (C) full multimodal retrieval — store the actual images, retrieve them alongside text, and have the answering model (vision-capable) reason over the real image at query time
- **Decision:** B
- **Reasoning:** the deck's actual informational content is largely in plots/charts (efficient frontier diagrams, indifference curves, CAL graphs — Sarah's own observation, confirmed by checking: ~30 of 63 slides have an embedded image), so A alone risks silently losing most of the real content — not every slide's notes fully narrate what's in its chart. C is the most complete option but requires genuinely new infrastructure (a different embedding approach entirely, since text embedding models can't handle images — not something 003's vector-database work covered), which is more complexity than this system's actual use case (answering conceptual MPT questions in text) justifies. B is the sweet spot: it's justified (the images carry real content, not complexity for its own sake) and it slots into the exact RAG pipeline already planned (Chroma, text embeddings, MultiQuery/SelfQuery/re-ranking) without new infrastructure — the images just become richer *text* feeding a pipeline that already exists. Practical execution: check notes first (cheap, may already cover plenty), only generate a vision description where notes are thin or the image is clearly carrying information the notes don't capture.

### Portfolio Analyst's data source: given/assumed inputs, not a historical-data pipeline
- **Options considered:** (A) fetch real historical price data (would require a new Questrade MCP tool — none of the planned tools, `get_quote`/`get_positions`/`place_order`, provide historical series) and compute empirical expected returns/volatility/covariance from it; (B) take expected-return and volatility as given/assumed inputs, matching how MPT problems are typically posed in coursework, and focus the tool on the optimization math itself
- **Decision:** B
- **Reasoning:** naive historical-mean returns are a well-known weak predictor of future returns (dominated by estimation noise) — this is exactly why practitioners don't trust raw historical-mean-based Markowitz optimization, and likely part of why the MPT coursework this Capstone is grounded in covers CAPM/Fama-French at all. So "real" historical data wouldn't actually make the tool more reliable or more interview-credible than assumed inputs — it would just add a large, mostly separate scope (sourcing and validating historical market data via a new Questrade tool) without improving what's actually being tested. The eval design already committed to in this doc (ground-truth assertions on math correctness given inputs) doesn't need real market data to be meaningful. Keeps the specialist focused on demonstrating the optimization math correctly, which is the actual interview-relevant skill here.

### Refresh-token persistence for the deployed MCP server: in-memory access-token caching, defer external persistence
- **Options considered:** (A) leave `get_access_token` re-exchanging the refresh token on every single call, and have it call Render's own API to persist the rotated token back as an env var; (B) cache the access token in memory (it's valid 30 minutes) so the refresh token only actually rotates roughly once per 30 minutes of activity instead of on every call, and accept that a full container restart (Render free tier sleeps idle services) needs a manually-refreshed token — a documented limitation, not silently broken; (C) B, plus add external persistent storage (e.g. a small hosted key-value store) so the token survives restarts too
- **Decision:** B
- **Reasoning:** A turned out to be a dead end — Render's env-var-update API doesn't take effect live, it requires triggering a full redeploy, which would restart the container mid-request and need yet another secret (a Render API key) just to manage this one. B is a real, independent efficiency fix (there's no reason to burn a single-use refresh token on every call when the access token it produces is valid for 30 minutes) and shrinks how often the persistence problem even arises. C was considered but skipped for now — added infrastructure and cost for a portfolio/interview project that doesn't have high-traffic production requirements; the documented restart limitation from B is an honest, explainable tradeoff rather than unjustified complexity for its own sake. Revisit if this actually becomes a practical problem once deployed.
- **Earlier note this replaces:** originally this was scoped narrower — just "don't crash when no `.env` exists inside a container" (skip persistence gracefully) — which is still true and still in the code, but B above is the fuller fix for the deployed-service version of the same problem.

### Repo structure: Capstone gets its own standalone git repo, not nested in the curriculum repo
- **Options considered:** (A) inside `Phase 2/03_Anthropic_Notes/` alongside `012_capstone.ipynb`, mirroring how 010/011's app code lives in that same repo; (B) its own standalone repo, separate from both the curriculum repo and the rest of the ungoverned `2026_Upskill/` folder
- **Decision:** B — initialized at `Projects/012_capstone_portfolio_insight_assistant/` (2026-08-04)
- **Reasoning:** Sarah's direct instruction, given while we were creating the local `.env` for the Questrade refresh token. Not further explained beyond preference; a real side benefit is a clean deploy/version-control boundary — Render's GitHub-repo auto-deploy connects to one repo at a time, so a dedicated repo avoids entangling the Capstone's commit history and CI/deploy triggers with the rest of the curriculum's. Worth confirming the full reasoning (e.g. wanting a standalone piece to link directly in job applications) if it comes up again.

### 012a internal build order: top-down local build with one early isolated deploy proof, not a deploy-first slice-by-specialist
- **Options considered:** (A) the original plan — build and deploy the market trading specialist end-to-end (both services live on Render) before touching the other two specialists, which only get added in 012b; (B) fully top-down — build all three specialists locally, wrap them as tools, build `main_portfolio_agent` on top, iterate until the whole local system works, then deploy the agent service exactly once at the end; (C) a middle ground — deploy the MCP server alone, in isolation, very early (no agent wired in yet) to prove the Docker/Render mechanic works, then build all three specialists and `main_portfolio_agent` top-down locally, deploying the agent service once at the end
- **Decision:** C
- **Reasoning:** Sarah's instinct was that building each specialist, wrapping them into `main_portfolio_agent`, and iterating top-down is the more natural engineering flow — and it avoids the redeploy churn of pushing the agent service twice (once thin, once full). Pure top-down (B) was rejected because it fully defers deploy risk to the very end, undercutting the original reason for splitting into 012a/012b checkpoints at all (de-risking Sarah's first-ever cloud deploy before sinking time into the full system). Option C keeps that early signal on the newest/riskiest piece — Docker + Render, proven with just the MCP server in isolation — while letting the actual multi-agent build happen in the top-down order Sarah described, with only one deploy of the agent service, at the end of 012a/start of 012b.

### MCP server deployment shape: separate container, HTTP transport
- **Options considered:** (A) `questrade_mcp_server.py` as its own Docker container/deploy, HTTP transport, reachable over the network — same shape as 011's `app5_weather_server.py`; (B) bundled into the FastAPI container, STDIO transport, launched as a subprocess by the agent — same shape as 011's `app5_math_server.py`
- **Decision:** Option A — separate container, HTTP transport
- **Reasoning:** the whole point of using MCP at all (011 §1's N+M argument) is that a tool should be reachable independently of the one agent calling it. Bundling the server into the same container as the FastAPI app (Option B) would technically work but reduces the MCP server to an implementation detail of one service, undercutting the actual demonstration. The cost is real — two services to deploy and manage instead of one — but it's the more honest architecture for what's actually being shown.

### Concepts specialist RAG: real advanced-retrieval depth, not naive single-query similarity search
- **Options considered:** plain single-query similarity search (simplest, lowest effort) vs. applying 006's advanced retrieval techniques (MultiQueryRetriever, SelfQueryRetriever, re-ranking) where each is actually justified by the content, vs. adding complexity indiscriminately just to show more techniques
- **Decision:** apply advanced retrieval, but only where genuinely justified by the MPT deck's content — not complexity for its own sake
- **Reasoning:** RAG is one of the highest-frequency, most consistently interviewed-about skills for the LLM Application Engineer role, so this specialist is worth real depth. Specifically: **MultiQueryRetriever** because the deck naturally invites compound questions ("how does risk aversion relate to the Sharpe ratio and diversification?") a single embedding can't represent well; **SelfQueryRetriever** because the deck has real structure (numbered sections/topics) that becomes genuine filterable metadata, not a synthetic field invented just to demo the technique; **re-ranking** because adjacent finance concepts within the corpus (e.g. "CAL," "Optimal Risky Portfolio," and "Optimal CAL and the Optimal Risky Portfolio" — slides 29, 39, 41) can be superficially close in embedding space while differing in what's actually being asked. (Originally justified via "CAPM vs. Single Index Model" — updated 2026-08-07 once that content was scoped out entirely, see the knowledge-base-scope decision below; re-ranking's justification still holds with an in-scope example pair.) Unjustified complexity was explicitly rejected as a design goal — it reads as not knowing when to stop, which is itself a bad interview signal.
- **Also decided alongside this:** the eval suite must include a **real labeled retrieval-quality eval set** (precision@k/recall@k/MRR, 007-style) rather than eyeballing retrieval quality — the deck's clear structure makes a genuine eval set buildable, not hand-waved.

### Concepts specialist knowledge base: permanently scoped to rate-of-return + capital-allocation/optimal-portfolio, not the full deck
- **Options considered:** (A) RAG over the entire 63-slide deck, including CAPM, the Single Index Model, and Fama-French factor models; (B) permanently scope the knowledge base to just the slides directly relevant to what this system's specialists actually do — rate of return (slides 3–6) and capital allocation/optimal portfolio construction (slides 26–48) — excluding CAPM/factor-model content entirely, not just deferring it
- **Decision:** B
- **Reasoning:** CAPM and factor models answer a different question (how to price/estimate returns for individual securities) than what any of this system's specialists actually do (construct/evaluate a portfolio from given inputs — see the Portfolio Analyst's given/assumed-inputs decision above, which specifically does *not* use CAPM-estimated returns). No other part of the system touches that content, and a user of a portfolio-construction assistant is far more likely to ask about Sharpe ratio, diversification, or the Capital Allocation Line than about Fama-French. Including it anyway would be exactly the unjustified-breadth-for-its-own-sake this project has consistently avoided elsewhere. Also discovered while extracting deck content for the Portfolio Analyst: slide 36 (the deck's own internal page number; "Optimal Risky Portfolio with Two Risky Assets" in the pptx's slide order) contains a real worked example with concrete numbers (Debt: 8% return/12% σ; Equity: 13% return/20% σ; covariance 0.0072; correlation 0.30; risk-free rate 5%) — directly usable as realistic given/assumed input data for the Portfolio Analyst, reinforcing that this in-scope range is where the actually-useful content lives.

### Observability: include LangSmith tracing, not just the eval suite
- **Options considered:** eval suite only (007-style retrieval metrics + ground-truth checks, no tracing layer), vs. eval suite plus full LangSmith tracing (008's ground-up treatment)
- **Decision:** include LangSmith tracing, as a required piece of 012b alongside the eval suite
- **Reasoning:** 008 made tracing a core practice specifically because it shows *what a system actually did*, not just whether the final answer was right — and that maps unusually well onto this Capstone's required nested-agent-layers exercise. A real trace showing `main_portfolio_agent → consult_market_trading_specialist → MCP tool call → Questrade's response` is something Sarah can pull up and walk through directly in an interview, more concrete than describing the architecture verbally. Cost: one more account/API key to wire in via `.env` (008's pattern), and it's an observability layer rather than a functional dependency — but the payoff for interview-readiness specifically was judged worth it.

### Observability, part 2: container/infra-level monitoring, distinct from LangSmith
- **Options considered:** LangSmith tracing alone (covers the LLM/agent-decision layer only) vs. also adding container/infra-level observability (is the service alive, what is it logging)
- **Decision:** add both — a `/health` endpoint on each deployed service (FastAPI agent service and the MCP server), plus structured application logging, in addition to LangSmith
- **Reasoning:** LangSmith answers "what did the agent decide and why" but has no concept of whether the container itself is healthy or running — that's a genuinely different question, and the original Capstone scope (Roadmap.md) already called for "light production monitoring" without making it concrete. A `/health` endpoint is the standard way any platform (Render included) or a human checks liveness without exercising real logic. Structured logging means `docker logs`/Render's log dashboard actually show meaningful events (requests received, errors, key state transitions) instead of silence. This is genuinely new territory not covered by any existing notebook — will need a ground-up explanation (what a health-check endpoint is *for*, what "structured logging" means vs. plain `print()`) when 012b actually gets built, per the established habit of explaining new tools before showing their code.

### Deployment platform: Render (confirmed final)
- **Options considered:** Render, Fly.io, Railway, Google Cloud Run
- **Decision:** Render
- **Reasoning:** connects directly to a GitHub repo and auto-builds from the existing Dockerfile, free tier available, no new CLI tool required for Sarah's first-ever cloud deploy. Confirmed 2026-08-06 — the MCP server (`questrade_mcp_server.py`) is live at `https://portfolio-insight-assistant.onrender.com`, `/health` and `get_quote` both proven working against the real deployed URL. One real config gotcha worth remembering (see `RUNBOOK.md`): Render's "Root Directory" and "Dockerfile Path" fields both needed setting to `012_app/mcp_server` (and `012_app/mcp_server/Dockerfile` respectively) since the Dockerfile isn't at the repo root — a monorepo-style layout, not the single-service default Render's UI assumes.

---

## Open, not yet decided

- Final deployment platform
- Exact eval-set design for the Portfolio Analyst's ground-truth math checks
- Chunking strategy for the MPT deck's RAG knowledge base
- Whether the Gradio frontend gets its own deploy target or stays local-only
- Financial-disclaimer guardrail — exact trigger condition and wording
