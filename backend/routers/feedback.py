from fastapi import APIRouter, HTTPException
from backend import db
from backend.models import FeedbackCreate
from backend.services.learning import LearningService
from backend.services.action_taker import create_github_issue
from backend.services.pr_generator import generate_pr

router = APIRouter(prefix="/feedback", tags=["feedback"])
learning_service = LearningService()


@router.post("/{decision_id}")
async def submit_feedback(decision_id: int, feedback: FeedbackCreate):
    """Manual feedback endpoint — records founder's response and triggers learning."""
    decision = await db.fetch_one("SELECT * FROM decisions WHERE id = $1", decision_id)
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    # Store feedback
    row = await db.fetch_one(
        """
        INSERT INTO feedback (decision_id, response, response_details)
        VALUES ($1, $2, $3)
        RETURNING *
        """,
        decision_id, feedback.response, feedback.response_details
    )

    # Trigger self-improving loop
    await learning_service.process_feedback(decision_id, feedback.response, feedback.response_details or "")

    signal = await db.fetch_one("SELECT * FROM signals WHERE id = $1", decision["signal_id"])

    if feedback.response == "generate_pr" and signal:
        result = await generate_pr(dict(signal), dict(decision))
        return {"feedback": dict(row), "pr": result}

    if feedback.response == "create_issue" and signal:
        # For non-GitHub signals only — GitHub signals should use generate_pr
        if dict(signal).get("source") != "github_issue":
            result = await create_github_issue(dict(signal), dict(decision))
            return {"feedback": dict(row), "github_issue": result}

    return {"feedback": dict(row)}


@router.get("/accuracy")
async def get_accuracy_history():
    rows = await db.fetch_all("SELECT * FROM accuracy_log ORDER BY scan_number ASC")
    if not rows:
        return {"history": [], "current_accuracy": None, "total_feedback": 0}

    total = await db.fetchval("SELECT COUNT(*) FROM feedback")
    return {
        "history": [dict(r) for r in rows],
        "current_accuracy": rows[-1]["accuracy"],
        "total_feedback": total
    }


@router.get("")
async def list_feedback(limit: int = 50):
    rows = await db.fetch_all(
        """
        SELECT f.*, d.signal_id, d.action_taken, d.severity_score, s.title, s.source
        FROM feedback f
        JOIN decisions d ON d.id = f.decision_id
        JOIN signals s ON s.id = d.signal_id
        ORDER BY f.created_at DESC
        LIMIT $1
        """,
        limit
    )
    return [dict(r) for r in rows]
