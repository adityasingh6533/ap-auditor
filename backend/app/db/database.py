"""
Database connection and session management for AP Auditor.
Configures file-based SQLite database at backend/data/ap_auditor.db.
"""

from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3
from typing import Generator, Optional


def get_db_path() -> Path:
    """
    Returns the absolute path to the SQLite database file.
    Default: backend/data/ap_auditor.db
    """
    env_path = os.getenv("AP_AUDITOR_DB_PATH")
    if env_path:
        db_path = Path(env_path).resolve()
    else:
        # Resolve to backend/data/ap_auditor.db relative to this file
        base_dir = Path(__file__).resolve().parent.parent.parent
        db_path = base_dir / "data" / "ap_auditor.db"

    # Ensure parent directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def get_connection(db_path: Optional[Path | str] = None) -> sqlite3.Connection:
    """
    Creates and returns a new sqlite3 connection with standard settings.
    Enables foreign keys and row factory for dict-like access.
    """
    target_path = Path(db_path) if db_path else get_db_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        str(target_path),
        timeout=60.0,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn


@contextmanager
def get_db_cursor(db_path: Optional[Path | str] = None) -> Generator[sqlite3.Cursor, None, None]:
    """
    Context manager for database transactions.
    Yields cursor, commits automatically on completion, rolls back on error.
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def init_db(db_path: Optional[Path | str] = None) -> None:
    """
    Initializes database schema by executing table creation DDL.
    """
    from .models import create_tables
    conn = get_connection(db_path)
    try:
        create_tables(conn)
    finally:
        conn.close()
