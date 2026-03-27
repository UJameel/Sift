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
| **Airbyte Agent Connectors** | GitHub issue ingestion via strongly-typed Python SDK |
| **Ghost** | Postgres database for all agent memory and learned rules |
| **Bland AI + Norm** | Voice calls when severity > 7, captures verbal response |
| **Overmind** | Every LLM call is traced, evaluated, and optimized |
| **Auth0** | Dashboard authentication (React SPA) |

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

Option A — Ghost (recommended):
```bash
curl -fsSL https://install.ghost.build | sh
ghost db create sift
# Copy DATABASE_URL from Ghost output to .env
```

Option B — Local Postgres:
```bash
createdb sift
# Set DATABASE_URL=postgresql://localhost/sift in .env
```

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

# Run analysis scan
curl -X POST http://localhost:8000/agent/scan

# Submit feedback (triggers learning)
curl -X POST http://localhost:8000/feedback/1 \
  -H "Content-Type: application/json" \
  -d '{"response": "good_call"}'

# Check accuracy over time
curl http://localhost:8000/agent/accuracy

# Pull from GitHub
curl -X POST "http://localhost:8000/agent/ingest?owner=fastapi&repo=fastapi"
```

## Project Structure

```
sift/
├── backend/
│   ├── main.py              # FastAPI app + lifespan
│   ├── config.py            # Env config
│   ├── models.py            # Pydantic models
│   ├── db.py                # asyncpg pool + schema
│   ├── seed.py              # Demo data seeder
│   ├── routers/
│   │   ├── signals.py       # Signal CRUD
│   │   ├── agent.py         # Scan, ingest, accuracy
│   │   ├── feedback.py      # Learning loop trigger
│   │   └── webhooks.py      # Bland AI callback
│   └── services/
│       ├── ingestion.py     # Airbyte GitHub connector
│       ├── analyzer.py      # LLM analysis + Overmind
│       ├── bland_caller.py  # Voice alert service
│       ├── action_taker.py  # Create GitHub issues
│       └── learning.py      # Self-improving loop
├── dashboard/
│   └── index.html           # React CDN dashboard
└── skill/
    └── SKILL.md             # shipables.dev skill
```
