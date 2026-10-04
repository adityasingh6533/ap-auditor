"""
Main FastAPI entrypoint for the AP Auditor Backend Application.
Provides RESTful APIs for invoice auditing, exception review workflows, audit trails, and reporting.
"""

from pathlib import Path
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables (.env in backend or workspace root)
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path)
else:
    load_dotenv()

from .api import audit, chat, config, exceptions, invoices, reports, stats
from .db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure SQLite database and tables exist
    init_db()
    yield
    # Shutdown logic if needed


app = FastAPI(
    title="AP Auditor API",
    description="Accounts-Payable Exception Checker & Audit Intelligence Platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Enable CORS for frontend web application
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(invoices.router)
app.include_router(exceptions.router)
app.include_router(audit.router)
app.include_router(stats.router)
app.include_router(reports.router)
app.include_router(config.router)
app.include_router(chat.router)


@app.get("/", tags=["Health"])
def health_check():
    """Service health check endpoint."""
    return {
        "status": "healthy",
        "service": "AP Auditor API",
        "version": "1.0.0",
        "docs": "/docs",
    }
