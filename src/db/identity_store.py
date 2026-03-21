"""User, authentication, and password reset token CRUD.

Self-contained auth module - no budget imports.
Cross-domain operations (create_user + seed categories) live in operations.py.
"""

import sqlite3

from .connection import get_connection
from .models import PasswordResetToken, User
from .security import hash_email, hash_password, verify_password

__all__ = [
    "authenticate_user",
    "create_password_reset_token",
    "get_user_by_email",
    "get_user_by_id",
    "get_user_by_username",
    "get_user_count",
    "get_valid_reset_token",
    "mark_reset_token_used",
    "update_last_login",
    "update_user_email",
    "update_user_password",
]


# =============================================================================
# User operations
# =============================================================================

def get_user_by_username(username: str) -> User | None:
    """Get user by username."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, username, password_hash, salt, email_hash
               FROM users WHERE username = ?""",
            (username,)
        )
        row = cur.fetchone()
    return User(**dict(row)) if row else None


def get_user_by_email(email: str) -> User | None:
    """Get user by email hash (for password reset lookup).

    This function finds the user by their email hash. The actual email
    is never stored - only the hash is kept for verification.
    """
    email_hash_val = hash_email(email)
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, username, password_hash, salt, email_hash
               FROM users WHERE email_hash = ?""",
            (email_hash_val,)
        )
        row = cur.fetchone()
    return User(**dict(row)) if row else None


def get_user_by_id(user_id: int) -> User | None:
    """Get user by ID."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, username, password_hash, salt, email_hash
               FROM users WHERE id = ?""",
            (user_id,)
        )
        row = cur.fetchone()
    return User(**dict(row)) if row else None


def update_user_email(user_id: int, email: str):
    """Update email hash for a user.

    Only the email hash is stored for password reset verification.
    The actual email is never stored.
    """
    with get_connection() as conn:
        if not email:
            conn.execute(
                "UPDATE users SET email_hash = NULL WHERE id = ?",
                (user_id,)
            )
        else:
            email_hash_val = hash_email(email)
            conn.execute(
                "UPDATE users SET email_hash = ? WHERE id = ?",
                (email_hash_val, user_id)
            )
        conn.commit()


def update_user_password(user_id: int, password: str):
    """Update password for a user."""
    password_hash, salt = hash_password(password)
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, salt = ? WHERE id = ?",
            (password_hash, salt, user_id)
        )
        conn.commit()


def authenticate_user(username: str, password: str) -> User | None:
    """Authenticate user. Returns User if successful, None otherwise."""
    user = get_user_by_username(username)
    if user and verify_password(password, user.password_hash, user.salt):
        return user
    return None


def update_last_login(user_id: int):
    """Update last_login timestamp for a user."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
            (user_id,)
        )
        conn.commit()


def get_user_count() -> int:
    """Get total number of registered users."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        count = cur.fetchone()[0]
    return count


# =============================================================================
# Password reset token operations
# =============================================================================

def create_password_reset_token(user_id: int, token_hash: str, expires_at: str) -> int:
    """Create a password reset token. Returns token ID."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE password_reset_tokens SET used = 1 WHERE user_id = ?", (user_id,))
        cur.execute(
            """INSERT INTO password_reset_tokens (user_id, token_hash, expires_at)
               VALUES (?, ?, ?)""",
            (user_id, token_hash, expires_at)
        )
        token_id = cur.lastrowid
        conn.commit()
    return token_id


def get_valid_reset_token(token_hash: str) -> PasswordResetToken | None:
    """Get a valid (unused, not expired) reset token."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, user_id, token_hash, expires_at, used
               FROM password_reset_tokens
               WHERE token_hash = ? AND used = 0 AND expires_at > datetime('now')""",
            (token_hash,)
        )
        row = cur.fetchone()
    if row:
        return PasswordResetToken(
            id=row[0], user_id=row[1], token_hash=row[2],
            expires_at=row[3], used=bool(row[4])
        )
    return None


def mark_reset_token_used(token_id: int):
    """Mark a reset token as used."""
    with get_connection() as conn:
        conn.execute("UPDATE password_reset_tokens SET used = 1 WHERE id = ?", (token_id,))
        conn.commit()
