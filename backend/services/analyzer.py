"""LLM analyzer — scores signals, classifies them, decides escalation. Traced by Overmind."""
import json
import httpx
from contextlib import contextmanager
from datetime import datetime

try:
    import overmind
    _OVERMIND_AVAILABLE = True
except ImportError:
    _OVERMIND_AVAILABLE = False


@contextmanager
def _trace(name, **kwargs):
    """Overmind trace wrapper — no-op if not initialized."""
    if _OVERMIND_AVAILABLE:
        try:
            with overmind.trace(name, **kwargs):
                yield
            return
        except Exception:
            pass
    yield

from backend import db
from backend.config import OPENAI_API_KEY, ESCALATION_THRESHOLD


SYSTEM_PROMPT = """You are Sift's analysis engine. Your job is to evaluate product feedback signals and determine:
1. How severe/urgent this issue is (0-10 scale)
2. What category it falls into
3. Whether to escalate (call the founder)
4. Your reasoning

Be precise and conservative with escalations — false alarms erode trust.
Severity guide:
- 9-10: Data loss, security vulnerabilities, complete outages affecting many users
- 7-8: Significant bugs affecting multiple users, revenue at risk, performance degradation
- 5-6: Feature requests with real user pain, minor bugs with workarounds
- 3-4: Nice-to-haves, low-impact feature requests
- 1-2: Praise, minor typos, cosmetic issues

Always respond with valid JSON only."""


async def analyze_signal(signal_row: dict) -> dict:
    """Analyze a single signal. Returns decision dict."""
    learned_rules = await _get_learned_rules()
    rules_context = _format_rules(learned_rules)

    prompt = f"""Analyze this product feedback signal:

Source: {signal_row['source']}
Title: {signal_row['title']}
Body: {signal_row['body'][:500]}
Author: {signal_row.get('author', 'unknown')}

{rules_context}

Return JSON with exactly these fields:
{{
  "severity_score": <float 0-10>,
  "category": <"bug"|"feature_request"|"complaint"|"praise"|"security">,
  "should_escalate": <true|false>,
  "action_taken": <"escalated"|"ignored"|"queued">,
  "reasoning": "<1-2 sentences explaining your decision>",
  "confidence": <float 0-1>
}}"""

    with _trace("analyze_signal", metadata={"source": signal_row["source"], "signal_id": signal_row.get("id")}):
        result = await _call_llm(prompt)

    # Parse JSON from LLM response
    try:
        decision_data = json.loads(result)
    except json.JSONDecodeError:
        # Extract JSON from markdown code blocks if present
        import re
        match = re.search(r'\{.*\}', result, re.DOTALL)
        if match:
            decision_data = json.loads(match.group())
        else:
            # Fallback decision
            decision_data = {
                "severity_score": 5.0,
                "category": "bug",
                "should_escalate": False,
                "action_taken": "queued",
                "reasoning": "Analysis failed — defaulting to queue",
                "confidence": 0.3
            }

    # Override action based on threshold
    severity = decision_data.get("severity_score", 0)
    if severity >= ESCALATION_THRESHOLD and decision_data.get("should_escalate"):
        decision_data["action_taken"] = "escalated"
    elif severity < 4:
        decision_data["action_taken"] = "ignored"
    else:
        decision_data["action_taken"] = "queued"

    return decision_data


async def _get_learned_rules() -> list[dict]:
    rows = await db.fetch_all(
        "SELECT rule, confidence FROM learned_rules ORDER BY confidence DESC LIMIT 10"
    )
    return [dict(r) for r in rows]


def _format_rules(rules: list[dict]) -> str:
    if not rules:
        return ""
    lines = ["Learned rules from past feedback (apply these):"]
    for r in rules:
        lines.append(f"- {r['rule']} (confidence: {r['confidence']:.0%})")
    return "\n".join(lines) + "\n"


async def _call_llm(prompt: str) -> str:
    """Call OpenAI API."""
    if not OPENAI_API_KEY:
        return _mock_llm_response(prompt)

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",
                "max_tokens": 512,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=30.0
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


def _mock_llm_response(prompt: str) -> str:
    """Deterministic mock for when no API key is available."""
    text_lower = prompt.lower()
    if any(w in text_lower for w in ["crash", "data loss", "corruption", "security", "sql injection", "vulnerability"]):
        return json.dumps({
            "severity_score": 9.0,
            "category": "security" if "injection" in text_lower or "vulnerability" in text_lower else "bug",
            "should_escalate": True,
            "action_taken": "escalated",
            "reasoning": "Critical issue detected — data integrity or security risk.",
            "confidence": 0.92
        })
    elif any(w in text_lower for w in ["enterprise", "revenue", "churn", "memory leak", "token"]):
        return json.dumps({
            "severity_score": 8.0,
            "category": "bug",
            "should_escalate": True,
            "action_taken": "escalated",
            "reasoning": "High-impact issue affecting multiple enterprise users or revenue.",
            "confidence": 0.85
        })
    elif any(w in text_lower for w in ["feature", "nice to have", "would be nice", "dark mode"]):
        return json.dumps({
            "severity_score": 3.0,
            "category": "feature_request",
            "should_escalate": False,
            "action_taken": "queued",
            "reasoning": "Low-priority feature request, no urgency.",
            "confidence": 0.88
        })
    elif any(w in text_lower for w in ["love", "great", "excellent", "5 star"]):
        return json.dumps({
            "severity_score": 1.0,
            "category": "praise",
            "should_escalate": False,
            "action_taken": "ignored",
            "reasoning": "Positive feedback, no action needed.",
            "confidence": 0.95
        })
    else:
        return json.dumps({
            "severity_score": 5.5,
            "category": "complaint",
            "should_escalate": False,
            "action_taken": "queued",
            "reasoning": "Moderate issue requiring follow-up but not urgent.",
            "confidence": 0.70
        })
