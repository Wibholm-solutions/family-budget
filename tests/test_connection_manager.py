"""Tests for get_connection() context manager safety."""
import sqlite3
from unittest.mock import MagicMock, patch, call
import pytest


class TestGetConnectionContextManager:
    """Verify get_connection() is a context manager that prevents leaks."""

    def test_get_connection_is_context_manager(self, db_module):
        """get_connection() must be usable as a context manager."""
        with db_module.get_connection() as conn:
            assert conn is not None
            assert isinstance(conn, sqlite3.Connection)

    def test_connection_closed_on_normal_exit(self, db_module):
        """Connection must be closed after normal with-block exit."""
        with db_module.get_connection() as conn:
            captured = conn  # hold reference outside

        # After the with block, executing on the closed connection should fail
        with pytest.raises(Exception):
            captured.execute("SELECT 1")

    def test_connection_closed_on_exception(self, db_module):
        """Connection must be closed even when the with-block raises."""
        captured = None
        with pytest.raises(ValueError):
            with db_module.get_connection() as conn:
                captured = conn
                raise ValueError("simulated failure")

        # Connection should be closed despite the exception
        with pytest.raises(Exception):
            captured.execute("SELECT 1")

    def test_row_factory_set(self, db_module):
        """Connection must have row_factory = sqlite3.Row."""
        with db_module.get_connection() as conn:
            assert conn.row_factory is sqlite3.Row
