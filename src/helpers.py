"""Shared helpers for Family Budget (session, auth, templates, formatting)."""

import hashlib
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Request
from fastapi.templating import Jinja2Templates

# Load environment
load_dotenv(Path(__file__).parent.parent / ".env")

# Stripe donation payment links (override with env vars for production)
DONATION_LINKS = {
    10: os.getenv("STRIPE_DONATE_10", "https://buy.stripe.com/test_28E14hdiw6eb5Z70Jl9IQ00"),
    25: os.getenv("STRIPE_DONATE_25", "https://buy.stripe.com/test_aFa4gt3HW0TR0ENdw79IQ01"),
    50: os.getenv("STRIPE_DONATE_50", "https://buy.stripe.com/test_5kQ6oB5Q40TRevDfEf9IQ02"),
}


# Session management (file-based for persistence)
# Sessions map hashed tokens to user_ids
SESSIONS_FILE = Path(__file__).parent.parent / "data" / "sessions.json"


def hash_token(token: str) -> str:
    """Hash a session token for secure storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def load_sessions() -> dict:
    """Load sessions from file.

    Returns dict mapping hashed tokens to user_ids.
    Note: Basic implementation without locking for simplicity/portability,
    relying on atomic file operations if needed.
    """
    if SESSIONS_FILE.exists():
        try:
            with open(SESSIONS_FILE) as f:
                try:
                    data = json.load(f)
                    # Migrate from old format (list) to new format (dict)
                    if isinstance(data, list):
                        return {}  # Clear old sessions, users need to re-login
                    return data
                except (json.JSONDecodeError, OSError) as e:
                    logging.warning(f"Could not load sessions file: {e}")
        except Exception as e:
            logging.warning(f"Unexpected error loading sessions: {e}")
    return {}


def save_sessions(sessions: dict):
    """Save sessions to file.

    Writes to a temporary file and renames to prevent corruption.
    """
    SESSIONS_FILE.parent.mkdir(exist_ok=True)
    temp_file = SESSIONS_FILE.with_suffix(".tmp")
    with open(temp_file, 'w') as f:
        json.dump(sessions, f)
    # Atomic rename (on Unix, mostly on Windows too if file not open)
    try:
        if SESSIONS_FILE.exists():
            os.replace(temp_file, SESSIONS_FILE)
        else:
            temp_file.rename(SESSIONS_FILE)
    except OSError as e:
        logging.error(f"Failed to save sessions: {e}")


SESSIONS = load_sessions()  # Maps hashed tokens to user_ids

# Templates
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# =============================================================================
# Template helpers
# =============================================================================

def parse_danish_amount(amount_str: str) -> float:
    """Parse Danish currency format to float.

    Accepts:
    - "1234,50" -> 1234.50
    - "1.234,50" -> 1234.50
    - "1234.5" -> 1234.50
    - "1234" -> 1234.00

    Returns float with 2 decimal precision.
    Raises ValueError for invalid input.
    """
    if not amount_str or not isinstance(amount_str, str):
        raise ValueError("Invalid amount")

    # Remove whitespace
    amount_str = amount_str.strip()

    # Remove thousands separator (period)
    amount_str = amount_str.replace('.', '')

    # Replace comma with period for float parsing
    amount_str = amount_str.replace(',', '.')

    try:
        amount = float(amount_str)
        # Round to 2 decimals to prevent floating point errors
        return round(amount, 2)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid amount format: {amount_str}") from None


def format_currency(amount: float) -> str:
    """Format amount as Danish currency with 2 decimal places."""
    # Format: 1234.50 -> "1.234,50 kr"
    formatted = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return formatted + " kr"


def format_currency_short(amount: float) -> str:
    """Format amount as short Danish currency (no 'kr' suffix, no decimals for whole numbers)."""
    if amount == 0:
        return "0"
    if amount == int(amount):
        formatted = f"{int(amount):,}".replace(",", ".")
    else:
        formatted = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return formatted


# Add to Jinja2 globals
templates.env.globals["format_currency"] = format_currency
templates.env.globals["format_currency_short"] = format_currency_short


# =============================================================================
# Authentication helpers
# =============================================================================

DEMO_SESSION_ID = "demo"  # Special marker for demo mode


def check_auth(request: Request) -> bool:
    """Check if request is authenticated (including demo mode)."""
    session_id = request.cookies.get("budget_session")
    if not session_id:
        return False
    # Demo mode
    if session_id == DEMO_SESSION_ID:
        return True
    # Compare hashed token
    return hash_token(session_id) in SESSIONS


def get_user_id(request: Request) -> int | None:
    """Get user_id from session. Returns None for demo mode or invalid sessions."""
    session_id = request.cookies.get("budget_session")
    if not session_id or session_id == DEMO_SESSION_ID:
        return None
    hashed = hash_token(session_id)
    return SESSIONS.get(hashed)


def is_demo_mode(request: Request) -> bool:
    """Check if request is in demo mode (read-only)."""
    return request.cookies.get("budget_session") == DEMO_SESSION_ID


def is_demo_advanced(request: Request) -> bool:
    """Check if demo mode is set to advanced view."""
    return is_demo_mode(request) and request.cookies.get("demo_level") == "advanced"
