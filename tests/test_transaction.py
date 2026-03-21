"""Tests for transaction() context manager."""

import sqlite3

from src.db.connection import transaction


class TestTransaction:
    """Tests for the transaction() context manager."""

    def test_auto_commit_on_success(self, temp_db):
        """transaction() without conn should auto-commit on success."""
        with transaction() as conn:
            conn.execute("INSERT INTO users (username, password_hash, salt) VALUES ('txtest', 'h', 's')")

        # Verify committed: open new connection, check data persists
        with transaction() as conn:
            row = conn.execute("SELECT username FROM users WHERE username = 'txtest'").fetchone()
        assert row is not None
        assert row[0] == "txtest"

    def test_auto_rollback_on_exception(self, temp_db):
        """transaction() without conn should rollback on exception."""
        try:
            with transaction() as conn:
                conn.execute("INSERT INTO users (username, password_hash, salt) VALUES ('txfail', 'h', 's')")
                raise ValueError("deliberate failure")
        except ValueError:
            pass

        # Verify rolled back
        with transaction() as conn:
            row = conn.execute("SELECT username FROM users WHERE username = 'txfail'").fetchone()
        assert row is None

    def test_passthrough_existing_conn(self, temp_db):
        """transaction(conn) should yield the same conn without commit/close."""
        with transaction() as outer:
            with transaction(outer) as inner:
                assert inner is outer
                inner.execute("INSERT INTO users (username, password_hash, salt) VALUES ('txpass', 'h', 's')")
            # inner did NOT commit - outer still owns the transaction
            # Rollback outer to prove inner didn't auto-commit
            outer.rollback()

        with transaction() as conn:
            row = conn.execute("SELECT username FROM users WHERE username = 'txpass'").fetchone()
        assert row is None

    def test_row_factory_set(self, temp_db):
        """transaction() should set row_factory to sqlite3.Row."""
        with transaction() as conn:
            assert conn.row_factory is sqlite3.Row
