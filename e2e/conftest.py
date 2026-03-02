"""Pytest fixtures for E2E tests with Playwright."""

import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def temp_db_path():
    """Create a temporary database for E2E tests."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_path = Path(f.name)
    yield temp_path
    if temp_path.exists():
        temp_path.unlink()


def wait_for_server(url: str, timeout: float = 30, interval: float = 0.5) -> bool:
    """Wait for server to be ready by polling the health endpoint."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            # Try to connect to the login page (always accessible)
            urllib.request.urlopen(f"{url}/budget/login", timeout=5)
            return True
        except (urllib.error.URLError, ConnectionRefusedError, TimeoutError):
            time.sleep(interval)
    return False


@pytest.fixture(scope="session")
def app_server(temp_db_path):
    """Start the FastAPI server for E2E tests.

    Uses a temporary database to ensure test isolation.
    """
    import os

    # Set environment to use temp database
    env = os.environ.copy()
    env["BUDGET_DB_PATH"] = str(temp_db_path)

    # Start server on random available port
    import socket
    with socket.socket() as s:
        s.bind(('', 0))
        port = s.getsockname()[1]

    project_root = Path(__file__).parent.parent
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.api:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=project_root,
        env=env,
        stdout=subprocess.DEVNULL,  # Don't buffer output
        stderr=subprocess.DEVNULL,
    )

    base_url = f"http://127.0.0.1:{port}"

    # Wait for server to actually be ready (with health check)
    if not wait_for_server(base_url, timeout=30):
        proc.terminate()
        proc.wait(timeout=5)
        raise RuntimeError(f"Server failed to start within 30 seconds on port {port}")

    # Check server is still running
    if proc.poll() is not None:
        raise RuntimeError("Server process died during startup")

    yield base_url

    # Cleanup
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Configure browser context for tests."""
    return {
        **browser_context_args,
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    }


@pytest.fixture(scope="session")
def base_url(app_server):
    """Provide base URL to tests."""
    return app_server


@pytest.fixture
def authenticated_page(page, base_url, request):
    """Page with a logged-in user session.

    Creates a unique test user per test and logs in before returning the page.
    """
    import uuid

    # Set reasonable timeouts for navigation
    page.set_default_timeout(60000)  # 60 seconds for actions
    page.set_default_navigation_timeout(60000)  # 60 seconds for navigation

    # Create unique username for this test
    unique_id = str(uuid.uuid4())[:8]
    username = f"e2euser_{unique_id}"

    # Register new user with retry logic
    max_retries = 3
    for attempt in range(max_retries):
        try:
            page.goto(f"{base_url}/budget/register", wait_until="domcontentloaded")
            page.fill('input[name="username"]', username)
            page.fill('input[name="password"]', "testpass123")
            page.fill('input[name="password_confirm"]', "testpass123")
            page.click('button[type="submit"]')

            # Should redirect to dashboard after registration
            page.wait_for_url(f"{base_url}/budget/", timeout=30000)
            break
        except Exception:
            if attempt == max_retries - 1:
                raise
            # Wait a bit before retrying
            time.sleep(1)
            # Generate new username for retry
            unique_id = str(uuid.uuid4())[:8]
            username = f"e2euser_{unique_id}"

    # Store user_id on page for tests that need it
    page.user_id = username

    return page
