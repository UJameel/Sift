"""Action taker — creates GitHub issues from escalated signals."""
import httpx
from backend.config import GITHUB_TOKEN


async def create_github_issue(signal: dict, decision: dict, owner: str = None, repo: str = None) -> dict:
    """Create a GitHub issue from an escalated signal."""
    if not GITHUB_TOKEN:
        print(f"[ActionTaker] No GITHUB_TOKEN — would have created issue: {signal['title']}")
        return {"error": "no_token", "would_create": signal["title"]}

    # Default to a placeholder repo if not specified
    target_owner = owner or "your-org"
    target_repo = repo or "your-repo"

    body = f"""## Escalated by Sift 🤖

**Source**: {signal['source'].replace('_', ' ').title()}
**Original Author**: {signal.get('author', 'unknown')}
**Severity Score**: {decision['severity_score']}/10
**Category**: {decision.get('category', 'unknown')}

---

### Original Report

{signal.get('body', 'No body provided')}

---

### Agent Analysis

{decision.get('reasoning', 'No reasoning available')}

---
*Created automatically by Sift. Confidence: {decision.get('confidence', 0):.0%}*"""

    labels = _get_labels(decision)

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.github.com/repos/{target_owner}/{target_repo}/issues",
            headers={
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "Accept": "application/vnd.github+json",
            },
            json={
                "title": f"[Sift] {signal['title']}",
                "body": body,
                "labels": labels,
            },
            timeout=15.0
        )
        if resp.status_code == 201:
            data = resp.json()
            return {"created": True, "url": data["html_url"], "number": data["number"]}
        else:
            return {"error": resp.text, "status_code": resp.status_code}


def _get_labels(decision: dict) -> list[str]:
    labels = ["sift"]
    severity = decision.get("severity_score", 0)
    category = decision.get("category", "")

    if severity >= 9:
        labels.append("critical")
    elif severity >= 7:
        labels.append("high-priority")

    if category == "bug":
        labels.append("bug")
    elif category == "security":
        labels.append("security")
    elif category == "feature_request":
        labels.append("enhancement")

    return labels
