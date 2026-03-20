"""CRUD operations and aggregation for Family Budget.

All database I/O for domain entities lives here.
"""

import json
import sqlite3

from .connection import get_connection
from .models import (
    Account,
    Category,
    Expense,
    Income,
    PasswordResetToken,
    User,
)
from .schema import DEFAULT_CATEGORIES
from .security import hash_email, hash_password, verify_password

# =============================================================================
# Income operations
# =============================================================================

def get_all_income(user_id: int) -> list[Income]:
    """Get all income entries for a user."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, user_id, person, amount, frequency FROM income WHERE user_id = ? ORDER BY person",
            (user_id,)
        )
        rows = cur.fetchall()
    return [Income(**dict(row)) for row in rows]


def add_income(user_id: int, person: str, amount: float, frequency: str = 'monthly') -> int:
    """Add income entry for a user. Returns the new income ID."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO income (user_id, person, amount, frequency) VALUES (?, ?, ?, ?)",
            (user_id, person, amount, frequency)
        )
        income_id = cur.lastrowid
        conn.commit()
    return income_id


def update_income(user_id: int, person: str, amount: float, frequency: str = 'monthly'):
    """Update or insert income for a user.

    Uses INSERT ... ON CONFLICT for atomic upsert operation,
    which is thread-safe and more efficient than check-then-act.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO income (user_id, person, amount, frequency)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id, person) DO UPDATE SET amount = excluded.amount, frequency = excluded.frequency""",
            (user_id, person, amount, frequency)
        )
        conn.commit()


def get_total_income(user_id: int) -> float:
    """Get total monthly income for a user (converted to monthly equivalent)."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT COALESCE(SUM(
                CASE
                    WHEN frequency = 'monthly' THEN amount
                    WHEN frequency = 'quarterly' THEN amount / 3
                    WHEN frequency = 'semi-annual' THEN amount / 6
                    WHEN frequency = 'yearly' THEN amount / 12
                    ELSE amount
                END
            ), 0) FROM income WHERE user_id = ?
        """, (user_id,))
        total = cur.fetchone()[0]
    return total


def delete_all_income(user_id: int):
    """Delete all income entries for a user."""
    with get_connection() as conn:
        conn.execute("DELETE FROM income WHERE user_id = ?", (user_id,))
        conn.commit()


# =============================================================================
# Expense operations
# =============================================================================

def get_all_expenses(user_id: int) -> list[Expense]:
    """Get all expenses for a user."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, user_id, name, category, amount, frequency, account, months
            FROM expenses
            WHERE user_id = ?
            ORDER BY category, name
        """, (user_id,))
        rows = cur.fetchall()
    expenses = []
    for row in rows:
        d = dict(row)
        d['months'] = json.loads(d['months']) if d['months'] else None
        expenses.append(Expense(**d))
    return expenses


def get_expense_by_id(expense_id: int, user_id: int) -> Expense | None:
    """Get a specific expense for a user."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, user_id, name, category, amount, frequency, account, months FROM expenses WHERE id = ? AND user_id = ?",
            (expense_id, user_id)
        )
        row = cur.fetchone()
    if row is None:
        return None
    d = dict(row)
    d['months'] = json.loads(d['months']) if d['months'] else None
    return Expense(**d)


def add_expense(user_id: int, name: str, category: str, amount: float, frequency: str, account: str | None = None, months: list[int] | None = None) -> int:  # noqa: PLR0913
    """Add a new expense for a user. Returns the new expense ID."""
    with get_connection() as conn:
        cur = conn.cursor()
        months_json = json.dumps(months) if months else None
        cur.execute(
            """INSERT INTO expenses (user_id, name, category, amount, frequency, account, months)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, name, category, amount, frequency, account, months_json)
        )
        expense_id = cur.lastrowid
        conn.commit()
    return expense_id


def update_expense(expense_id: int, user_id: int, name: str, category: str, amount: float, frequency: str, account: str | None = None, months: list[int] | None = None):  # noqa: PLR0913
    """Update an existing expense for a user."""
    with get_connection() as conn:
        cur = conn.cursor()
        months_json = json.dumps(months) if months else None
        cur.execute(
            """UPDATE expenses
               SET name = ?, category = ?, amount = ?, frequency = ?, account = ?, months = ?
               WHERE id = ? AND user_id = ?""",
            (name, category, amount, frequency, account, months_json, expense_id, user_id)
        )
        conn.commit()


def delete_expense(expense_id: int, user_id: int):
    """Delete an expense for a user."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM expenses WHERE id = ? AND user_id = ?", (expense_id, user_id))
        conn.commit()


def get_total_monthly_expenses(user_id: int) -> float:
    """Get total monthly expenses for a user (converted to monthly equivalent)."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT COALESCE(SUM(
                CASE
                    WHEN frequency = 'monthly' THEN amount
                    WHEN frequency = 'quarterly' THEN amount / 3
                    WHEN frequency = 'semi-annual' THEN amount / 6
                    WHEN frequency = 'yearly' THEN amount / 12
                    ELSE amount
                END
            ), 0) FROM expenses WHERE user_id = ?
        """, (user_id,))
        total = cur.fetchone()[0]
    return total


def get_expenses_by_category(user_id: int) -> dict[str, list[Expense]]:
    """Get expenses grouped by category for a user."""
    expenses = get_all_expenses(user_id)
    grouped = {}
    for exp in expenses:
        if exp.category not in grouped:
            grouped[exp.category] = []
        grouped[exp.category].append(exp)
    return grouped


def get_category_totals(user_id: int) -> dict[str, float]:
    """Get total monthly amount per category for a user."""
    expenses = get_all_expenses(user_id)
    totals = {}
    for exp in expenses:
        if exp.category not in totals:
            totals[exp.category] = 0
        totals[exp.category] += exp.monthly_amount
    return totals


# =============================================================================
# Category operations
# =============================================================================

def get_all_categories(user_id: int) -> list[Category]:
    """Get all categories for a specific user."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, icon FROM categories WHERE user_id = ? ORDER BY name",
            (user_id,)
        )
        rows = cur.fetchall()
    return [Category(**dict(row)) for row in rows]


def get_category_by_id(category_id: int) -> Category | None:
    """Get a specific category."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name, icon FROM categories WHERE id = ?", (category_id,))
        row = cur.fetchone()
    return Category(**dict(row)) if row else None


def add_category(user_id: int, name: str, icon: str) -> int:
    """Add a new category for a user. Returns the new category ID."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO categories (user_id, name, icon) VALUES (?, ?, ?)",
            (user_id, name, icon)
        )
        category_id = cur.lastrowid
        conn.commit()
    return category_id


def update_category(category_id: int, user_id: int, name: str, icon: str) -> int:
    """Update an existing category for a user.

    Returns the number of expenses that were updated due to a name change.
    """
    with get_connection() as conn:
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
        conn.commit()
    return updated_expenses


def delete_category(category_id: int, user_id: int) -> bool:
    """Delete a category for a user. Returns False if category is in use or not owned.

    Uses a single connection to avoid race conditions between
    checking for usage and deleting.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM categories WHERE id = ? AND user_id = ?",
            (category_id, user_id)
        )
        row = cur.fetchone()
        if not row:
            return False

        category_name = row[0]

        cur.execute(
            "SELECT COUNT(*) FROM expenses WHERE (category_id = ? OR category = ?) AND user_id = ?",
            (category_id, category_name, user_id)
        )
        count = cur.fetchone()[0]
        if count > 0:
            return False

        cur.execute(
            "DELETE FROM categories WHERE id = ? AND user_id = ?",
            (category_id, user_id)
        )
        conn.commit()
        return True


def get_category_usage_count(category_name: str, user_id: int) -> int:
    """Get number of expenses using a category for a specific user.

    Checks both category_id (FK) and category (text) fields for backward compatibility.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT COUNT(*) FROM expenses
               WHERE user_id = ?
               AND (category = ? OR category_id = (SELECT id FROM categories WHERE name = ? AND user_id = ?))""",
            (user_id, category_name, category_name, user_id)
        )
        count = cur.fetchone()[0]
    return count


def ensure_default_categories(user_id: int):
    """Create default categories for a user if they don't exist."""
    with get_connection() as conn:
        cur = conn.cursor()
        for name, icon in DEFAULT_CATEGORIES:
            cur.execute(
                "INSERT OR IGNORE INTO categories (user_id, name, icon) VALUES (?, ?, ?)",
                (user_id, name, icon)
            )
        conn.commit()


def migrate_user_categories(user_id: int):
    """Migrate a user's expenses from text categories to category_id references.

    Creates user-specific category records for each distinct category in their expenses.
    Only creates categories that the user actually uses.
    """
    with get_connection() as conn:
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

        conn.commit()


# =============================================================================
# Account operations
# =============================================================================

def get_all_accounts(user_id: int) -> list[Account]:
    """Get all accounts for a specific user."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name FROM accounts WHERE user_id = ? ORDER BY name",
            (user_id,)
        )
        rows = cur.fetchall()
    return [Account(**dict(row)) for row in rows]


def get_account_by_id(account_id: int, user_id: int) -> Account | None:
    """Get a specific account for a user."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM accounts WHERE id = ? AND user_id = ?", (account_id, user_id))
        row = cur.fetchone()
    return Account(**dict(row)) if row else None


def add_account(user_id: int, name: str) -> int:
    """Add a new account for a user. Returns the new account ID."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO accounts (user_id, name) VALUES (?, ?)",
            (user_id, name)
        )
        account_id = cur.lastrowid
        conn.commit()
    return account_id


def update_account(account_id: int, user_id: int, name: str) -> int:
    """Update an existing account for a user.

    Returns the number of expenses that were updated due to a name change.
    """
    with get_connection() as conn:
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
        conn.commit()
    return updated_expenses


def delete_account(account_id: int, user_id: int) -> bool:
    """Delete an account for a user. Returns False if account is in use or not owned.

    Uses a single connection to avoid race conditions between
    checking for usage and deleting.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM accounts WHERE id = ? AND user_id = ?",
            (account_id, user_id)
        )
        row = cur.fetchone()
        if not row:
            return False

        account_name = row[0]

        cur.execute(
            "SELECT COUNT(*) FROM expenses WHERE account = ? AND user_id = ?",
            (account_name, user_id)
        )
        count = cur.fetchone()[0]
        if count > 0:
            return False

        cur.execute(
            "DELETE FROM accounts WHERE id = ? AND user_id = ?",
            (account_id, user_id)
        )
        conn.commit()
        return True


def get_account_usage_count(account_name: str, user_id: int) -> int:
    """Get number of expenses using an account for a specific user."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ? AND account = ?",
            (user_id, account_name)
        )
        count = cur.fetchone()[0]
    return count


def get_account_totals(user_id: int) -> dict[str, float]:
    """Get total monthly amount per account for a user."""
    expenses = get_all_expenses(user_id)
    totals = {}
    for exp in expenses:
        if exp.account:
            if exp.account not in totals:
                totals[exp.account] = 0
            totals[exp.account] += exp.monthly_amount
    return totals


# =============================================================================
# User operations
# =============================================================================

def create_user(
    username: str,
    password: str,
    email: str | None = None
) -> int | None:
    """Create a new user. Returns user ID or None if username exists.

    If email is provided, only its hash is stored for password reset lookup.
    The actual email is never stored.

    Uses try/except for IntegrityError to handle race conditions where
    another process might insert the same username between check and insert.
    """
    password_hash, salt = hash_password(password)

    email_hash_val = hash_email(email) if email else None

    with get_connection() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                """INSERT INTO users
                   (username, password_hash, salt, email_hash)
                   VALUES (?, ?, ?, ?)""",
                (username, password_hash, salt, email_hash_val)
            )
            user_id = cur.lastrowid
            conn.commit()
        except sqlite3.IntegrityError:
            return None

    ensure_default_categories(user_id)

    return user_id


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


# =============================================================================
# Aggregation
# =============================================================================

def _calculate_yearly_overview(expenses: list, income_entries: list) -> dict:
    """Shared aggregation logic for yearly overview.

    Args:
        expenses: List of Expense objects with get_monthly_amounts().
        income_entries: List of Income objects with get_monthly_amounts().

    Returns:
        dict with keys: categories, totals, income, balance, year_total.
    """
    categories: dict[str, dict[int, float]] = {}
    for exp in expenses:
        if exp.category not in categories:
            categories[exp.category] = {m: 0.0 for m in range(1, 13)}
        monthly = exp.get_monthly_amounts()
        for m in range(1, 13):
            categories[exp.category][m] += monthly[m]

    for cat in categories:
        for m in range(1, 13):
            categories[cat][m] = round(categories[cat][m], 2)

    totals = {m: round(sum(cat[m] for cat in categories.values()), 2) for m in range(1, 13)}

    income = {m: 0.0 for m in range(1, 13)}
    for inc in income_entries:
        monthly_amounts = inc.get_monthly_amounts()
        for m in range(1, 13):
            income[m] += monthly_amounts[m]
    for m in range(1, 13):
        income[m] = round(income[m], 2)

    balance = {m: round(income[m] - totals[m], 2) for m in range(1, 13)}
    year_total = round(sum(totals.values()), 2)

    return {
        'categories': categories,
        'totals': totals,
        'income': income,
        'balance': balance,
        'year_total': year_total,
    }


def get_yearly_overview(user_id: int) -> dict:
    """Calculate yearly overview with monthly breakdown.

    Returns dict with:
        categories: {category_name: {1: amount, 2: amount, ..., 12: amount}}
        totals: {1: total, ..., 12: total}
        income: {1: amount, ..., 12: amount}
        balance: {1: amount, ..., 12: amount}
        year_total: float (total expenses for the year)
    """
    return _calculate_yearly_overview(
        get_all_expenses(user_id),
        get_all_income(user_id),
    )
