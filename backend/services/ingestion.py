"""Airbyte GitHub connector — fetch real issues from a public repo."""
import os
import httpx
from typing import Optional
from backend import db
from backend.config import GITHUB_TOKEN


async def ingest_github_issues(owner: str = "fastapi", repo: str = "fastapi", limit: int = 20) -> list[dict]:
    """
    Fetch open issues from a GitHub repo via Airbyte agent connector (GraphQL).
    Falls back to GitHub REST API if connector unavailable.
    """
    try:
        from airbyte_agent_github import GithubConnector
        from airbyte_agent_github.models import GithubPersonalAccessTokenAuthConfig

        connector = GithubConnector(
            auth_config=GithubPersonalAccessTokenAuthConfig(token=GITHUB_TOKEN)
        )

        result = await connector.execute("issues", "list", {
            "owner": owner,
            "repo": repo,
            "states": ["OPEN"],
            "per_page": limit,
        })

        # Airbyte returns a GithubExecuteResult with .data attribute (list of GraphQL nodes)
        if hasattr(result, "data"):
            issues = result.data or []
        elif isinstance(result, list):
            issues = result
        else:
            issues = result.get("issues", []) if isinstance(result, dict) else []

        print(f"[Airbyte] Fetched {len(issues)} issues from {owner}/{repo}")
        return await _store_issues(_normalize_airbyte_issues(issues), owner, repo)

    except Exception as e:
        print(f"[Airbyte] Connector failed ({e}), falling back to GitHub REST API")
        return await _fetch_via_rest(owner, repo, limit)


def _normalize_airbyte_issues(issues: list) -> list[dict]:
    """Map Airbyte GraphQL fields to the shape _store_issues expects."""
    normalized = []
    for issue in issues:
        if not isinstance(issue, dict):
            issue = dict(issue) if hasattr(issue, "__dict__") else vars(issue)
        normalized.append({
            "number": issue.get("number") or issue.get("databaseId"),
            "title": issue.get("title", ""),
            "body": issue.get("body", "") or "",
            "user": {"login": (issue.get("author") or {}).get("login", "unknown")},
            "pull_request": None,  # Airbyte issues endpoint doesn't return PRs
        })
    return normalized


async def _fetch_via_rest(owner: str, repo: str, limit: int) -> list[dict]:
    """Fallback: direct GitHub REST API call."""
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/issues",
            params={"state": "open", "per_page": limit},
            headers=headers,
            timeout=15.0
        )
        resp.raise_for_status()
        issues = resp.json()

    return await _store_issues(issues, owner, repo)


async def _store_issues(issues: list, owner: str, repo: str) -> list[dict]:
    """Insert GitHub issues as signals, skip existing ones."""
    stored = []
    for issue in issues:
        source_id = f"gh_{owner}_{repo}_{issue.get('number', issue.get('id', ''))}"
        title = issue.get("title", "")
        body = (issue.get("body") or "")[:2000]
        author = issue.get("user", {}).get("login", "") if isinstance(issue.get("user"), dict) else str(issue.get("author", ""))

        # Skip PRs
        if issue.get("pull_request"):
            continue

        existing = await db.fetch_one("SELECT id FROM signals WHERE source_id = $1", source_id)
        if existing:
            continue

        row = await db.fetch_one(
            """
            INSERT INTO signals (source, source_id, title, body, author, repo_owner, repo_name)
            VALUES ('github_issue', $1, $2, $3, $4, $5, $6)
            RETURNING *
            """,
            source_id, title, body, author, owner, repo
        )
        stored.append(dict(row))

    return stored
