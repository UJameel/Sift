"""
Ghost (ghost.build) — Postgres built for agents.

Ghost's killer feature: instant database forks. Sift uses this to run
"what-if" simulations — e.g. "what would have happened if my escalation
threshold was 6.0 instead of 7.0?" — without touching production data.

The fork is a Postgres schema copy that is isolated, disposable, and
discarded after the simulation. This is the Ghost agent-native pattern.
"""
import asyncpg
import uuid
from contextlib import asynccontextmanager
from backend.config import DATABASE_URL


@asynccontextmanager
async def fork_db(label: str = "sim"):
    """
    Ghost fork pattern: copy production schema into an isolated namespace,
    run agent logic against the fork, then drop it.

    Usage:
        async with fork_db("what_if_threshold_6") as fork_conn:
            await fork_conn.execute("UPDATE signals SET ...")
            results = await fork_conn.fetch("SELECT ...")
        # Fork is automatically dropped — production unchanged
    """
    fork_name = f"ghost_fork_{label}_{uuid.uuid4().hex[:8]}"
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # Create isolated schema for this fork
        await conn.execute(f'CREATE SCHEMA "{fork_name}"')

        # Copy production tables into fork schema
        for table in ["signals", "decisions", "feedback", "learned_rules", "accuracy_log"]:
            await conn.execute(f"""
                CREATE TABLE "{fork_name}".{table}
                AS SELECT * FROM public.{table}
            """)

        print(f"[Ghost] Fork created: {fork_name}")
        yield conn, fork_name

    finally:
        # Drop the fork — disposable, no side effects
        await conn.execute(f'DROP SCHEMA IF EXISTS "{fork_name}" CASCADE')
        await conn.close()
        print(f"[Ghost] Fork dropped: {fork_name}")


async def simulate_threshold(threshold: float) -> dict:
    """
    What-if simulation: how many signals would have escalated
    at a different severity threshold? Runs on a Ghost fork.
    """
    async with fork_db(f"threshold_{str(threshold).replace('.', '_')}") as (conn, schema):
        # Count escalations at the given threshold in the fork
        total = await conn.fetchval(f'SELECT COUNT(*) FROM "{schema}".signals WHERE processed_at IS NOT NULL')
        would_escalate = await conn.fetchval(
            f'SELECT COUNT(*) FROM "{schema}".signals WHERE severity_score >= $1',
            threshold
        )
        actual_escalated = await conn.fetchval(
            f'SELECT COUNT(*) FROM "{schema}".signals WHERE is_escalated = TRUE'
        )

        return {
            "simulation": "threshold_change",
            "simulated_threshold": threshold,
            "total_processed": total,
            "would_escalate": would_escalate,
            "actual_escalated": actual_escalated,
            "delta": would_escalate - actual_escalated,
            "ghost_fork": "isolated — production unchanged",
        }
