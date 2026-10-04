"""
Main FastAPI entrypoint for the AP Auditor Backend Application.
Provides RESTful APIs for invoice auditing, exception review workflows, audit trails, and reporting.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import audit, chat, exceptions, invoices, stats
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
