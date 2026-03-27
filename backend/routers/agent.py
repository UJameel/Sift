from fastapi import APIRouter, HTTPException, Depends
from backend import db
from backend.services.analyzer import analyze_signal
from backend.services.ingestion import ingest_github_issues
from backend.services.bland_caller import call_founder
from backend.services.ghost import simulate_threshold
from backend.auth import require_auth
from datetime import datetime

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/scan")
async def run_scan(user=Depends(require_auth)):
    """Analyze all unprocessed signals and take action."""
    unprocessed = await db.fetch_all(
        "SELECT * FROM signals WHERE processed_at IS NULL ORDER BY created_at ASC"
    )

    results = []
    escalated = 0
    ignored = 0
    queued = 0

    for row in unprocessed:
        signal = dict(row)
        decision_data = await analyze_signal(signal)

        # Store decision
        decision_row = await db.fetch_one(
            """
            INSERT INTO decisions (signal_id, action_taken, severity_score, confidence, reasoning)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
            """,
            signal["id"],
            decision_data["action_taken"],
            decision_data["severity_score"],
            decision_data["confidence"],
            decision_data["reasoning"]
        )

        # Update signal with analysis
        await db.execute(
            """
            UPDATE signals
            SET severity_score = $1, category = $2, is_escalated = $3,
                agent_reasoning = $4, processed_at = $5
            WHERE id = $6
            """,
            decision_data["severity_score"],
            decision_data["category"],
            decision_data["action_taken"] == "escalated",
            decision_data["reasoning"],
            datetime.utcnow(),
            signal["id"]
        )

        action = decision_data["action_taken"]
        if action == "escalated":
            escalated += 1
            # Trigger Bland AI voice call for escalated signals
            try:
                call_result = await call_founder(signal, decision_data)
                decision_data["call_id"] = call_result.get("call_id")
                decision_data["call_status"] = call_result.get("status", "queued")
                decision_data["inbound_fallback"] = "+14153601802"
            except Exception as e:
                decision_data["call_error"] = str(e)
                decision_data["inbound_fallback"] = "+14153601802"
        elif action == "ignored":
            ignored += 1
        else:
            queued += 1

        results.append({
            "signal_id": signal["id"],
            "title": signal["title"],
            "source": signal["source"],
            "decision_id": decision_row["id"],
            **decision_data
        })

    return {
        "total_processed": len(unprocessed),
        "escalated": escalated,
        "ignored": ignored,
        "queued": queued,
        "decisions": results
    }


@router.post("/scan/{signal_id}")
async def scan_single(signal_id: int):
    """Analyze a single signal by ID."""
    signal = await db.fetch_one("SELECT * FROM signals WHERE id = $1", signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    signal = dict(signal)
    decision_data = await analyze_signal(signal)

    decision_row = await db.fetch_one(
        """
        INSERT INTO decisions (signal_id, action_taken, severity_score, confidence, reasoning)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING *
        """,
        signal_id,
        decision_data["action_taken"],
        decision_data["severity_score"],
        decision_data["confidence"],
        decision_data["reasoning"]
    )

    await db.execute(
        """
        UPDATE signals
        SET severity_score = $1, category = $2, is_escalated = $3,
            agent_reasoning = $4, processed_at = $5
        WHERE id = $6
        """,
        decision_data["severity_score"],
        decision_data["category"],
        decision_data["action_taken"] == "escalated",
        decision_data["reasoning"],
        datetime.utcnow(),
        signal_id
    )

    return {"signal_id": signal_id, "decision_id": decision_row["id"], **decision_data}


@router.post("/ingest")
async def ingest(owner: str = "fastapi", repo: str = "fastapi", limit: int = 10, user=Depends(require_auth)):
    """Pull real GitHub issues via Airbyte connector and store as signals."""
    stored = await ingest_github_issues(owner=owner, repo=repo, limit=limit)
    return {"ingested": len(stored), "signals": stored}


@router.get("/accuracy")
async def get_accuracy():
    """Return accuracy time series for the learning chart."""
    rows = await db.fetch_all(
        "SELECT * FROM accuracy_log ORDER BY scan_number ASC"
    )
    return {
        "history": [dict(r) for r in rows],
        "current_accuracy": rows[-1]["accuracy"] if rows else None
    }


@router.get("/decisions")
async def list_decisions(limit: int = 50):
    rows = await db.fetch_all(
        """
        SELECT d.*, s.title, s.source, s.body
        FROM decisions d
        JOIN signals s ON s.id = d.signal_id
        ORDER BY d.created_at DESC
        LIMIT $1
        """,
        limit
    )
    return [dict(r) for r in rows]


@router.get("/learned-rules")
async def list_learned_rules():
    rows = await db.fetch_all(
        "SELECT * FROM learned_rules ORDER BY confidence DESC"
    )
    return [dict(r) for r in rows]


@router.post("/reset-signals")
async def reset_signals(full: bool = False, clear_rules: bool = False):
    """
    Reset the feedback loop.
    - Default: mark signals unprocessed (soft reset for demo re-runs)
    - full=true: delete all signals, decisions, feedback, and accuracy log
    - clear_rules=true: also wipe learned rules
    """
    if full:
        await db.execute("DELETE FROM feedback")
        await db.execute("DELETE FROM decisions")
        await db.execute("DELETE FROM signals")
        await db.execute("DELETE FROM accuracy_log")
        deleted = {"signals": True, "decisions": True, "feedback": True, "accuracy_log": True}
    else:
        await db.execute("UPDATE signals SET processed_at = NULL, is_escalated = FALSE, severity_score = 0, agent_reasoning = NULL, category = NULL, pr_url = NULL")
        deleted = {}

    if clear_rules:
        await db.execute("DELETE FROM learned_rules")
        deleted["learned_rules"] = True

    return {"reset": True, "full": full, "cleared": deleted}


@router.post("/simulate")
async def simulate(threshold: float = 6.0):
    """
    Ghost fork simulation — runs a what-if analysis on an isolated DB copy.
    Shows how many signals would escalate at a different threshold,
    without touching production data. Powered by Ghost's fork pattern.
    """
    try:
        result = await simulate_threshold(threshold)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
