"""Database connection management."""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(os.environ.get("BUDGET_DB_PATH", Path(__file__).parent.parent.parent / "data" / "budget.db"))


@contextmanager
def get_connection():
    """Get database connection as a context manager. Always closes on exit."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction(conn=None):
    """Yield a connection inside a transaction.

    If conn is provided, yield it as-is (caller owns commit/rollback).
    If conn is None, open a new connection, commit on success, rollback on exception.
    """
    if conn is not None:
        yield conn
        return
    new_conn = sqlite3.connect(DB_PATH)
    new_conn.row_factory = sqlite3.Row
    try:
        yield new_conn
        new_conn.commit()
    except BaseException:
        new_conn.rollback()
        raise
    finally:
        new_conn.close()


def ensure_db_directory():
    """Ensure database directory exists. Called once at init."""
    DB_PATH.parent.mkdir(exist_ok=True)
