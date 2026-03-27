"""Bland AI voice alert service — calls the founder via the Sift Norm persona."""
import httpx
from backend.config import BLAND_API_KEY, BLAND_PERSONA_ID, BLAND_PATHWAY_ID, BLAND_FROM_NUMBER, ALERT_PHONE_NUMBER, WEBHOOK_URL


async def call_founder(signal: dict, decision: dict) -> dict:
    """Make a Bland AI call using the Sift Norm persona with signal context injected."""
    if not BLAND_API_KEY or not ALERT_PHONE_NUMBER:
        print(f"[BlandAI] Skipping — missing config. Would have called about: {signal['title']}")
        return {"call_id": "mock_call_no_config", "status": "skipped"}

    # Signal context passed as variables — the persona prompt references these
    # Variable names must match what Norm pathway expects
    request_data = {
        "phone_number": ALERT_PHONE_NUMBER,
        "from": BLAND_FROM_NUMBER or None,
        "record": True,
        "max_duration": 5,
        "metadata": {
            "signal_id": signal.get("id"),
            "decision_id": decision.get("id"),
        },
        "request_data": {
            # Norm pathway variables
            "issue_title": signal.get("title", "Unknown issue"),
            "issue_source": signal.get("source", "github_issue").replace("_", " ").title(),
            "severity_score": str(round(float(decision.get("severity_score", 0)), 1)),
            # Extra context for the agent
            "signal_author": signal.get("author", "unknown"),
            "additional_context": (decision.get("reasoning") or "")[:300],
        },
    }

    if BLAND_PATHWAY_ID:
        # Use the Norm-built pathway (preferred)
        request_data["pathway_id"] = BLAND_PATHWAY_ID
    elif BLAND_PERSONA_ID:
        # Fallback: persona
        request_data["persona_id"] = BLAND_PERSONA_ID
    else:
        # Fallback: inline task
        request_data["task"] = _build_task(signal, decision)
        request_data["voice"] = "mason"
        request_data["max_duration"] = 3

    # Only attach webhook if publicly reachable
    if WEBHOOK_URL and not WEBHOOK_URL.startswith("http://localhost"):
        request_data["webhook"] = f"{WEBHOOK_URL}/webhooks/bland-complete"

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.bland.ai/v1/calls",
            headers={"authorization": BLAND_API_KEY},
            json=request_data,
            timeout=15.0,
        )
        resp.raise_for_status()
        return resp.json()


def _build_task(signal: dict, decision: dict) -> str:
    """Inline task fallback when no persona is configured."""
    return f"""You are Sift, an autonomous AI that monitors product feedback for founders.

You are calling because you detected a critical signal:

Signal: {signal.get('title')}
Source: {signal.get('source', '').replace('_', ' ').title()}
Severity: {decision.get('severity_score')}/10
Author: {signal.get('author', 'unknown')}
Reasoning: {decision.get('reasoning', '')}

Start with: "Hi, this is Sift. I've detected a critical issue that needs your attention."
Describe the signal briefly, then ask: "Should I generate a PR fix, add it to your backlog, or is this not worth tracking?"
Confirm what action you will take and end the call. Keep it under 90 seconds."""
