# Sift

> Autonomous AI agent that monitors product feedback, learns what matters, and calls you when it's critical.

Built for the **Deep Agents Hackathon — RSAC 2026**.

## What It Does

Founders drown in feedback scattered across GitHub, Slack, reviews, and support tickets. By the time you notice a critical issue, your users are already frustrated.

Sift watches all your channels, learns what matters to **you specifically**, and only calls when it's truly worth your time. It gets smarter after every interaction.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Sift                             │
│                                                                 │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────────────┐  │
│  │ Airbyte  │───▶│   Signals    │───▶│   LLM Analyzer       │  │
│  │ GitHub   │    │   (Ghost DB) │    │   (Overmind traced)  │  │
│  └──────────┘    └──────────────┘    └──────────┬───────────┘  │
│                                                 │ severity > 7 │
│  ┌──────────────────────────────────────┐       ▼              │
│  │           Learning Loop              │  ┌──────────┐        │
│  │  Feedback → Rule → Better Decisions  │  │ Bland AI │        │
│  │  50% accuracy → 80%+ over time       │  │  Voice   │        │
│  └──────────────────────────────────────┘  └──────────┘        │
└─────────────────────────────────────────────────────────────────┘
```

## Sponsor Integrations

| Sponsor | Integration |
|---------|-------------|
| **Airbyte Agent Connectors** | `airbyte-agent-github` GraphQL connector — ingests issues, PRs, commits from 21+ sources |
| **Ghost** | Live Ghost DB provisioned via `ghost create --name sift`. Fork pattern in `ghost.py` enables isolated "what-if" simulations without touching production data |
| **Bland AI + Norm** | Norm-built pathway calls founder when severity ≥ 7. Captures verbal response, feeds back into learning loop. Inbound fallback at +14153601802 |
| **Overmind** | `overmind.init(providers=["openai"])` at startup — every GPT-4o/4o-mini call auto-traced, latency + quality visible in Overmind dashboard |
| **Auth0** | JWT middleware on `/agent/scan` and `/agent/ingest` — verifies RS256 tokens against Auth0 JWKS |

## Setup

### Prerequisites

- Python 3.11+
- PostgreSQL (Ghost or local)
- API keys: Anthropic, Bland AI, GitHub PAT

### Install

```bash
git clone <repo>
cd sift

# Create virtualenv
python -m venv venv
source venv/bin/activate

pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

### Database

Option A — Ghost (recommended, ghost.build):
```bash
curl -fsSL https://install.ghost.build | sh
ghost login
ghost create --name sift --wait --json
# Copy the connection string into GHOST_DATABASE_URL in .env
```

Option B — Local Postgres:
```bash
createdb sift
# Set DATABASE_URL=postgresql://localhost/sift in .env
```

> `GHOST_DATABASE_URL` takes priority over `DATABASE_URL` when both are set.

### Run

```bash
uvicorn backend.main:app --reload
```

Open dashboard: http://localhost:8000

## Demo Flow

1. **Open dashboard** at http://localhost:8000
2. Click **"▶ Run Scan"** — agent analyzes all 10 seeded signals
3. Watch the agent log: escalated vs ignored vs queued
4. **Submit feedback** on decisions using the ✓/✗ buttons — this triggers the learning loop
5. Watch **accuracy chart** improve (pre-seeded from 50% → 80%)
6. Click **"+ Inject Signal"** — add a live critical bug
7. Run scan again — agent applies learned rules to new signal

For live voice demo: ensure `BLAND_API_KEY` and `ALERT_PHONE_NUMBER` are set. Severity > 7 signals trigger a call.

## API Reference

```bash
# List signals
curl http://localhost:8000/signals

# Run analysis scan (escalates critical signals + fires Bland AI call)
curl -X POST http://localhost:8000/agent/scan

# Ingest real GitHub issues via Airbyte connector
curl -X POST "http://localhost:8000/agent/ingest?owner=UJameel&repo=Sift"

# Submit feedback (triggers learning loop)
curl -X POST http://localhost:8000/feedback/1 \
  -H "Content-Type: application/json" \
  -d '{"response": "good_call"}'

# Generate a PR fix for a signal (agentic — reads repo, GPT-4o, opens PR)
curl -X POST http://localhost:8000/feedback/1 \
  -H "Content-Type: application/json" \
  -d '{"response": "generate_pr"}'

# Ghost fork simulation — what-if at different threshold (production unchanged)
curl -X POST "http://localhost:8000/agent/simulate?threshold=6.0"

# Reset options
curl -X POST "http://localhost:8000/agent/reset-signals"                          # soft reset
curl -X POST "http://localhost:8000/agent/reset-signals?full=true"                # delete all data
curl -X POST "http://localhost:8000/agent/reset-signals?full=true&clear_rules=true" # full + learned rules

# Check accuracy over time
curl http://localhost:8000/agent/accuracy
```

## Project Structure

```
sift/
├── backend/
│   ├── main.py              # FastAPI app + Overmind init
│   ├── config.py            # Env config (Ghost URL priority)
│   ├── auth.py              # Auth0 JWT middleware
│   ├── models.py            # Pydantic models
│   ├── db.py                # asyncpg pool + schema
│   ├── seed.py              # Demo data seeder
│   ├── routers/
│   │   ├── signals.py       # Signal CRUD
│   │   ├── agent.py         # Scan, ingest, simulate, reset
│   │   ├── feedback.py      # Learning loop trigger + PR generation
│   │   └── webhooks.py      # Bland AI callback
│   └── services/
│       ├── ingestion.py     # Airbyte GitHub connector (GraphQL)
│       ├── analyzer.py      # LLM analysis + Overmind traces
│       ├── bland_caller.py  # Voice alert via Norm pathway
│       ├── ghost.py         # Ghost fork pattern for simulations
│       ├── pr_generator.py  # Agentic PR generation via OpenAI + GitHub
│       ├── action_taker.py  # Create GitHub issues
│       └── learning.py      # Self-improving loop
├── dashboard/
│   └── index.html           # React CDN dashboard
└── skill/
    └── SKILL.md             # shipables.dev skill
```
