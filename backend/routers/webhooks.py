"""Bland AI webhook — receives call completion with transcript."""
from fastapi import APIRouter, Request
from backend import db
from backend.services.action_taker import create_github_issue
from backend.services.pr_generator import generate_pr
from backend.services.learning import LearningService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
learning_service = LearningService()


@router.post("/bland-complete")
async def bland_call_complete(request: Request):
    """Handle Bland AI call completion webhook."""
    data = await request.json()

    call_id = data.get("call_id", "")
    transcript = data.get("concatenated_transcript", "") or data.get("transcript", "")
    metadata = data.get("metadata", {})

    signal_id = metadata.get("signal_id")
    decision_id = metadata.get("decision_id")

    # Parse founder's response from transcript
    response, details = _parse_founder_response(transcript)

    if decision_id:
        # Store feedback
        feedback_row = await db.fetch_one(
            """
            INSERT INTO feedback (decision_id, response, response_details)
            VALUES ($1, $2, $3)
            RETURNING *
            """,
            int(decision_id), response, transcript[:1000]
        )

        # Trigger learning
        await learning_service.process_feedback(int(decision_id), response, transcript)

        # Take action if requested
        if signal_id and decision_id:
            signal = await db.fetch_one("SELECT * FROM signals WHERE id = $1", int(signal_id))
            decision = await db.fetch_one("SELECT * FROM decisions WHERE id = $1", int(decision_id))
            if signal and decision:
                if response == "generate_pr":
                    await generate_pr(dict(signal), dict(decision))
                elif response == "create_issue":
                    await create_github_issue(dict(signal), dict(decision))

    return {"received": True, "call_id": call_id, "response_parsed": response}


def _parse_founder_response(transcript: str) -> tuple[str, str]:
    """Parse the founder's verbal response into a structured action."""
    if not transcript:
        return "not_important", ""

    text = transcript.lower()

    if any(p in text for p in ["fix it", "fix this", "generate a pr", "generate pr", "send a pr", "open a pr", "create a pr", "write a fix", "patch it"]):
        return "generate_pr", transcript
    elif any(p in text for p in ["create issue", "create a github", "create an issue", "make an issue", "open an issue"]):
        return "create_issue", transcript
    elif any(p in text for p in ["not important", "not worth", "ignore", "skip it", "don't bother", "false alarm"]):
        return "not_important", transcript
    elif any(p in text for p in ["good call", "yes", "absolutely", "critical", "urgent", "that's important"]):
        return "good_call", transcript
    elif any(p in text for p in ["backlog", "add it", "track it", "note it"]):
        return "good_call", transcript
    else:
        return "good_call", transcript  # Default to positive if response captured
