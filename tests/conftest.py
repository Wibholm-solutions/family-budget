"""Pytest fixtures for Family Budget tests."""

import secrets
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="function")
def temp_db():
    """Create a temporary database for testing.

    Each test gets a fresh database to ensure isolation.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_path = Path(f.name)

    # Re-initialize database with the temp path
    from src import database as db
    db.DB_PATH = temp_path
    db.init_db()

    yield temp_path

    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture(scope="function")
def db_module(temp_db):
    """Get database module with temporary database."""
    from src import database as db
    db.DB_PATH = temp_db
    return db


@pytest.fixture(scope="function")
def client(temp_db):
    """Create a test client with fresh database and sessions."""
    from src import api
    from src import database as db

    # Reset database path
    db.DB_PATH = temp_db

    # Clear sessions for fresh state
    api.SESSIONS.clear()

    # Create test client
    with TestClient(api.app) as c:
        yield c


@pytest.fixture
def authenticated_client(client, db_module):
    """Test client with an authenticated session.

    Note: We manually create and register a session because
    the secure cookie flag prevents TestClient from storing
    cookies (it uses HTTP, not HTTPS).
    """
    from src import api

    # Create a test user
    user_id = db_module.create_user("testuser", "testpass123")

    # Create session manually (bypassing secure cookie issue)
    session_id = secrets.token_urlsafe(32)
    api.SESSIONS[api.hash_token(session_id)] = user_id

    # Set cookie on client
    client.cookies.set("budget_session", session_id)

    # Store user_id on client for tests that need it
    client.user_id = user_id

    return client
