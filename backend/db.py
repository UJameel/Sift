import asyncpg
from backend.config import DATABASE_URL

_pool = None


async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS signals (
    id SERIAL PRIMARY KEY,
    source VARCHAR(50) NOT NULL,
    source_id VARCHAR(255),
    title TEXT,
    body TEXT,
    author VARCHAR(255),
    severity_score FLOAT DEFAULT 0,
    category VARCHAR(50),
    is_escalated BOOLEAN DEFAULT FALSE,
    agent_reasoning TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    processed_at TIMESTAMP,
    repo_owner VARCHAR(255),
    repo_name VARCHAR(255),
    pr_url TEXT
);

CREATE TABLE IF NOT EXISTS decisions (
    id SERIAL PRIMARY KEY,
    signal_id INTEGER REFERENCES signals(id),
    action_taken VARCHAR(50),
    severity_score FLOAT,
    confidence FLOAT,
    reasoning TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS feedback (
    id SERIAL PRIMARY KEY,
    decision_id INTEGER REFERENCES decisions(id),
    response VARCHAR(50),
    response_details TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS learned_rules (
    id SERIAL PRIMARY KEY,
    rule TEXT NOT NULL,
    confidence FLOAT,
    source_feedback_ids INTEGER[],
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS accuracy_log (
    id SERIAL PRIMARY KEY,
    scan_number INTEGER,
    total_decisions INTEGER,
    correct_decisions INTEGER,
    accuracy FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);
"""


async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA_SQL)


async def fetch_all(query: str, *args):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(query, *args)


async def fetch_one(query: str, *args):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(query, *args)


async def execute(query: str, *args):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.execute(query, *args)


async def fetchval(query: str, *args):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(query, *args)
