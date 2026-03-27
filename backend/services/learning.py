"""Self-improving loop — generates rules from feedback, tracks accuracy over time."""
import json
import httpx
from contextlib import contextmanager

try:
    import overmind
    _OVERMIND_AVAILABLE = True
except ImportError:
    _OVERMIND_AVAILABLE = False


@contextmanager
def _trace(name, **kwargs):
    if _OVERMIND_AVAILABLE:
        try:
            with overmind.trace(name, **kwargs):
                yield
            return
        except Exception:
            pass
    yield

from backend import db
from backend.config import OPENAI_API_KEY


class LearningService:
    async def process_feedback(self, decision_id: int, response: str, details: str):
        """The core learning loop: feedback → lesson → stored rule → better future decisions."""
        decision = await db.fetch_one("SELECT * FROM decisions WHERE id = $1", decision_id)
        if not decision:
            return

        signal = await db.fetch_one("SELECT * FROM signals WHERE id = $1", decision["signal_id"])
        if not signal:
            return

        decision = dict(decision)
        signal = dict(signal)

        # Was the escalation correct?
        was_correct = response in ["good_call", "create_issue"]

        # Generate a lesson from this interaction
        lesson = await self.generate_lesson(signal, decision, response, was_correct)

        if lesson:
            await self.store_learned_rule(lesson, [decision_id])

        # Update rolling accuracy
        await self.update_accuracy(was_correct)

    async def generate_lesson(self, signal: dict, decision: dict, response: str, was_correct: bool) -> str | None:
        """Ask the LLM to reflect on what it got right or wrong."""
        prompt = f"""You previously analyzed this signal and made a decision:

Signal title: {signal['title']}
Signal body: {(signal.get('body') or '')[:200]}
Source: {signal['source']}
Your severity score: {decision['severity_score']}/10
Your action: {decision['action_taken']}
Your reasoning: {decision['reasoning']}

Founder's response: {response}
Was your call correct: {was_correct}

Generate ONE concise rule (max 1 sentence) that will help you make better decisions next time.
The rule should be specific and actionable, referencing patterns from this example.
Format: just the rule text, nothing else.

Examples of good rules:
- "GitHub issues mentioning 'crash' or 'data loss' from repos with >100 stars should always be escalated"
- "Feature requests phrased as complaints are usually low-severity despite negative tone"
- "Issues from security researchers should always be escalated regardless of politeness"
- "Memory leaks affecting production servers warrant immediate escalation"
- "Praise feedback should always be ignored — no action needed"
"""
        with _trace("generate_lesson", metadata={"decision_id": decision["id"], "was_correct": was_correct}):
            rule = await self._call_llm(prompt)

        return rule.strip() if rule else None

    async def store_learned_rule(self, rule: str, feedback_ids: list[int]):
        """Store a new rule, or increase confidence of existing similar rule."""
        # Check for very similar existing rule (simple dedup)
        existing = await db.fetch_one(
            "SELECT id, confidence FROM learned_rules WHERE rule = $1",
            rule
        )

        if existing:
            new_confidence = min(0.99, existing["confidence"] + 0.05)
            await db.execute(
                "UPDATE learned_rules SET confidence = $1 WHERE id = $2",
                new_confidence, existing["id"]
            )
        else:
            await db.execute(
                "INSERT INTO learned_rules (rule, confidence, source_feedback_ids) VALUES ($1, $2, $3)",
                rule, 0.70, feedback_ids
            )

    async def update_accuracy(self, was_correct: bool):
        """Recalculate rolling accuracy and log it."""
        total_feedback = await db.fetchval("SELECT COUNT(*) FROM feedback")
        correct = await db.fetchval(
            "SELECT COUNT(*) FROM feedback WHERE response IN ('good_call', 'create_issue')"
        )

        accuracy = correct / total_feedback if total_feedback > 0 else 0.5

        # Get current scan number
        last_scan = await db.fetchval("SELECT MAX(scan_number) FROM accuracy_log") or 0
        scan_number = last_scan + 1

        await db.execute(
            """
            INSERT INTO accuracy_log (scan_number, total_decisions, correct_decisions, accuracy)
            VALUES ($1, $2, $3, $4)
            """,
            scan_number, total_feedback, correct, round(accuracy, 4)
        )

    async def _call_llm(self, prompt: str) -> str:
        if not OPENAI_API_KEY:
            return self._mock_rule(prompt)

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "max_tokens": 150,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=20.0
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

    def _mock_rule(self, prompt: str) -> str:
        """Deterministic mock rules for demo without API key."""
        text = prompt.lower()
        if "crash" in text:
            return "App crash reports from any source should always be escalated immediately"
        elif "security" in text or "injection" in text or "vulnerability" in text:
            return "Any signal mentioning security vulnerabilities warrants immediate escalation regardless of author"
        elif "enterprise" in text or "revenue" in text or "churn" in text:
            return "Signals mentioning enterprise customers or revenue risk should always be escalated"
        elif "memory" in text or "leak" in text:
            return "Memory leaks causing production restarts are critical and should always be escalated"
        elif "feature" in text or "nice to have" in text:
            return "Feature requests phrased as suggestions are low priority unless from multiple users"
        elif "praise" in text or "love" in text or "great" in text:
            return "Positive feedback and praise should always be ignored — no escalation needed"
        else:
            return "Signals with multiple users reporting the same issue should have severity increased by 2 points"


async def seed_demo_feedback():
    """Pre-seed feedback entries to show an accuracy improvement curve for the demo."""
    # Check if we already have seeded feedback
    existing = await db.fetchval("SELECT COUNT(*) FROM feedback")
    if existing > 0:
        return

    decisions = await db.fetch_all("SELECT * FROM decisions ORDER BY id LIMIT 6")
    if not decisions:
        return

    learning = LearningService()

    # Seed: first few have 50% accuracy, improving to 80%+
    mock_responses = [
        ("not_important", "Actually this isn't that urgent"),    # wrong — agent escalated
        ("good_call", "Yes, that's definitely worth tracking"),  # correct
        ("not_important", "That's a feature request, ignore"),   # correct — agent queued
        ("good_call", "Absolutely critical, create an issue"),   # correct
    ]

    for i, decision_row in enumerate(decisions[:len(mock_responses)]):
        decision = dict(decision_row)
        response, details = mock_responses[i]
        await db.execute(
            "INSERT INTO feedback (decision_id, response, response_details) VALUES ($1, $2, $3)",
            decision["id"], response, details
        )
        await learning.update_accuracy(response in ["good_call", "create_issue"])
