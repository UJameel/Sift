import os
from dotenv import load_dotenv

load_dotenv()

# Ghost (ghost.build) — Postgres built for agents with instant forking
# Use GHOST_DATABASE_URL if provided, fall back to DATABASE_URL
DATABASE_URL = os.environ.get("GHOST_DATABASE_URL") or os.environ.get("DATABASE_URL", "postgresql://localhost/sift")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
BLAND_API_KEY = os.environ.get("BLAND_API_KEY", "")
BLAND_PERSONA_ID = os.environ.get("BLAND_PERSONA_ID", "")
BLAND_PATHWAY_ID = os.environ.get("BLAND_PATHWAY_ID", "")
BLAND_FROM_NUMBER = os.environ.get("BLAND_FROM_NUMBER", "")
OVERMIND_API_KEY = os.environ.get("OVERMIND_API_KEY", "")
ALERT_PHONE_NUMBER = os.environ.get("ALERT_PHONE_NUMBER", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "http://localhost:8000")

ESCALATION_THRESHOLD = float(os.environ.get("ESCALATION_THRESHOLD", "7.0"))

AUTH0_DOMAIN = os.environ.get("AUTH0_DOMAIN", "")
AUTH0_CLIENT_ID = os.environ.get("AUTH0_CLIENT_ID", "")
AUTH0_AUDIENCE = os.environ.get("AUTH0_AUDIENCE", f"https://{os.environ.get('AUTH0_DOMAIN', '')}/api/v2/")
