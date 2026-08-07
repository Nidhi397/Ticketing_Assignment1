"""
Lakebase (Databricks-managed Postgres) connection helper.

Connects using a single LAKEBASE_URL (a standard Postgres connection URL,
e.g. postgresql://role:password@host:5432/databricks_postgres?sslmode=require)
pointing at a native Postgres role with a static, non-expiring password.
The URL is fetched from a Databricks secret scope (see setup_secrets.py)
rather than kept in an env var, so no plaintext credential lives in app.yaml.

Exposes the same named functions as the OAuth-based version of this file
(get_all_tickets, create_ticket, etc.) so app.py works unchanged regardless
of which db.py is deployed - the generic run_query/run_write helpers are
kept underneath as reusable building blocks.
"""

import base64
import os
from contextlib import contextmanager

import psycopg2
from databricks.sdk import WorkspaceClient
from psycopg2.extras import RealDictCursor
from sqlalchemy import create_engine

SCHEMA = "ticketing_system"

_w = WorkspaceClient()

_SCOPE = os.environ.get("LAKEBASE_SECRET_SCOPE", "database")
_KEY = os.environ.get("LAKEBASE_SECRET_KEY", "lakebase-url")


def _lakebase_url() -> str:
    """Fetch and decode the Lakebase connection URL from the Databricks secret scope."""
    secret = _w.secrets.get_secret(scope=_SCOPE, key=_KEY)
    return base64.b64decode(secret.value).decode("utf-8")


@contextmanager
def get_connection():
    """Yield a raw psycopg2 connection with a RealDictCursor factory."""
    conn = psycopg2.connect(_lakebase_url(), cursor_factory=RealDictCursor)
    try:
        yield conn
    finally:
        conn.close()


def get_engine():
    """Return a SQLAlchemy engine for Lakebase."""
    return create_engine(_lakebase_url())


def run_query(sql: str, params: tuple | dict | None = None) -> list[dict]:
    """Run a read query against Lakebase and return rows as list[dict]."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def run_write(sql: str, params: tuple | dict | None = None) -> int:
    """Run an INSERT/UPDATE/DELETE against Lakebase, return affected row count."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
            return cur.rowcount


# ---------------------------------------------------------------------------
# Named functions used by app.py
# ---------------------------------------------------------------------------

def get_all_tickets():
    """Return all tickets, most recently created first."""
    return run_query(f"""
        SELECT ticket_id, title, status, created_by, created_at
        FROM {SCHEMA}.tickets
        ORDER BY created_at DESC
    """)


def get_ticket(ticket_id: int):
    rows = run_query(f"""
        SELECT ticket_id, title, status, created_by, created_at
        FROM {SCHEMA}.tickets
        WHERE ticket_id = %s
    """, (ticket_id,))
    return rows[0] if rows else None


def create_ticket(title: str, created_by: str, status: str = "open") -> int:
    """Insert a new ticket and return its generated ticket_id."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COALESCE(MAX(ticket_id), 0) + 1 FROM {SCHEMA}.tickets")
            new_id = cur.fetchone()["coalesce"]
            cur.execute(f"""
                INSERT INTO {SCHEMA}.tickets (ticket_id, title, status, created_by, created_at)
                VALUES (%s, %s, %s, %s, NOW())
            """, (new_id, title, status, created_by))
            conn.commit()
            return new_id


def update_ticket_status(ticket_id: int, status: str):
    run_write(f"""
        UPDATE {SCHEMA}.tickets
        SET status = %s
        WHERE ticket_id = %s
    """, (status, ticket_id))


def get_messages(ticket_id: int):
    return run_query(f"""
        SELECT message_id, ticket_id, message_text, author, author_role, created_at
        FROM {SCHEMA}.ticket_messages
        WHERE ticket_id = %s
        ORDER BY created_at ASC
    """, (ticket_id,))


def add_message(ticket_id: int, message_text: str, author: str, author_role: str) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COALESCE(MAX(message_id), 0) + 1 FROM {SCHEMA}.ticket_messages")
            new_id = cur.fetchone()["coalesce"]
            cur.execute(f"""
                INSERT INTO {SCHEMA}.ticket_messages
                    (message_id, ticket_id, message_text, author, author_role, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
            """, (new_id, ticket_id, message_text, author, author_role))
            conn.commit()
            return new_id


STATUS_OPTIONS = ["open", "in_progress", "resolved"]
ROLE_OPTIONS = ["customer", "representative"]