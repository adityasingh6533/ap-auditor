"""
Database schema models and table definitions for AP Auditor.
Defines 'invoices' and immutable 'audit_log' tables using raw SQLite DDL.
Includes SHA-256 cryptographic integrity hash for audit trail immutability.
"""

import hashlib
import sqlite3


CREATE_INVOICES_TABLE = """
CREATE TABLE IF NOT EXISTS invoices (
    invoice_id TEXT PRIMARY KEY,
    vendor_name TEXT,
    amount REAL,
    category TEXT,
    status TEXT NOT NULL,
    confidence_score REAL,
    triggered_checks TEXT,
    reason_text TEXT,
    matched_reference TEXT,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_AUDIT_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS audit_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id TEXT NOT NULL,
    action TEXT NOT NULL,
    performed_by TEXT NOT NULL,
    reason TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    integrity_hash TEXT
);
"""

CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);
CREATE INDEX IF NOT EXISTS idx_invoices_vendor ON invoices(vendor_name);
CREATE INDEX IF NOT EXISTS idx_audit_log_invoice_id ON audit_log(invoice_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp);
"""


def compute_audit_hash(invoice_id: str, action: str, performed_by: str, reason: str, timestamp: str) -> str:
    """
    Computes a cryptographic SHA-256 digest over the core audit fields:
    (invoice_id + action + performed_by + reason + timestamp)
    """
    payload = f"{str(invoice_id).strip()}{str(action).strip()}{str(performed_by).strip()}{str(reason or '').strip()}{str(timestamp).strip()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def create_tables(conn: sqlite3.Connection) -> None:
    """
    Executes table creation DDL on the provided SQLite connection and
    ensures migration for the integrity_hash column exists.
    """
    with conn:
        conn.execute(CREATE_INVOICES_TABLE)
        conn.execute(CREATE_AUDIT_LOG_TABLE)
        conn.executescript(CREATE_INDEXES)

        # Check if integrity_hash column exists; add if missing
        cur = conn.execute("PRAGMA table_info(audit_log)")
        columns = [row[1] for row in cur.fetchall()]
        if "integrity_hash" not in columns:
            conn.execute("ALTER TABLE audit_log ADD COLUMN integrity_hash TEXT")

        # Backfill any existing audit_log rows that lack an integrity_hash
        unhashed = conn.execute(
            "SELECT log_id, invoice_id, action, performed_by, reason, timestamp FROM audit_log WHERE integrity_hash IS NULL"
        ).fetchall()
        if unhashed:
            updates = []
            for row in unhashed:
                lid, inv_id, action, perf, reason, ts = row
                digest = compute_audit_hash(inv_id, action, perf, reason, ts)
                updates.append((digest, lid))
            conn.executemany("UPDATE audit_log SET integrity_hash = ? WHERE log_id = ?", updates)
