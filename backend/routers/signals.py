from fastapi import APIRouter, HTTPException
from backend import db
from backend.models import SignalCreate

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("")
async def list_signals(limit: int = 50, offset: int = 0):
    rows = await db.fetch_all(
        "SELECT * FROM signals ORDER BY created_at DESC LIMIT $1 OFFSET $2",
        limit, offset
    )
    return [dict(r) for r in rows]


@router.get("/{signal_id}")
async def get_signal(signal_id: int):
    row = await db.fetch_one("SELECT * FROM signals WHERE id = $1", signal_id)
    if not row:
        raise HTTPException(status_code=404, detail="Signal not found")
    return dict(row)


@router.post("")
async def create_signal(signal: SignalCreate):
    row = await db.fetch_one(
        """
        INSERT INTO signals (source, source_id, title, body, author)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING *
        """,
        signal.source, signal.source_id, signal.title, signal.body, signal.author
    )
    return dict(row)


@router.delete("/{signal_id}")
async def delete_signal(signal_id: int):
    await db.execute("DELETE FROM signals WHERE id = $1", signal_id)
    return {"deleted": signal_id}
