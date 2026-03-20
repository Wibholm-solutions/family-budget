"""Cryptographic operations for Family Budget.

Contains password hashing (PBKDF2) and email hashing (SHA-256).
Auditable in isolation — no database or I/O dependencies.
"""

import hashlib
import secrets

# OWASP recommends 600,000 iterations for PBKDF2-HMAC-SHA256 (2023)
PBKDF2_ITERATIONS = 600_000


def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    """Hash password with PBKDF2. Returns (hash, salt) as hex strings."""
    if salt is None:
        salt = secrets.token_bytes(32)
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, PBKDF2_ITERATIONS)
    return hashed.hex(), salt.hex()


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """Verify password against stored hash."""
    new_hash, _ = hash_password(password, bytes.fromhex(salt))
    return secrets.compare_digest(new_hash, stored_hash)


def hash_email(email: str) -> str:
    """Hash email for lookup (case-insensitive). Returns hex string."""
    return hashlib.sha256(email.lower().strip().encode()).hexdigest()
