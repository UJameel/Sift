---
name: sift
description: "Autonomous product feedback monitoring agent. Ingests signals from GitHub, reviews, Slack. Learns what matters to you. Calls you when it's critical. Gets smarter with every interaction."
---
# Sift

An autonomous, self-improving AI agent that monitors what people are saying about your product across multiple channels and only bothers you when it truly matters.

## How It Works

1. **Ingest**: Pulls signals from GitHub issues, app reviews, Slack, support tickets (via Airbyte connectors)
2. **Analyse**: LLM scores severity (0-10), classifies type, decides whether to escalate
3. **Act**: Calls you via Bland AI with a briefing, captures your verbal response
4. **Learn**: Stores your feedback, generates rules, improves accuracy over time
5. **Repeat**: Every cycle makes the agent smarter at knowing what matters to YOU

## The Self-Improving Loop

The key differentiator: after each voice call, the founder's response (approve/dismiss/create issue) is stored as feedback. An LLM then generates a new heuristic rule:

> "GitHub issues mentioning 'data loss' from production repos should always be escalated"
> "Feature requests from new contributors are low priority regardless of tone"

These rules are injected into every future analysis prompt. The agent literally gets smarter with every interaction.

## Sponsor Tools Used

- **Airbyte Agent Connectors** — data ingestion from GitHub (21+ sources available)
- **Ghost** — Postgres database for agent memory, signals, and learned rules
- **Bland AI + Norm** — voice alerts when severity > 7, captures founder's verbal response
- **Overmind** — traces every LLM decision, evaluates quality, continuous optimization
- **Auth0** — secure dashboard access (React SPA)

## Setup

```bash
pip install -r requirements.txt

# Set up Ghost DB (or use local Postgres)
ghost db create sift

# Configure environment
cp .env.example .env
# Fill in: DATABASE_URL, GITHUB_TOKEN, BLAND_API_KEY, ANTHROPIC_API_KEY, ALERT_PHONE_NUMBER

# Run
cd sift
uvicorn backend.main:app --reload

# Open dashboard
open http://localhost:8000
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /signals | List all ingested signals |
| POST | /signals | Create signal manually |
| POST | /agent/scan | Run full analysis loop |
| POST | /agent/ingest | Pull fresh GitHub issues |
| GET | /agent/accuracy | Accuracy time series |
| GET | /agent/learned-rules | Current learned heuristics |
| POST | /feedback/{id} | Submit founder feedback |
| POST | /webhooks/bland-complete | Bland AI call callback |

## Architecture

```
Airbyte GitHub → signals table → LLM Analyzer (Overmind traced)
                                    ↓ severity > 7?
                              Bland AI Voice Call
                                    ↓ founder response
                              Learning Service
                                    ↓ generate rule
                              learned_rules table
                                    ↓ fed back into next analysis
                              Improved accuracy
```
