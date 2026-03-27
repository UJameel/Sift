"""
Agentic PR generator — reads a GitHub repo, sends context to Claude,
and opens a PR with a proposed fix. Triggered when founder says "fix it" on a Bland call.

Sponsors: Claude (fix generation), GitHub API (branch + PR), Overmind (tracing)
"""
import httpx
import base64
import json
import re
from datetime import datetime
from backend.config import GITHUB_TOKEN, OPENAI_API_KEY
from backend import db

try:
    import overmind
    _overmind = True
except Exception:
    _overmind = False


GITHUB_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# File extensions worth reading for context
CODE_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".rb", ".java", ".md"}
# Max files to pull for context (keep prompt lean)
MAX_CONTEXT_FILES = 8
MAX_FILE_CHARS = 3000


async def generate_pr(signal: dict, decision: dict) -> dict:
    """
    Full agentic loop:
    1. Read repo structure via GitHub API
    2. Pick relevant files based on issue title/body
    3. Send to Claude — ask for a concrete file diff/fix
    4. Create branch + commit + open PR
    5. Store PR URL back on the signal row
    """
    owner = signal.get("repo_owner")
    repo = signal.get("repo_name")

    if not owner or not repo:
        return {"error": "no_repo", "detail": "Signal missing repo_owner/repo_name"}

    if not GITHUB_TOKEN:
        return {"error": "no_token"}

    span = None
    if _overmind:
        try:
            span = overmind.start_span("sift.generate_pr", {
                "owner": owner, "repo": repo, "signal_id": signal.get("id")
            })
        except Exception:
            pass

    try:
        # 1. Get default branch
        default_branch = await _get_default_branch(owner, repo)

        # 2. Read repo tree (flat list of files)
        tree = await _get_repo_tree(owner, repo, default_branch)

        # 3. Pick files most relevant to this issue
        relevant_files = _pick_relevant_files(tree, signal)

        # 4. Fetch file contents
        file_contents = await _fetch_files(owner, repo, relevant_files)

        # 5. Ask Claude to generate the fix
        fix = await _generate_fix_with_claude(signal, decision, file_contents, owner, repo)

        if not fix or not fix.get("files"):
            return {"error": "no_fix_generated", "claude_response": fix}

        # 6. Create branch
        branch_name = f"sift/fix-{signal['id']}-{_slug(signal['title'])}"
        await _create_branch(owner, repo, branch_name, default_branch)

        # 7. Commit each changed file
        for file_change in fix["files"]:
            await _commit_file(owner, repo, branch_name, file_change["path"], file_change["content"], signal)

        # 8. Open PR
        pr = await _open_pr(owner, repo, branch_name, default_branch, signal, decision, fix)

        # 9. Store PR URL on signal
        if pr.get("url"):
            await db.execute(
                "UPDATE signals SET pr_url = $1 WHERE id = $2",
                pr["url"], signal["id"]
            )

        if span:
            try:
                overmind.finish_span(span, {"pr_url": pr.get("url"), "status": "success"})
            except Exception:
                pass

        return pr

    except Exception as e:
        if span:
            try:
                overmind.finish_span(span, {"status": "error", "error": str(e)})
            except Exception:
                pass
        return {"error": str(e)}


async def _get_default_branch(owner: str, repo: str) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}",
            headers=GITHUB_HEADERS, timeout=10.0
        )
        resp.raise_for_status()
        return resp.json().get("default_branch", "main")


async def _get_repo_tree(owner: str, repo: str, branch: str) -> list[str]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1",
            headers=GITHUB_HEADERS, timeout=15.0
        )
        if resp.status_code != 200:
            return []
        items = resp.json().get("tree", [])
        return [i["path"] for i in items if i["type"] == "blob"]


def _pick_relevant_files(tree: list[str], signal: dict) -> list[str]:
    """Score each file by keyword overlap with the issue title + body."""
    text = f"{signal.get('title', '')} {signal.get('body', '')}".lower()
    words = set(re.findall(r'\w+', text)) - {"the", "a", "an", "is", "in", "of", "to", "and", "or", "it"}

    scored = []
    for path in tree:
        ext = "." + path.rsplit(".", 1)[-1] if "." in path else ""
        if ext not in CODE_EXTENSIONS:
            continue
        parts = re.findall(r'\w+', path.lower())
        score = sum(1 for p in parts if p in words)
        # Boost root-level and src/ files
        if path.count("/") <= 1:
            score += 0.5
        scored.append((score, path))

    scored.sort(reverse=True)
    return [p for _, p in scored[:MAX_CONTEXT_FILES]]


async def _fetch_files(owner: str, repo: str, paths: list[str]) -> dict[str, str]:
    contents = {}
    async with httpx.AsyncClient() as client:
        for path in paths:
            try:
                resp = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo}/contents/{path}",
                    headers=GITHUB_HEADERS, timeout=10.0
                )
                if resp.status_code == 200:
                    data = resp.json()
                    raw = base64.b64decode(data.get("content", "")).decode("utf-8", errors="replace")
                    contents[path] = raw[:MAX_FILE_CHARS]
            except Exception:
                continue
    return contents


async def _generate_fix_with_claude(signal: dict, decision: dict, files: dict, owner: str, repo: str) -> dict:
    """Call OpenAI/Claude to produce a structured fix."""
    file_block = "\n\n".join(
        f"### {path}\n```\n{content}\n```" for path, content in files.items()
    ) if files else "No relevant files found — use your best judgement."

    prompt = f"""You are an expert software engineer. A critical bug has been detected in the GitHub repo `{owner}/{repo}`.

## Issue
**Title**: {signal['title']}
**Severity**: {decision['severity_score']}/10
**Category**: {decision.get('category', 'unknown')}

**Description**:
{signal.get('body', '')[:1000]}

## Agent Analysis
{decision.get('reasoning', '')}

## Relevant Repo Files
{file_block}

## Your Task
Propose a minimal, surgical fix for this issue. Return a JSON object with this exact shape:
{{
  "summary": "one-sentence description of the fix",
  "explanation": "2-3 sentences on what was wrong and how you fixed it",
  "files": [
    {{
      "path": "path/to/file.py",
      "content": "FULL new content of the file with the fix applied"
    }}
  ]
}}

Rules:
- Only modify files you have content for, or create a new file if necessary
- Keep changes minimal — fix the specific bug, don't refactor unrelated code
- If you cannot determine a concrete fix from the available context, return {{"files": [], "summary": "Insufficient context", "explanation": "..."}}
- Return ONLY the JSON, no markdown fences"""

    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 4000,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers, json=payload, timeout=60.0
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()

    # Strip markdown fences if model added them anyway
    raw = re.sub(r'^```(?:json)?\n?', '', raw).rstrip('`').strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"files": [], "summary": "Parse error", "explanation": raw[:500]}


async def _create_branch(owner: str, repo: str, branch: str, base: str):
    async with httpx.AsyncClient() as client:
        # Get base SHA
        ref_resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/git/ref/heads/{base}",
            headers=GITHUB_HEADERS, timeout=10.0
        )
        ref_resp.raise_for_status()
        sha = ref_resp.json()["object"]["sha"]

        # Create branch
        await client.post(
            f"https://api.github.com/repos/{owner}/{repo}/git/refs",
            headers=GITHUB_HEADERS,
            json={"ref": f"refs/heads/{branch}", "sha": sha},
            timeout=10.0
        )


async def _commit_file(owner: str, repo: str, branch: str, path: str, content: str, signal: dict):
    encoded = base64.b64encode(content.encode()).decode()
    async with httpx.AsyncClient() as client:
        # Get current SHA if file exists
        existing = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}",
            headers=GITHUB_HEADERS, timeout=10.0
        )
        body = {
            "message": f"fix: {signal['title'][:72]} [Sift #{signal['id']}]",
            "content": encoded,
            "branch": branch,
        }
        if existing.status_code == 200:
            body["sha"] = existing.json()["sha"]

        await client.put(
            f"https://api.github.com/repos/{owner}/{repo}/contents/{path}",
            headers=GITHUB_HEADERS, json=body, timeout=15.0
        )


async def _open_pr(owner: str, repo: str, branch: str, base: str, signal: dict, decision: dict, fix: dict) -> dict:
    body = f"""## Sift Auto-Fix 🤖

**Signal**: {signal['title']}
**Severity**: {decision['severity_score']}/10
**Source**: {signal.get('source', 'github_issue').replace('_', ' ').title()}
**Reported by**: {signal.get('author', 'unknown')}

---

### What was wrong
{fix.get('explanation', '')}

### What changed
{fix.get('summary', '')}

---

### Original Issue Description
{signal.get('body', '')[:500]}

---

### Agent Reasoning
{decision.get('reasoning', '')}

---
*Generated by [Sift](https://github.com) — review carefully before merging. Confidence: {decision.get('confidence', 0):.0%}*"""

    labels = ["sift", "auto-fix"]
    if decision.get("severity_score", 0) >= 9:
        labels.append("critical")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.github.com/repos/{owner}/{repo}/pulls",
            headers=GITHUB_HEADERS,
            json={
                "title": f"[Sift Fix] {signal['title'][:72]}",
                "body": body,
                "head": branch,
                "base": base,
            },
            timeout=15.0
        )
        data = resp.json()
        if resp.status_code == 201:
            return {"created": True, "url": data["html_url"], "number": data["number"]}
        else:
            return {"error": data.get("message", resp.text), "status_code": resp.status_code}


def _slug(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', text.lower())[:40].strip('-')
