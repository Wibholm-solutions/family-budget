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


def ensure_db_directory():
    """Ensure database directory exists. Called once at init."""
    DB_PATH.parent.mkdir(exist_ok=True)
