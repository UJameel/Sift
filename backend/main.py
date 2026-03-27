import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend import db
from backend.seed import seed
from backend.routers import signals
from backend.routers import agent
from backend.routers import feedback
from backend.routers import webhooks

import overmind
from backend.config import OVERMIND_API_KEY

# Init Overmind tracing — patches OpenAI calls automatically
try:
    overmind.init(
        overmind_api_key=OVERMIND_API_KEY or None,
        service_name="sift",
        environment="production",
        providers=["openai"],
    )
    print(f"[Overmind] Tracing active — service=sift providers=[openai]")
except Exception as e:
    print(f"[Overmind] Init failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()
    await seed()
    yield
    await db.close_pool()


app = FastAPI(
    title="Sift",
    description="Autonomous AI agent that monitors product feedback, learns what matters, and calls you when it's critical.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(signals.router)
app.include_router(agent.router)
app.include_router(feedback.router)
app.include_router(webhooks.router)

# Serve dashboard
dashboard_path = os.path.join(os.path.dirname(__file__), "..", "dashboard")
if os.path.exists(dashboard_path):
    app.mount("/", StaticFiles(directory=dashboard_path, html=True), name="dashboard")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "sift"}
