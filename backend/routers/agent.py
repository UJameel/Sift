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
        "SELECT * FROM signals WHERE processed_at IS NULL AND is_escalated = FALSE ORDER BY created_at ASC"
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
