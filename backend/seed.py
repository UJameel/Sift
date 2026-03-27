"""Seed realistic demo signals, learned rules, and demo accuracy data."""
import asyncio
from backend.db import init_db, execute, fetch_all, fetchval

SEED_SIGNALS = [
    {
        "source": "github_issue",
        "source_id": "gh_001",
        "title": "CRITICAL: Data corruption when saving user settings",
        "body": "After the latest update, user settings are being overwritten randomly. Multiple users reporting lost data. This is happening on production. We've had 47 reports in the last 2 hours.",
        "author": "angry_power_user",
    },
    {
        "source": "app_review",
        "source_id": "review_002",
        "title": "App crashes every time I open it — 1 star",
        "body": "Since the last update, the app crashes immediately on launch. I've tried reinstalling 3 times. This is completely broken. Lost all my data. Never using this again.",
        "author": "user_ios_frustrated",
    },
    {
        "source": "github_issue",
        "source_id": "gh_003",
        "title": "Feature request: dark mode support",
        "body": "It would be nice to have a dark mode option. The white background is a bit harsh at night. Not urgent at all, just a nice-to-have for the future.",
        "author": "new_contributor",
    },
    {
        "source": "slack",
        "source_id": "slack_004",
        "title": "Authentication tokens expiring too fast",
        "body": "Hey team, getting reports from enterprise clients that auth tokens are expiring after 15 minutes instead of 24 hours. About 12 enterprise accounts affected. Some are threatening churn.",
        "author": "support_team",
    },
    {
        "source": "support_ticket",
        "source_id": "ticket_005",
        "title": "Can't export data to CSV",
        "body": "Hi, when I click the export button nothing happens. I've tried in Chrome and Firefox. Would love this feature to work as I need to share reports with my team.",
        "author": "business_user_jane",
    },
    {
        "source": "github_issue",
        "source_id": "gh_006",
        "title": "SQL injection vulnerability in search endpoint",
        "body": "Found a potential SQL injection vector in the /api/search endpoint. User input is not being sanitized before hitting the DB. Tested with a simple ' OR 1=1 -- and got back all records. This is a serious security issue.",
        "author": "security_researcher",
    },
    {
        "source": "app_review",
        "source_id": "review_007",
        "title": "Love the new update! 5 stars",
        "body": "The new interface is so much cleaner. Everything loads faster and the new features are exactly what I needed. Great work team!",
        "author": "happy_power_user",
    },
    {
        "source": "slack",
        "source_id": "slack_008",
        "title": "Typo on pricing page",
        "body": "Just noticed there's a typo on the pricing page — it says 'Profesional' instead of 'Professional'. Minor thing but looks a bit unprofessional.",
        "author": "marketing_intern",
    },
    {
        "source": "support_ticket",
        "source_id": "ticket_009",
        "title": "API rate limiting hitting enterprise customers",
        "body": "We have 3 enterprise customers hitting the 1000 req/min limit repeatedly. They're on the enterprise tier and expected higher limits. Two are requesting refunds. Revenue at risk: ~$50k ARR.",
        "author": "account_manager",
    },
    {
        "source": "github_issue",
        "source_id": "gh_010",
        "title": "Memory leak in long-running WebSocket connections",
        "body": "Memory usage grows steadily when WebSocket connections are open for >1 hour. In production, servers are restarting every 6-8 hours due to OOM. Affects all users on the real-time dashboard.",
        "author": "senior_dev_external",
    },
]


SEED_RULES = [
    ("Security vulnerabilities and SQL injection reports should always be escalated immediately", 0.95),
    ("Issues mentioning 'data loss' or 'corruption' from production are always critical", 0.92),
    ("App crash reports affecting multiple users warrant immediate escalation", 0.88),
    ("Feature requests phrased politely are low priority — severity < 4", 0.85),
    ("Praise and 5-star reviews should always be ignored", 0.97),
]

SEED_ACCURACY = [
    (1, 4, 2, 0.50),
    (2, 6, 4, 0.67),
    (3, 8, 6, 0.75),
    (4, 10, 8, 0.80),
]


async def seed():
    await init_db()

    existing = await fetch_all("SELECT id FROM signals LIMIT 1")
    if not existing:
        for s in SEED_SIGNALS:
            await execute(
                """
                INSERT INTO signals (source, source_id, title, body, author)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT DO NOTHING
                """,
                s["source"], s["source_id"], s["title"], s["body"], s["author"]
            )
        print(f"Seeded {len(SEED_SIGNALS)} signals.")

    # Seed learned rules
    rules_count = await fetchval("SELECT COUNT(*) FROM learned_rules")
    if rules_count == 0:
        for rule, confidence in SEED_RULES:
            await execute(
                "INSERT INTO learned_rules (rule, confidence) VALUES ($1, $2)",
                rule, confidence
            )
        print(f"Seeded {len(SEED_RULES)} learned rules.")

    # Seed accuracy history (shows the improvement curve)
    accuracy_count = await fetchval("SELECT COUNT(*) FROM accuracy_log")
    if accuracy_count == 0:
        for scan_num, total, correct, accuracy in SEED_ACCURACY:
            await execute(
                "INSERT INTO accuracy_log (scan_number, total_decisions, correct_decisions, accuracy) VALUES ($1, $2, $3, $4)",
                scan_num, total, correct, accuracy
            )
        print("Seeded accuracy history (50% → 80%).")


if __name__ == "__main__":
    asyncio.run(seed())
