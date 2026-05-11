"""Intern Prep Agent - FastAPI Application."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy import text
from db.session import engine
from db.models import Base
from api.routes.plan import router as plan_router
from api.routes.interview import router as interview_router
from fastapi.responses import HTMLResponse
from pathlib import Path


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup."""
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="Intern Prep Agent",
    description="AI-powered internship preparation system",
    version="0.1.0",
    lifespan=lifespan,
)

@app.get("/", response_class=HTMLResponse)
async def chat_page():
    """Serve the chat frontend."""
    html = Path("templates/chat.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html)


@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}


# Register routers
app.include_router(plan_router, prefix="/api")
app.include_router(interview_router, prefix="/api")


@app.get("/health/db")
async def db_health_check():
    """Check database connectivity."""
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": str(e)}
