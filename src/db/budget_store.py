"""Single-table budget CRUD and aggregation.

Each function in this module touches exactly one entity's table.
Cross-domain operations live in operations.py.
"""

import json

from .connection import get_connection
from .models import Account, Category, Expense, Income
from .schema import DEFAULT_CATEGORIES

__all__ = [
    "_calculate_yearly_overview",
    "add_account",
    "add_category",
    "add_expense",
    "add_income",
    "delete_all_income",
    "delete_expense",
    "ensure_default_categories",
    "get_account_by_id",
    "get_account_totals",
    "get_account_usage_count",
    "get_all_accounts",
    "get_all_categories",
    "get_all_expenses",
    "get_all_income",
    "get_category_by_id",
    "get_category_totals",
    "get_category_usage_count",
    "get_expense_by_id",
    "get_expenses_by_category",
    "get_total_income",
    "get_total_monthly_expenses",
    "get_yearly_overview",
    "update_expense",
    "update_income",
]


# =============================================================================
# Income operations
# =============================================================================

def get_all_income(user_id: int) -> list[Income]:
    """Get all income entries for a user."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, user_id, person, source, amount, frequency FROM income WHERE user_id = ? ORDER BY person, source",
            (user_id,)
        )
        rows = cur.fetchall()
    return [Income(**dict(row)) for row in rows]


def add_income(user_id: int, person: str, amount: float, frequency: str = 'monthly', source: str = 'Løn') -> int:
    """Add income entry for a user. Returns the new income ID."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO income (user_id, person, source, amount, frequency) VALUES (?, ?, ?, ?, ?)",
            (user_id, person, source, amount, frequency)
        )
        income_id = cur.lastrowid
        conn.commit()
    return income_id


def update_income(user_id: int, person: str, amount: float, frequency: str = 'monthly', source: str = 'Løn'):
    """Update or insert income for a user.

    Uses INSERT ... ON CONFLICT for atomic upsert operation,
    which is thread-safe and more efficient than check-then-act.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO income (user_id, person, source, amount, frequency)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(user_id, person, source) DO UPDATE SET amount = excluded.amount, frequency = excluded.frequency""",
            (user_id, person, source, amount, frequency)
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
# Category operations (single-table only)
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


# =============================================================================
# Account operations (single-table only)
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
