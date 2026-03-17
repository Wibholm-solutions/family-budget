"""SQLite database operations for Family Budget."""

import hashlib
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

DB_PATH = Path(os.environ.get("BUDGET_DB_PATH", Path(__file__).parent.parent / "data" / "budget.db"))


# =============================================================================
# Password hashing (using PBKDF2 for simplicity, no extra dependencies)
# =============================================================================

# OWASP recommends 600,000 iterations for PBKDF2-HMAC-SHA256 (2023)
# https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
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


# =============================================================================
# Email hashing (SHA-256 for anonymous lookup)
# =============================================================================

def hash_email(email: str) -> str:
    """Hash email for lookup (case-insensitive). Returns hex string.

    The email is hashed with SHA-256 for privacy-preserving lookup.
    The actual email is never stored - only the hash is kept for verification.
    """
    return hashlib.sha256(email.lower().strip().encode()).hexdigest()


# Pre-defined categories with icons
DEFAULT_CATEGORIES = [
    ("Bolig", "house"),
    ("Forbrug", "zap"),
    ("Transport", "car"),
    ("Børn", "baby"),
    ("Mad", "utensils"),
    ("Forsikring", "shield"),
    ("Abonnementer", "tv"),
    ("Opsparing", "piggy-bank"),
    ("Andet", "more-horizontal"),
]

# Demo data - typical Danish household budget
DEMO_INCOME = [
    # (person, amount, frequency, months)
    ("Person 1", 28000, "monthly", None),
    ("Person 2", 22000, "monthly", None),
    ("Bonus", 30000, "semi-annual", [6, 12]),  # Bonus in June & December
]

DEMO_EXPENSES = [
    # (name, category, amount, frequency, months)
    # months=None means spread evenly; months=[...] means pay in those specific months
    ("Husleje/boliglån", "Bolig", 12000, "monthly", None),
    ("Ejendomsskat", "Bolig", 18000, "yearly", [1, 7]),  # Paid in Jan & Jul
    ("Varme", "Forbrug", 800, "monthly", None),
    ("El", "Forbrug", 600, "monthly", None),
    ("Vand", "Forbrug", 2400, "quarterly", [3, 6, 9, 12]),  # Quarterly water bill
    ("Internet", "Forbrug", 299, "monthly", None),
    ("Bil - lån", "Transport", 2500, "monthly", None),
    ("Benzin", "Transport", 1500, "monthly", None),
    ("Vægtafgift", "Transport", 3600, "yearly", [4]),  # Paid in April
    ("Bilforsikring", "Transport", 6000, "yearly", [2]),  # Paid in February
    ("Bilservice", "Transport", 4500, "semi-annual", [3, 9]),  # Service in Mar & Sep
    ("Institution", "Børn", 3200, "monthly", None),
    ("Fritidsaktiviteter", "Børn", 2400, "semi-annual", [1, 8]),  # Season start Jan & Aug
    ("Dagligvarer", "Mad", 6000, "monthly", None),
    ("Indboforsikring", "Forsikring", 1800, "yearly", [6]),  # Paid in June
    ("Ulykkesforsikring", "Forsikring", 1200, "yearly", [6]),  # Paid in June
    ("Tandlægeforsikring", "Forsikring", 600, "quarterly", [3, 6, 9, 12]),  # Quarterly dental
    ("Netflix", "Abonnementer", 129, "monthly", None),
    ("Spotify", "Abonnementer", 99, "monthly", None),
    ("Fitness", "Abonnementer", 299, "monthly", None),
    ("Opsparing", "Opsparing", 3000, "monthly", None),
    ("Telefon", "Andet", 199, "monthly", None),
]

# Advanced demo data - adds account assignments and extra income
DEMO_INCOME_ADVANCED = [
    # (person, amount, frequency, months)
    ("Person 1", 28000, "monthly", None),
    ("Person 2", 22000, "monthly", None),
    ("Bonus", 30000, "semi-annual", [6, 12]),
    ("Børnepenge", 6264, "quarterly", [1, 4, 7, 10]),
]

DEMO_EXPENSES_ADVANCED = [
    # (name, category, amount, frequency, account, months)
    ("Husleje/boliglån", "Bolig", 12000, "monthly", "Budgetkonto", None),
    ("Ejendomsskat", "Bolig", 18000, "yearly", "Budgetkonto", [1, 7]),
    ("Varme", "Forbrug", 800, "monthly", "Budgetkonto", None),
    ("El", "Forbrug", 600, "monthly", "Budgetkonto", None),
    ("Vand", "Forbrug", 2400, "quarterly", "Budgetkonto", [3, 6, 9, 12]),
    ("Internet", "Forbrug", 299, "monthly", "Budgetkonto", None),
    ("Bil - lån", "Transport", 2500, "monthly", "Budgetkonto", None),
    ("Benzin", "Transport", 1500, "monthly", "Forbrugskonto", None),
    ("Vægtafgift", "Transport", 3600, "yearly", "Budgetkonto", [4]),
    ("Bilforsikring", "Transport", 6000, "yearly", "Budgetkonto", [2]),
    ("Bilservice", "Transport", 4500, "semi-annual", "Budgetkonto", [3, 9]),
    ("Institution", "Børn", 3200, "monthly", "Budgetkonto", None),
    ("Fritidsaktiviteter", "Børn", 2400, "semi-annual", "Forbrugskonto", [1, 8]),
    ("Dagligvarer", "Mad", 6000, "monthly", "Forbrugskonto", None),
    ("Indboforsikring", "Forsikring", 1800, "yearly", "Budgetkonto", [6]),
    ("Ulykkesforsikring", "Forsikring", 1200, "yearly", "Budgetkonto", [6]),
    ("Tandlægeforsikring", "Forsikring", 600, "quarterly", "Budgetkonto", [3, 6, 9, 12]),
    ("Netflix", "Abonnementer", 129, "monthly", "Person 1 konto", None),
    ("Spotify", "Abonnementer", 99, "monthly", "Person 2 konto", None),
    ("Fitness", "Abonnementer", 299, "monthly", "Person 1 konto", None),
    ("Opsparing", "Opsparing", 3000, "monthly", "Opsparingskonto", None),
    ("Telefon", "Andet", 199, "monthly", "Person 2 konto", None),
]


@dataclass
class Income:
    id: int
    user_id: int
    person: str
    amount: float
    frequency: str = 'monthly'  # 'monthly', 'quarterly', 'semi-annual', or 'yearly'
    months: list[int] | None = None  # Which months this income falls in (1-12)

    @property
    def monthly_amount(self) -> float:
        """Return the monthly equivalent amount with 2 decimal precision."""
        divisors = {'monthly': 1, 'quarterly': 3, 'semi-annual': 6, 'yearly': 12}
        result = self.amount / divisors.get(self.frequency, 1)
        return round(result, 2)

    def get_monthly_amounts(self) -> dict[int, float]:
        """Return a dict mapping month (1-12) to the amount for that month."""
        result = {m: 0.0 for m in range(1, 13)}
        if self.frequency == 'monthly' or self.months is None:
            monthly = self.monthly_amount
            for m in range(1, 13):
                result[m] = monthly
        else:
            per_month = round(self.amount / len(self.months), 2)
            for m in self.months:
                result[m] = per_month
        return result


@dataclass
class Expense:
    id: int
    user_id: int
    name: str
    category: str
    amount: float
    frequency: str  # 'monthly', 'quarterly', 'semi-annual', or 'yearly'
    account: str | None = None  # Optional bank account assignment
    months: list[int] | None = None  # Which months this expense falls in (1-12)

    @property
    def monthly_amount(self) -> float:
        """Return the monthly equivalent amount with 2 decimal precision."""
        divisors = {'monthly': 1, 'quarterly': 3, 'semi-annual': 6, 'yearly': 12}
        result = self.amount / divisors.get(self.frequency, 1)
        return round(result, 2)

    def get_monthly_amounts(self) -> dict[int, float]:
        """Return a dict mapping month (1-12) to the amount for that month.

        If months is set, the total amount is split equally across those months.
        If months is None (default), the monthly_amount is spread evenly across all 12 months.
        Monthly expenses always spread evenly regardless of months setting.
        """
        result = {m: 0.0 for m in range(1, 13)}

        if self.frequency == 'monthly' or self.months is None:
            # Spread evenly across all 12 months
            monthly = self.monthly_amount
            for m in range(1, 13):
                result[m] = monthly
        else:
            # Split total amount across specified months
            per_month = round(self.amount / len(self.months), 2)
            for m in self.months:
                result[m] = per_month

        return result


@dataclass
class Account:
    id: int
    name: str


@dataclass
class Category:
    id: int
    name: str
    icon: str


@dataclass
class User:
    id: int
    username: str
    password_hash: str
    salt: str
    email_hash: str = None

    def has_email(self) -> bool:
        """Check if user has an email hash set (for password reset)."""
        return bool(self.email_hash)


@dataclass
class PasswordResetToken:
    id: int
    user_id: int
    token_hash: str
    expires_at: str
    used: bool = False


@contextmanager
def get_connection():
    """Get database connection as a context manager. Always closes on exit."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def ensure_db_directory():
    """Ensure database directory exists. Called once at init."""
    DB_PATH.parent.mkdir(exist_ok=True)


def _create_tables(cur) -> None:
    """Create all database tables and indexes if they don't exist."""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            email_hash TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS income (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            person TEXT NOT NULL,
            amount REAL NOT NULL DEFAULT 0,
            frequency TEXT NOT NULL DEFAULT 'monthly' CHECK(frequency IN ('monthly', 'quarterly', 'semi-annual', 'yearly')),
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, person)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            icon TEXT,
            UNIQUE(user_id, name)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_categories_user ON categories(user_id, name)")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            frequency TEXT NOT NULL CHECK(frequency IN ('monthly', 'quarterly', 'semi-annual', 'yearly')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            category_id INTEGER REFERENCES categories(id),
            account TEXT,
            months TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category_id)")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            UNIQUE(user_id, name)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_accounts_user ON accounts(user_id, name)")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            used INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)


def _seed_default_categories(cur) -> None:
    """Insert default categories for the demo user (user_id = 0)."""
    for name, icon in DEFAULT_CATEGORIES:
        cur.execute(
            "INSERT OR IGNORE INTO categories (user_id, name, icon) VALUES (?, ?, ?)",
            (0, name, icon)
        )


def init_db():
    """Initialize database with schema and default data."""
    ensure_db_directory()
    with get_connection() as conn:
        cur = conn.cursor()
        _create_tables(cur)
        _seed_default_categories(cur)
        conn.commit()


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
        # Also update expenses that use this category (by name, for backward compatibility)
        cur.execute(
            "SELECT name FROM categories WHERE id = ? AND user_id = ?",
            (category_id, user_id)
        )
        row = cur.fetchone()
        if row:
            old_name = row[0]
            if old_name != name:
                # Update expense text names for backward compatibility
                cur.execute(
                    "UPDATE expenses SET category = ? WHERE category = ? AND user_id = ?",
                    (name, old_name, user_id)
                )
                updated_expenses = cur.rowcount

        # Update the category
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
        # Check category exists and belongs to user, get name for text-based check
        cur.execute(
            "SELECT name FROM categories WHERE id = ? AND user_id = ?",
            (category_id, user_id)
        )
        row = cur.fetchone()
        if not row:
            return False

        category_name = row[0]

        # Check if any expenses use this category (by category_id or by text name for backward compatibility)
        cur.execute(
            "SELECT COUNT(*) FROM expenses WHERE (category_id = ? OR category = ?) AND user_id = ?",
            (category_id, category_name, user_id)
        )
        count = cur.fetchone()[0]
        if count > 0:
            return False

        # Delete the category
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

        # Get distinct categories used by this user
        cur.execute(
            "SELECT DISTINCT category FROM expenses WHERE user_id = ? AND category_id IS NULL",
            (user_id,)
        )
        used_categories = [row[0] for row in cur.fetchall()]

        for cat_name in used_categories:
            # Get icon from demo category (user_id=0) or use default
            cur.execute("SELECT icon FROM categories WHERE name = ? AND user_id = 0", (cat_name,))
            row = cur.fetchone()
            icon = row[0] if row else "more-horizontal"

            # Create user-specific category
            cur.execute(
                "INSERT OR IGNORE INTO categories (user_id, name, icon) VALUES (?, ?, ?)",
                (user_id, cat_name, icon)
            )

            # Get the category_id
            cur.execute(
                "SELECT id FROM categories WHERE user_id = ? AND name = ?",
                (user_id, cat_name)
            )
            category_id = cur.fetchone()[0]

            # Update expenses to use category_id
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
    # Hash password
    password_hash, salt = hash_password(password)

    # Hash email if provided (only hash is stored, not the email itself)
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
            # Username already exists (caught via UNIQUE constraint)
            return None

    # Create default categories for new user
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
            # Clear email hash if not provided
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
        # Invalidate any existing tokens for this user
        cur.execute("UPDATE password_reset_tokens SET used = 1 WHERE user_id = ?", (user_id,))
        # Create new token
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
# Demo data functions (returns in-memory data, not from database)
# =============================================================================

def _calculate_yearly_overview(expenses: list, income_entries: list) -> dict:
    """Shared aggregation logic for yearly overview.

    Args:
        expenses: List of Expense objects with get_monthly_amounts().
        income_entries: List of Income objects with get_monthly_amounts().

    Returns:
        dict with keys: categories, totals, income, balance, year_total.
    """
    # Build category breakdown
    categories: dict[str, dict[int, float]] = {}
    for exp in expenses:
        if exp.category not in categories:
            categories[exp.category] = {m: 0.0 for m in range(1, 13)}
        monthly = exp.get_monthly_amounts()
        for m in range(1, 13):
            categories[exp.category][m] += monthly[m]

    # Round all category values
    for cat in categories:
        for m in range(1, 13):
            categories[cat][m] = round(categories[cat][m], 2)

    # Totals per month
    totals = {m: round(sum(cat[m] for cat in categories.values()), 2) for m in range(1, 13)}

    # Income per month (respects months field via get_monthly_amounts)
    income = {m: 0.0 for m in range(1, 13)}
    for inc in income_entries:
        monthly_amounts = inc.get_monthly_amounts()
        for m in range(1, 13):
            income[m] += monthly_amounts[m]
    for m in range(1, 13):
        income[m] = round(income[m], 2)

    # Balance and year total
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


def get_demo_income(advanced: bool = False) -> list[Income]:
    """Get demo income data."""
    source = DEMO_INCOME_ADVANCED if advanced else DEMO_INCOME
    return [Income(id=i+1, user_id=0, person=person, amount=amount, frequency=freq, months=months)
            for i, (person, amount, freq, months) in enumerate(source)]


def get_demo_total_income(advanced: bool = False) -> float:
    """Get total demo income (converted to monthly equivalent)."""
    return sum(inc.monthly_amount for inc in get_demo_income(advanced))


def get_demo_expenses(advanced: bool = False) -> list[Expense]:
    """Get demo expense data."""
    if advanced:
        return [Expense(id=i+1, user_id=0, name=name, category=cat, amount=amount, frequency=freq, account=acct, months=months)
                for i, (name, cat, amount, freq, acct, months) in enumerate(DEMO_EXPENSES_ADVANCED)]
    return [Expense(id=i+1, user_id=0, name=name, category=cat, amount=amount, frequency=freq, account=None, months=months)
            for i, (name, cat, amount, freq, months) in enumerate(DEMO_EXPENSES)]


def get_demo_expenses_by_category(advanced: bool = False) -> dict[str, list[Expense]]:
    """Get demo expenses grouped by category."""
    expenses = get_demo_expenses(advanced)
    grouped = {}
    for exp in expenses:
        if exp.category not in grouped:
            grouped[exp.category] = []
        grouped[exp.category].append(exp)
    return grouped


def get_demo_category_totals(advanced: bool = False) -> dict[str, float]:
    """Get demo total monthly amount per category."""
    expenses = get_demo_expenses(advanced)
    totals = {}
    for exp in expenses:
        if exp.category not in totals:
            totals[exp.category] = 0
        totals[exp.category] += exp.monthly_amount
    return totals


def get_demo_total_expenses(advanced: bool = False) -> float:
    """Get demo total monthly expenses."""
    return sum(exp.monthly_amount for exp in get_demo_expenses(advanced))


def get_demo_account_totals(advanced: bool = False) -> dict[str, float]:
    """Get demo account totals (monthly equivalent)."""
    if not advanced:
        return {}
    expenses = get_demo_expenses(advanced=True)
    totals = {}
    for exp in expenses:
        if exp.account:
            if exp.account not in totals:
                totals[exp.account] = 0
            totals[exp.account] += exp.monthly_amount
    return totals


def get_demo_accounts(advanced: bool = False) -> list[Account]:
    """Get demo accounts for the accounts dropdown."""
    if not advanced:
        return []
    names = ["Budgetkonto", "Forbrugskonto", "Person 1 konto", "Person 2 konto", "Opsparingskonto"]
    return [Account(id=i+1, name=name) for i, name in enumerate(names)]


def get_yearly_overview_demo(advanced: bool = False) -> dict:
    """Get yearly overview for demo mode."""
    return _calculate_yearly_overview(
        get_demo_expenses(advanced),
        get_demo_income(advanced),
    )


# Initialize database when run directly (for testing/setup)
# For production, api.py calls init_db() explicitly at startup
if __name__ == "__main__":
    init_db()
