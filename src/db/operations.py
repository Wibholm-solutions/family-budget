"""Cross-domain operations with typed results.

Every function in this module touches 2+ entity tables in one transaction.
This is the audit surface for cross-domain effects.
"""

import sqlite3
from dataclasses import dataclass

from .connection import get_connection, transaction
from .models import Category
from .schema import DEFAULT_CATEGORIES
from .security import hash_email, hash_password

__all__ = [
    "CategoryUpdateResult",
    "DeleteResult",
    "create_user_with_default_categories",
    "delete_account_if_unused",
    "delete_category_if_unused",
    "migrate_user_categories",
    "rename_account_and_cascade_expenses",
    "rename_category_and_cascade_expenses",
]


@dataclass
class CategoryUpdateResult:
    """Result of a category rename operation."""
    cascaded_expense_count: int


@dataclass
class DeleteResult:
    """Result of a conditional delete operation."""
    deleted: bool
    reason: str  # "ok", "not_found", "in_use"


def rename_category_and_cascade_expenses(
    category_id: int, user_id: int, name: str, icon: str
) -> CategoryUpdateResult:
    """Update a category and cascade the name change to all its expenses."""
    with transaction() as conn:
        cur = conn.cursor()
        updated_expenses = 0
        cur.execute(
            "SELECT name FROM categories WHERE id = ? AND user_id = ?",
            (category_id, user_id)
        )
        row = cur.fetchone()
        if row:
            old_name = row[0]
            if old_name != name:
                cur.execute(
                    "UPDATE expenses SET category = ? WHERE category = ? AND user_id = ?",
                    (name, old_name, user_id)
                )
                updated_expenses = cur.rowcount

        cur.execute(
            "UPDATE categories SET name = ?, icon = ? WHERE id = ? AND user_id = ?",
            (name, icon, category_id, user_id)
        )
    return CategoryUpdateResult(cascaded_expense_count=updated_expenses)


def delete_category_if_unused(category_id: int, user_id: int) -> DeleteResult:
    """Delete a category only if no expenses reference it."""
    with transaction() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM categories WHERE id = ? AND user_id = ?",
            (category_id, user_id)
        )
        row = cur.fetchone()
        if not row:
            return DeleteResult(deleted=False, reason="not_found")

        category_name = row[0]

        cur.execute(
            "SELECT COUNT(*) FROM expenses WHERE (category_id = ? OR category = ?) AND user_id = ?",
            (category_id, category_name, user_id)
        )
        count = cur.fetchone()[0]
        if count > 0:
            return DeleteResult(deleted=False, reason="in_use")

        cur.execute(
            "DELETE FROM categories WHERE id = ? AND user_id = ?",
            (category_id, user_id)
        )
    return DeleteResult(deleted=True, reason="ok")


def rename_account_and_cascade_expenses(
    account_id: int, user_id: int, name: str
) -> int:
    """Update an account and cascade the name change to all its expenses.

    Returns the number of expenses updated.
    """
    with transaction() as conn:
        cur = conn.cursor()
        updated_expenses = 0
        cur.execute(
            "SELECT name FROM accounts WHERE id = ? AND user_id = ?",
            (account_id, user_id)
        )
        row = cur.fetchone()
        if row:
            old_name = row[0]
            if old_name != name:
                cur.execute(
                    "UPDATE expenses SET account = ? WHERE account = ? AND user_id = ?",
                    (name, old_name, user_id)
                )
                updated_expenses = cur.rowcount

        cur.execute(
            "UPDATE accounts SET name = ? WHERE id = ? AND user_id = ?",
            (name, account_id, user_id)
        )
    return updated_expenses


def delete_account_if_unused(account_id: int, user_id: int) -> DeleteResult:
    """Delete an account only if no expenses reference it."""
    with transaction() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM accounts WHERE id = ? AND user_id = ?",
            (account_id, user_id)
        )
        row = cur.fetchone()
        if not row:
            return DeleteResult(deleted=False, reason="not_found")

        account_name = row[0]

        cur.execute(
            "SELECT COUNT(*) FROM expenses WHERE account = ? AND user_id = ?",
            (account_name, user_id)
        )
        count = cur.fetchone()[0]
        if count > 0:
            return DeleteResult(deleted=False, reason="in_use")

        cur.execute(
            "DELETE FROM accounts WHERE id = ? AND user_id = ?",
            (account_id, user_id)
        )
    return DeleteResult(deleted=True, reason="ok")


def create_user_with_default_categories(
    username: str, password: str, email: str | None = None
) -> int | None:
    """Create user + seed categories in ONE transaction.

    Returns user ID or None if username already exists.
    """
    password_hash, salt = hash_password(password)
    email_hash_val = hash_email(email) if email else None

    with transaction() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                """INSERT INTO users
                   (username, password_hash, salt, email_hash)
                   VALUES (?, ?, ?, ?)""",
                (username, password_hash, salt, email_hash_val)
            )
            user_id = cur.lastrowid
        except sqlite3.IntegrityError:
            return None

        # Seed default categories in same transaction
        for name, icon in DEFAULT_CATEGORIES:
            cur.execute(
                "INSERT OR IGNORE INTO categories (user_id, name, icon) VALUES (?, ?, ?)",
                (user_id, name, icon)
            )

    return user_id


def migrate_user_categories(user_id: int):
    """Migrate a user's expenses from text categories to category_id references.

    Creates user-specific category records for each distinct category in their expenses.
    """
    with transaction() as conn:
        cur = conn.cursor()

        cur.execute(
            "SELECT DISTINCT category FROM expenses WHERE user_id = ? AND category_id IS NULL",
            (user_id,)
        )
        used_categories = [row[0] for row in cur.fetchall()]

        for cat_name in used_categories:
            cur.execute("SELECT icon FROM categories WHERE name = ? AND user_id = 0", (cat_name,))
            row = cur.fetchone()
            icon = row[0] if row else "more-horizontal"

            cur.execute(
                "INSERT OR IGNORE INTO categories (user_id, name, icon) VALUES (?, ?, ?)",
                (user_id, cat_name, icon)
            )

            cur.execute(
                "SELECT id FROM categories WHERE user_id = ? AND name = ?",
                (user_id, cat_name)
            )
            category_id = cur.fetchone()[0]

            cur.execute(
                "UPDATE expenses SET category_id = ? WHERE user_id = ? AND category = ? AND category_id IS NULL",
                (category_id, user_id, cat_name)
            )
