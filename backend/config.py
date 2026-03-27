import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost/sift")
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
