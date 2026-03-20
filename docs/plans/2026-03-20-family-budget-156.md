# Decompose database.py into coherent modules with DataContext facade

> **For agentic workers:** REQUIRED: Use superpowers-extended-cc:subagent-driven-development (if subagents available) or superpowers-extended-cc:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decompose the 1194-line `src/database.py` god module into 7 focused modules under `src/db/` with a DataContext facade that eliminates demo branching in routes.

**Architecture:** Extract modules bottom-up (models -> security -> connection -> schema -> store -> demo -> facade), maintaining a backward-compat shim at `src/database.py` that re-exports everything. Each extraction step keeps the full test suite green. Finally, migrate route GET handlers to use `DataContext` to eliminate `if demo:` branching.

**Tech Stack:** Python 3.12, SQLite, FastAPI, pytest

---

## File Structure

### New files to create:
- `src/db/__init__.py` — package re-exports
- `src/db/models.py` — dataclasses with MonthlyMixin
- `src/db/security.py` — hash_password, verify_password, hash_email, PBKDF2_ITERATIONS
- `src/db/connection.py` — DB_PATH, get_connection, ensure_db_directory
- `src/db/schema.py` — _create_tables, _seed_default_categories, init_db, DEFAULT_CATEGORIES
- `src/db/store.py` — all ~40 CRUD functions + _calculate_yearly_overview, get_yearly_overview
- `src/db/demo.py` — DEMO_* data + get_demo_* functions
- `src/db/facade.py` — DataContext class
- `tests/test_models.py` — MonthlyMixin unit tests (pure, no DB)
- `tests/test_security_standalone.py` — security tests without DB setup
- `tests/test_data_context.py` — DataContext facade tests

### Files to modify:
- `src/database.py` — becomes a shim that re-exports from `src.db`
- `src/routes/dashboard.py` — migrate to DataContext
- `src/routes/expenses.py` — migrate GET handler to DataContext
- `src/routes/income.py` — migrate GET handler to DataContext
- `src/routes/yearly.py` — migrate to DataContext
- `src/routes/api_endpoints.py` — migrate chart_data to DataContext
- `src/routes/accounts.py` — partial migration (demo branching for GET)
- `src/routes/categories.py` — partial migration (demo branching for GET)

### Files unchanged:
- `tests/conftest.py` — continues using `from src import database as db` via shim
- `tests/test_database.py` — continues working via shim
- All other test files — continue working via shim
- `src/api.py` — `db.init_db()` call works via shim

## Dependency Graph

```
connection.py    (no internal deps)
security.py      (no internal deps — stdlib only)
models.py        (no internal deps — pure dataclasses)
     |
schema.py        -> connection, models
     |
store.py         -> connection, models
     |
demo.py          -> models, store._calculate_yearly_overview
     |
facade.py        -> store, demo, models
     |
db/__init__.py   -> all above (re-exports)
database.py      -> db (shim)
```

---

### Task 0: Create src/db/ package and extract models.py with MonthlyMixin

**Files:**
- Create: `src/db/__init__.py`
- Create: `src/db/models.py`
- Create: `tests/test_models.py`

Models are pure dataclasses with zero dependencies — safest to extract first.

- [ ] **Step 1: Write failing test for MonthlyMixin**

Create `tests/test_models.py`:

```python
"""Unit tests for domain models — pure computation, no DB needed."""


class TestMonthlyMixin:
    """Tests for shared monthly_amount and get_monthly_amounts logic."""

    def test_monthly_income_amount(self):
        from src.db.models import Income
        inc = Income(id=1, user_id=1, person="Test", amount=12000, frequency="monthly")
        assert inc.monthly_amount == 12000.0

    def test_yearly_income_monthly_amount(self):
        from src.db.models import Income
        inc = Income(id=1, user_id=1, person="Test", amount=12000, frequency="yearly")
        assert inc.monthly_amount == 1000.0

    def test_quarterly_expense_monthly_amount(self):
        from src.db.models import Expense
        exp = Expense(id=1, user_id=1, name="Test", category="Bolig", amount=3000, frequency="quarterly")
        assert exp.monthly_amount == 1000.0

    def test_semi_annual_monthly_amount(self):
        from src.db.models import Expense
        exp = Expense(id=1, user_id=1, name="Test", category="Bolig", amount=6000, frequency="semi-annual")
        assert exp.monthly_amount == 1000.0

    def test_get_monthly_amounts_monthly_spreads_evenly(self):
        from src.db.models import Expense
        exp = Expense(id=1, user_id=1, name="Test", category="Bolig", amount=1200, frequency="monthly")
        amounts = exp.get_monthly_amounts()
        assert all(amounts[m] == 1200.0 for m in range(1, 13))

    def test_get_monthly_amounts_with_specific_months(self):
        from src.db.models import Expense
        exp = Expense(id=1, user_id=1, name="Test", category="Bolig", amount=6000, frequency="semi-annual", months=[6, 12])
        amounts = exp.get_monthly_amounts()
        assert amounts[6] == 3000.0
        assert amounts[12] == 3000.0
        assert amounts[1] == 0.0

    def test_get_monthly_amounts_no_months_spreads_evenly(self):
        from src.db.models import Income
        inc = Income(id=1, user_id=1, person="Test", amount=12000, frequency="yearly")
        amounts = inc.get_monthly_amounts()
        assert all(amounts[m] == 1000.0 for m in range(1, 13))

    def test_income_and_expense_share_same_logic(self):
        """Both Income and Expense should produce identical monthly_amount for same inputs."""
        from src.db.models import Expense, Income
        inc = Income(id=1, user_id=1, person="X", amount=2400, frequency="quarterly")
        exp = Expense(id=1, user_id=1, name="X", category="C", amount=2400, frequency="quarterly")
        assert inc.monthly_amount == exp.monthly_amount


class TestUserModel:
    def test_has_email_true(self):
        from src.db.models import User
        u = User(id=1, username="test", password_hash="h", salt="s", email_hash="abc")
        assert u.has_email() is True

    def test_has_email_false(self):
        from src.db.models import User
        u = User(id=1, username="test", password_hash="h", salt="s")
        assert u.has_email() is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.db'`

- [ ] **Step 3: Create src/db/ package with models.py**

Create `src/db/__init__.py` (empty for now):
```python
"""Family Budget database package."""
```

Create `src/db/models.py` — extract dataclasses from `src/database.py:135-238`:
```python
"""Domain models for Family Budget."""

from dataclasses import dataclass


class MonthlyMixin:
    """Shared monthly amount computation for Income and Expense."""
    amount: float
    frequency: str
    months: list[int] | None

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
class Income(MonthlyMixin):
    id: int
    user_id: int
    person: str
    amount: float
    frequency: str = 'monthly'
    months: list[int] | None = None


@dataclass
class Expense(MonthlyMixin):
    id: int
    user_id: int
    name: str
    category: str
    amount: float
    frequency: str
    account: str | None = None
    months: list[int] | None = None


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
```

- [ ] **Step 4: Run tests to verify models tests pass**

Run: `venv/bin/pytest tests/test_models.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run full test suite to verify nothing is broken**

Run: `venv/bin/pytest tests/ -q`
Expected: All existing tests still pass (they still import from `src.database`)

- [ ] **Step 6: Commit**

```bash
git add src/db/__init__.py src/db/models.py tests/test_models.py
git commit -m "refactor(db): extract models.py with MonthlyMixin from database.py"
```

---

### Task 1: Extract security.py

**Files:**
- Create: `src/db/security.py`
- Create: `tests/test_security_standalone.py`

Security functions have zero internal dependencies (stdlib only).

- [ ] **Step 1: Write failing test**

Create `tests/test_security_standalone.py`:

```python
"""Standalone security tests — no DB setup needed."""


class TestHashPassword:
    def test_returns_hash_and_salt(self):
        from src.db.security import hash_password
        h, s = hash_password("testpassword")
        assert len(h) == 64  # SHA-256 hex
        assert len(s) == 64  # 32 bytes hex

    def test_same_salt_same_hash(self):
        from src.db.security import hash_password
        _, salt = hash_password("test")
        h1, _ = hash_password("test", bytes.fromhex(salt))
        h2, _ = hash_password("test", bytes.fromhex(salt))
        assert h1 == h2

    def test_different_passwords_differ(self):
        from src.db.security import hash_password
        _, salt = hash_password("a")
        h1, _ = hash_password("a", bytes.fromhex(salt))
        h2, _ = hash_password("b", bytes.fromhex(salt))
        assert h1 != h2


class TestVerifyPassword:
    def test_correct_password(self):
        from src.db.security import hash_password, verify_password
        h, s = hash_password("mypass")
        assert verify_password("mypass", h, s) is True

    def test_wrong_password(self):
        from src.db.security import hash_password, verify_password
        h, s = hash_password("mypass")
        assert verify_password("wrong", h, s) is False


class TestHashEmail:
    def test_deterministic(self):
        from src.db.security import hash_email
        assert hash_email("Test@Example.com") == hash_email("test@example.com")

    def test_strips_whitespace(self):
        from src.db.security import hash_email
        assert hash_email("  test@example.com  ") == hash_email("test@example.com")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/test_security_standalone.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create security.py**

Create `src/db/security.py` — extract from `src/database.py:15-48`:

```python
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
```

- [ ] **Step 4: Run tests**

Run: `venv/bin/pytest tests/test_security_standalone.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run full suite**

Run: `venv/bin/pytest tests/ -q`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add src/db/security.py tests/test_security_standalone.py
git commit -m "refactor(db): extract security.py from database.py"
```

---

### Task 2: Extract connection.py and schema.py

**Files:**
- Create: `src/db/connection.py`
- Create: `src/db/schema.py`

These depend on models but not on each other.

- [ ] **Step 1: Create connection.py**

Create `src/db/connection.py` — extract from `src/database.py:12,241-254`:

```python
"""Database connection management."""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(os.environ.get("BUDGET_DB_PATH", Path(__file__).parent.parent.parent / "data" / "budget.db"))


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
```

**Note:** `DB_PATH` uses `Path(__file__).parent.parent.parent` because the file is now at `src/db/connection.py` (3 levels to project root instead of 2).

- [ ] **Step 2: Create schema.py**

Create `src/db/schema.py` — extract from `src/database.py:52-351`:

```python
"""Database schema creation and initialization."""

from .connection import ensure_db_directory, get_connection

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
```

- [ ] **Step 3: Run full suite**

Run: `venv/bin/pytest tests/ -q`
Expected: All pass (nothing imports these yet — existing code still uses database.py)

- [ ] **Step 4: Commit**

```bash
git add src/db/connection.py src/db/schema.py
git commit -m "refactor(db): extract connection.py and schema.py"
```

---

### Task 3: Extract store.py (CRUD + aggregation)

**Files:**
- Create: `src/db/store.py`

The bulk of the module — all ~40 CRUD functions. This is a large file but its responsibility is cohesive: all database I/O for the domain entities.

- [ ] **Step 1: Create store.py**

Create `src/db/store.py` — extract from `src/database.py:353-1111`. This includes:
- All income operations (get_all_income, add_income, update_income, get_total_income, delete_all_income)
- All expense operations (get_all_expenses, get_expense_by_id, add_expense, update_expense, delete_expense, get_total_monthly_expenses, get_expenses_by_category, get_category_totals)
- All category operations (get_all_categories, get_category_by_id, add_category, update_category, delete_category, get_category_usage_count, ensure_default_categories, migrate_user_categories)
- All account operations (get_all_accounts, get_account_by_id, add_account, update_account, delete_account, get_account_usage_count, get_account_totals)
- All user operations (create_user, get_user_by_username, get_user_by_email, get_user_by_id, update_user_email, update_user_password, authenticate_user, update_last_login, get_user_count)
- Password reset token operations (create_password_reset_token, get_valid_reset_token, mark_reset_token_used)
- Aggregation (_calculate_yearly_overview, get_yearly_overview)

The file header:
```python
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
```

Copy all functions from `src/database.py:353-1111` verbatim, removing the section comment headers. All references to local `get_connection`, model classes, `hash_password`, `verify_password`, `hash_email`, and `DEFAULT_CATEGORIES` now resolve via the imports above.

- [ ] **Step 2: Run full suite**

Run: `venv/bin/pytest tests/ -q`
Expected: All pass (nothing imports store.py yet)

- [ ] **Step 3: Commit**

```bash
git add src/db/store.py
git commit -m "refactor(db): extract store.py with all CRUD operations"
```

---

### Task 4: Extract demo.py

**Files:**
- Create: `src/db/demo.py`

- [ ] **Step 1: Create demo.py**

Create `src/db/demo.py` — extract from `src/database.py:64-132,1113-1188`:

```python
"""Demo data and demo-specific query functions.

Hardcoded data for demo mode. Reuses _calculate_yearly_overview from store.
"""

from .models import Account, Expense, Income
from .store import _calculate_yearly_overview

# Demo data - typical Danish household budget
DEMO_INCOME = [
    # (person, amount, frequency, months)
    ("Person 1", 28000, "monthly", None),
    ("Person 2", 22000, "monthly", None),
    ("Bonus", 30000, "semi-annual", [6, 12]),
]

DEMO_EXPENSES = [
    # (name, category, amount, frequency, months)
    ("Husleje/boliglån", "Bolig", 12000, "monthly", None),
    ("Ejendomsskat", "Bolig", 18000, "yearly", [1, 7]),
    ("Varme", "Forbrug", 800, "monthly", None),
    ("El", "Forbrug", 600, "monthly", None),
    ("Vand", "Forbrug", 2400, "quarterly", [3, 6, 9, 12]),
    ("Internet", "Forbrug", 299, "monthly", None),
    ("Bil - lån", "Transport", 2500, "monthly", None),
    ("Benzin", "Transport", 1500, "monthly", None),
    ("Vægtafgift", "Transport", 3600, "yearly", [4]),
    ("Bilforsikring", "Transport", 6000, "yearly", [2]),
    ("Bilservice", "Transport", 4500, "semi-annual", [3, 9]),
    ("Institution", "Børn", 3200, "monthly", None),
    ("Fritidsaktiviteter", "Børn", 2400, "semi-annual", [1, 8]),
    ("Dagligvarer", "Mad", 6000, "monthly", None),
    ("Indboforsikring", "Forsikring", 1800, "yearly", [6]),
    ("Ulykkesforsikring", "Forsikring", 1200, "yearly", [6]),
    ("Tandlægeforsikring", "Forsikring", 600, "quarterly", [3, 6, 9, 12]),
    ("Netflix", "Abonnementer", 129, "monthly", None),
    ("Spotify", "Abonnementer", 99, "monthly", None),
    ("Fitness", "Abonnementer", 299, "monthly", None),
    ("Opsparing", "Opsparing", 3000, "monthly", None),
    ("Telefon", "Andet", 199, "monthly", None),
]

DEMO_INCOME_ADVANCED = [
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


def get_demo_income(advanced: bool = False) -> list[Income]:
    source = DEMO_INCOME_ADVANCED if advanced else DEMO_INCOME
    return [Income(id=i+1, user_id=0, person=person, amount=amount, frequency=freq, months=months)
            for i, (person, amount, freq, months) in enumerate(source)]


def get_demo_total_income(advanced: bool = False) -> float:
    return sum(inc.monthly_amount for inc in get_demo_income(advanced))


def get_demo_expenses(advanced: bool = False) -> list[Expense]:
    if advanced:
        return [Expense(id=i+1, user_id=0, name=name, category=cat, amount=amount, frequency=freq, account=acct, months=months)
                for i, (name, cat, amount, freq, acct, months) in enumerate(DEMO_EXPENSES_ADVANCED)]
    return [Expense(id=i+1, user_id=0, name=name, category=cat, amount=amount, frequency=freq, account=None, months=months)
            for i, (name, cat, amount, freq, months) in enumerate(DEMO_EXPENSES)]


def get_demo_expenses_by_category(advanced: bool = False) -> dict[str, list[Expense]]:
    expenses = get_demo_expenses(advanced)
    grouped = {}
    for exp in expenses:
        if exp.category not in grouped:
            grouped[exp.category] = []
        grouped[exp.category].append(exp)
    return grouped


def get_demo_category_totals(advanced: bool = False) -> dict[str, float]:
    expenses = get_demo_expenses(advanced)
    totals = {}
    for exp in expenses:
        if exp.category not in totals:
            totals[exp.category] = 0
        totals[exp.category] += exp.monthly_amount
    return totals


def get_demo_total_expenses(advanced: bool = False) -> float:
    return sum(exp.monthly_amount for exp in get_demo_expenses(advanced))


def get_demo_account_totals(advanced: bool = False) -> dict[str, float]:
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
    if not advanced:
        return []
    names = ["Budgetkonto", "Forbrugskonto", "Person 1 konto", "Person 2 konto", "Opsparingskonto"]
    return [Account(id=i+1, name=name) for i, name in enumerate(names)]


def get_yearly_overview_demo(advanced: bool = False) -> dict:
    return _calculate_yearly_overview(
        get_demo_expenses(advanced),
        get_demo_income(advanced),
    )
```

- [ ] **Step 2: Run full suite**

Run: `venv/bin/pytest tests/ -q`
Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add src/db/demo.py
git commit -m "refactor(db): extract demo.py with demo data and functions"
```

---

### Task 5: Wire up db/__init__.py and convert database.py to shim

**Files:**
- Modify: `src/db/__init__.py`
- Modify: `src/database.py`

This is the critical step — the shim must re-export **every** public name that any consumer currently imports. After this, all existing `from src import database as db` and `from src.database import X` imports continue working.

- [ ] **Step 1: Write db/__init__.py with all re-exports**

Update `src/db/__init__.py`:

```python
"""Family Budget database package.

Re-exports all public names for convenient access via `from src.db import X`.
"""

from .connection import DB_PATH, ensure_db_directory, get_connection
from .demo import (
    DEMO_EXPENSES,
    DEMO_EXPENSES_ADVANCED,
    DEMO_INCOME,
    DEMO_INCOME_ADVANCED,
    get_demo_account_totals,
    get_demo_accounts,
    get_demo_category_totals,
    get_demo_expenses,
    get_demo_expenses_by_category,
    get_demo_income,
    get_demo_total_expenses,
    get_demo_total_income,
    get_yearly_overview_demo,
)
from .models import (
    Account,
    Category,
    Expense,
    Income,
    PasswordResetToken,
    User,
)
from .schema import DEFAULT_CATEGORIES, init_db
from .security import (
    PBKDF2_ITERATIONS,
    hash_email,
    hash_password,
    verify_password,
)
from .store import (
    _calculate_yearly_overview,
    add_account,
    add_category,
    add_expense,
    add_income,
    authenticate_user,
    create_password_reset_token,
    create_user,
    delete_account,
    delete_all_income,
    delete_category,
    delete_expense,
    ensure_default_categories,
    get_account_by_id,
    get_account_totals,
    get_account_usage_count,
    get_all_accounts,
    get_all_categories,
    get_all_expenses,
    get_all_income,
    get_category_by_id,
    get_category_totals,
    get_category_usage_count,
    get_expense_by_id,
    get_expenses_by_category,
    get_total_income,
    get_total_monthly_expenses,
    get_user_by_email,
    get_user_by_id,
    get_user_by_username,
    get_user_count,
    get_valid_reset_token,
    get_yearly_overview,
    mark_reset_token_used,
    migrate_user_categories,
    update_account,
    update_category,
    update_expense,
    update_income,
    update_last_login,
    update_user_email,
    update_user_password,
)

__all__ = [
    # connection
    "DB_PATH", "get_connection", "ensure_db_directory",
    # security
    "PBKDF2_ITERATIONS", "hash_password", "verify_password", "hash_email",
    # models
    "Income", "Expense", "Account", "Category", "User", "PasswordResetToken",
    # schema
    "DEFAULT_CATEGORIES", "init_db",
    # store (all CRUD + aggregation)
    "get_all_income", "add_income", "update_income", "get_total_income", "delete_all_income",
    "get_all_expenses", "get_expense_by_id", "add_expense", "update_expense", "delete_expense",
    "get_total_monthly_expenses", "get_expenses_by_category", "get_category_totals",
    "get_all_categories", "get_category_by_id", "add_category", "update_category",
    "delete_category", "get_category_usage_count", "ensure_default_categories",
    "migrate_user_categories",
    "get_all_accounts", "get_account_by_id", "add_account", "update_account",
    "delete_account", "get_account_usage_count", "get_account_totals",
    "create_user", "get_user_by_username", "get_user_by_email", "get_user_by_id",
    "update_user_email", "update_user_password", "authenticate_user",
    "update_last_login", "get_user_count",
    "create_password_reset_token", "get_valid_reset_token", "mark_reset_token_used",
    "_calculate_yearly_overview", "get_yearly_overview",
    # demo
    "DEMO_INCOME", "DEMO_EXPENSES", "DEMO_INCOME_ADVANCED", "DEMO_EXPENSES_ADVANCED",
    "get_demo_income", "get_demo_total_income", "get_demo_expenses",
    "get_demo_expenses_by_category", "get_demo_category_totals", "get_demo_total_expenses",
    "get_demo_account_totals", "get_demo_accounts", "get_yearly_overview_demo",
]
```

- [ ] **Step 2: Convert database.py to a shim**

Replace the entire content of `src/database.py` with:

```python
"""Backward-compatibility shim.

All logic has moved to src/db/. This module re-exports everything
so existing `from src import database as db` and
`from src.database import X` imports continue working.

DB_PATH writes (e.g. conftest's `db.DB_PATH = temp_path`) are intercepted
by _ShimModule and propagated to src.db.connection.DB_PATH.
"""

from src.db import *  # noqa: F401,F403

import sys as _sys  # noqa: E402
import types as _types  # noqa: E402

import src.db.connection as _conn  # noqa: E402


class _ShimModule(_types.ModuleType):
    """Module subclass that intercepts DB_PATH assignment.

    Python data descriptors (properties with __get__ + __set__) take
    precedence over instance __dict__ entries, so the property always wins.
    """

    @property
    def DB_PATH(self):
        return _conn.DB_PATH

    @DB_PATH.setter
    def DB_PATH(self, value):
        _conn.DB_PATH = value


# Replace this module in sys.modules with the shim instance
_current = _sys.modules[__name__]
_shim = _ShimModule(__name__)
_shim.__dict__.update({k: v for k, v in _current.__dict__.items()
                       if k != '_ShimModule'})
_shim.__file__ = __file__
_shim.__package__ = __package__
_sys.modules[__name__] = _shim
```

**Critical:** The conftest does `db.DB_PATH = temp_path` to redirect the database for tests. The shim must propagate this write to `src.db.connection.DB_PATH` where `get_connection()` reads it. The `_ShimModule` property handles this.

- [ ] **Step 3: Run full test suite**

Run: `venv/bin/pytest tests/ -q`
Expected: ALL existing tests pass. This is the most critical verification point.

- [ ] **Step 4: Run new tests too**

Run: `venv/bin/pytest tests/test_models.py tests/test_security_standalone.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/db/__init__.py src/database.py
git commit -m "refactor(db): convert database.py to shim re-exporting from src.db"
```

---

### Task 6: Create DataContext facade and tests

**Files:**
- Create: `src/db/facade.py`
- Create: `tests/test_data_context.py`

- [ ] **Step 1: Write failing test for DataContext**

Create `tests/test_data_context.py`:

```python
"""Tests for DataContext facade — verifies demo transparency."""


class TestDataContextDemo:
    """DataContext with demo=True should return demo data without DB."""

    def test_expenses_returns_demo_data(self):
        from src.db.facade import DataContext
        ctx = DataContext(user_id=0, demo=True)
        expenses = ctx.expenses()
        assert len(expenses) > 0
        assert expenses[0].name == "Husleje/boliglån"

    def test_income_returns_demo_data(self):
        from src.db.facade import DataContext
        ctx = DataContext(user_id=0, demo=True)
        income = ctx.income()
        assert len(income) >= 3

    def test_categories_returns_demo_categories(self, db_module):
        from src.db.facade import DataContext
        ctx = DataContext(user_id=0, demo=True)
        cats = ctx.categories()
        assert len(cats) > 0

    def test_category_totals(self):
        from src.db.facade import DataContext
        ctx = DataContext(user_id=0, demo=True)
        totals = ctx.category_totals()
        assert "Bolig" in totals
        assert totals["Bolig"] > 0

    def test_total_income(self):
        from src.db.facade import DataContext
        ctx = DataContext(user_id=0, demo=True)
        assert ctx.total_income() > 0

    def test_total_expenses(self):
        from src.db.facade import DataContext
        ctx = DataContext(user_id=0, demo=True)
        assert ctx.total_expenses() > 0

    def test_yearly_overview(self):
        from src.db.facade import DataContext
        ctx = DataContext(user_id=0, demo=True)
        overview = ctx.yearly_overview()
        assert "categories" in overview
        assert "totals" in overview

    def test_expenses_by_category(self):
        from src.db.facade import DataContext
        ctx = DataContext(user_id=0, demo=True)
        grouped = ctx.expenses_by_category()
        assert "Bolig" in grouped

    def test_account_totals_advanced(self):
        from src.db.facade import DataContext
        ctx = DataContext(user_id=0, demo=True, advanced=True)
        totals = ctx.account_totals()
        assert "Budgetkonto" in totals

    def test_accounts_advanced(self):
        from src.db.facade import DataContext
        ctx = DataContext(user_id=0, demo=True, advanced=True)
        accounts = ctx.accounts()
        assert len(accounts) > 0

    def test_category_usage_demo_is_zero(self, db_module):
        from src.db.facade import DataContext
        ctx = DataContext(user_id=0, demo=True)
        usage = ctx.category_usage()
        assert all(v == 0 for v in usage.values())


class TestDataContextReal:
    """DataContext with demo=False should query the real DB."""

    def test_expenses_empty_for_new_user(self, db_module):
        from src.db.facade import DataContext
        user_id = db_module.create_user("ctx_test", "pass123")
        ctx = DataContext(user_id=user_id, demo=False)
        assert ctx.expenses() == []

    def test_income_empty_for_new_user(self, db_module):
        from src.db.facade import DataContext
        user_id = db_module.create_user("ctx_test2", "pass123")
        ctx = DataContext(user_id=user_id, demo=False)
        assert ctx.income() == []

    def test_total_income_zero_for_new_user(self, db_module):
        from src.db.facade import DataContext
        user_id = db_module.create_user("ctx_test3", "pass123")
        ctx = DataContext(user_id=user_id, demo=False)
        assert ctx.total_income() == 0.0

    def test_categories_has_defaults(self, db_module):
        from src.db.facade import DataContext
        user_id = db_module.create_user("ctx_test4", "pass123")
        ctx = DataContext(user_id=user_id, demo=False)
        cats = ctx.categories()
        assert len(cats) == 9  # DEFAULT_CATEGORIES count
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/test_data_context.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.db.facade'`

- [ ] **Step 3: Create facade.py**

Create `src/db/facade.py`:

```python
"""DataContext facade — demo-transparent data access.

Construct once per request, call methods without demo branching.
Routes never see the if-demo-else-real pattern.
"""

from .demo import (
    get_demo_account_totals,
    get_demo_accounts,
    get_demo_category_totals,
    get_demo_expenses,
    get_demo_expenses_by_category,
    get_demo_income,
    get_demo_total_expenses,
    get_demo_total_income,
    get_yearly_overview_demo,
)
from .models import Account, Category, Expense, Income
from .store import (
    get_account_totals,
    get_account_usage_count,
    get_all_accounts,
    get_all_categories,
    get_all_expenses,
    get_all_income,
    get_category_totals,
    get_category_usage_count,
    get_expenses_by_category,
    get_total_income,
    get_total_monthly_expenses,
    get_yearly_overview,
)


class DataContext:
    """Demo-transparent data access.

    Construct once per request with user_id, demo flag, and optional advanced flag.
    All methods dispatch to real DB or demo data based on the demo flag.
    """

    def __init__(self, user_id: int, demo: bool, advanced: bool = False):
        self.user_id = user_id
        self.demo = demo
        self.advanced = advanced

    def expenses(self) -> list[Expense]:
        if self.demo:
            return get_demo_expenses(self.advanced)
        return get_all_expenses(self.user_id)

    def income(self) -> list[Income]:
        if self.demo:
            return get_demo_income(self.advanced)
        return get_all_income(self.user_id)

    def categories(self) -> list[Category]:
        effective_user_id = 0 if self.demo else self.user_id
        return get_all_categories(effective_user_id)

    def accounts(self) -> list[Account]:
        if self.demo:
            return get_demo_accounts(self.advanced)
        return get_all_accounts(self.user_id)

    def category_totals(self) -> dict[str, float]:
        if self.demo:
            return get_demo_category_totals(self.advanced)
        return get_category_totals(self.user_id)

    def account_totals(self) -> dict[str, float]:
        if self.demo:
            return get_demo_account_totals(self.advanced)
        return get_account_totals(self.user_id)

    def total_income(self) -> float:
        if self.demo:
            return get_demo_total_income(self.advanced)
        return get_total_income(self.user_id)

    def total_expenses(self) -> float:
        if self.demo:
            return get_demo_total_expenses(self.advanced)
        return get_total_monthly_expenses(self.user_id)

    def yearly_overview(self) -> dict:
        if self.demo:
            return get_yearly_overview_demo(self.advanced)
        return get_yearly_overview(self.user_id)

    def expenses_by_category(self) -> dict[str, list[Expense]]:
        if self.demo:
            return get_demo_expenses_by_category(self.advanced)
        return get_expenses_by_category(self.user_id)

    def category_usage(self) -> dict[str, int]:
        """Get usage count per category. Returns all zeros in demo mode."""
        cats = self.categories()
        if self.demo:
            return {cat.name: 0 for cat in cats}
        return {cat.name: get_category_usage_count(cat.name, self.user_id) for cat in cats}

    def account_usage(self) -> dict[str, int]:
        """Get usage count per account. Returns all zeros in demo mode."""
        accounts = self.accounts()
        if self.demo:
            return {acc.name: 0 for acc in accounts}
        return {acc.name: get_account_usage_count(acc.name, self.user_id) for acc in accounts}
```

- [ ] **Step 4: Add DataContext to db/__init__.py exports**

Add to `src/db/__init__.py`:
```python
from .facade import DataContext
```
And add `"DataContext"` to `__all__`.

- [ ] **Step 5: Run tests**

Run: `venv/bin/pytest tests/test_data_context.py tests/ -q`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/db/facade.py src/db/__init__.py tests/test_data_context.py
git commit -m "feat(db): add DataContext facade for demo-transparent data access"
```

---

### Task 7: Migrate route GET handlers to DataContext

**Files:**
- Modify: `src/routes/dashboard.py`
- Modify: `src/routes/expenses.py`
- Modify: `src/routes/income.py`
- Modify: `src/routes/yearly.py`
- Modify: `src/routes/api_endpoints.py`
- Modify: `src/routes/accounts.py`
- Modify: `src/routes/categories.py`

Each route's GET handler replaces the `if demo:` block with a single `DataContext` construction. Write operations (POST handlers) are unaffected — they already guard against demo mode via `require_write`.

- [ ] **Step 1: Migrate dashboard.py**

Replace the `if demo:` / `else:` block in `dashboard()` with:

```python
from ..db.facade import DataContext

# ... inside dashboard():
    ctx = DataContext(user_id=user_id, demo=demo, advanced=advanced)
    incomes = ctx.income()
    total_income = ctx.total_income()
    total_expenses = ctx.total_expenses()
    expenses_by_category = ctx.expenses_by_category()
    category_totals = ctx.category_totals()
    account_totals = ctx.account_totals()
    yearly_overview = ctx.yearly_overview()
```

Remove the `from .. import database as db` import if no other function in the file uses it.

- [ ] **Step 2: Migrate expenses.py GET handler**

In `expenses_page()`, replace the `if demo:` block with:

```python
from ..db.facade import DataContext

# ... inside expenses_page():
    ctx = DataContext(user_id=user_id, demo=demo, advanced=advanced)
    expenses = ctx.expenses()
    expenses_by_category = ctx.expenses_by_category()
    category_totals = ctx.category_totals()
    categories = ctx.categories()
    category_usage = ctx.category_usage()
    accounts = ctx.accounts()
```

Keep `from .. import database as db` for the POST handlers (add_expense, delete_expense, edit_expense).

- [ ] **Step 3: Migrate income.py GET handler**

In `income_page()`, replace:

```python
from ..db.facade import DataContext

# ... inside income_page():
    ctx = DataContext(user_id=user_id, demo=demo, advanced=advanced)
    incomes = ctx.income()
```

Keep `from .. import database as db` for the POST handler.

- [ ] **Step 4: Migrate yearly.py**

```python
from ..db.facade import DataContext

# ... inside yearly_overview_page():
    ctx = DataContext(user_id=user_id, demo=demo)
    overview = ctx.yearly_overview()
```

Remove `from .. import database as db` (no other usage in this file).

- [ ] **Step 5: Migrate api_endpoints.py chart_data**

In `chart_data()`, replace the `if demo:` block with:

```python
from ..db.facade import DataContext

# ... inside chart_data():
    ctx = DataContext(user_id=user_id, demo=demo, advanced=advanced)
    category_totals = ctx.category_totals()
    total_income = ctx.total_income()
    total_expenses = ctx.total_expenses()
    expenses = ctx.expenses()
```

Keep `from .. import database as db` for `api_stats()` which uses `db.get_user_count()`.

- [ ] **Step 6: Migrate accounts.py GET handler**

In `accounts_page()`, replace with:

```python
from ..db.facade import DataContext

# ... inside accounts_page():
    ctx = DataContext(user_id=user_id, demo=demo, advanced=is_demo_advanced(request))
    accounts = ctx.accounts()
    account_usage = ctx.account_usage()
```

Remove `effective_user_id` variable. Keep `from .. import database as db` for POST handlers.
Note: passing `advanced` is intentional — in advanced demo mode, the facade returns hardcoded demo accounts (Budgetkonto etc.) instead of querying user_id=0 from the DB. This matches the intent of the advanced demo feature.

- [ ] **Step 7: Migrate categories.py GET handler**

In `categories_page()`, replace with:

```python
from ..db.facade import DataContext

# ... inside categories_page():
    ctx = DataContext(user_id=user_id, demo=demo)
    categories = ctx.categories()
    category_usage = ctx.category_usage()
```

Remove `effective_user_id` variable. Keep `from .. import database as db` for POST handlers.

- [ ] **Step 8: Run full test suite**

Run: `venv/bin/pytest tests/ -q`
Expected: ALL PASS. This verifies that the route migrations haven't broken any behavior.

- [ ] **Step 9: Commit**

```bash
git add src/routes/dashboard.py src/routes/expenses.py src/routes/income.py \
        src/routes/yearly.py src/routes/api_endpoints.py src/routes/accounts.py \
        src/routes/categories.py
git commit -m "refactor(routes): migrate GET handlers to DataContext, eliminate demo branching"
```

---

### Task 8: Clean up — remove duplicate code from old database.py

At this point, `src/database.py` is a shim and all logic lives in `src/db/`. The old `database.py` body can be verified as dead code. However, since the shim approach uses `from src.db import *`, the old function bodies were already removed in Task 5.

This task verifies everything is clean.

- [ ] **Step 1: Verify database.py is just a shim**

Run: `wc -l src/database.py`
Expected: ~30-40 lines (just the shim code)

- [ ] **Step 2: Verify no circular imports**

Run: `venv/bin/python -c "from src.db import DataContext; print('OK')"`
Expected: `OK`

Run: `venv/bin/python -c "from src import database as db; print(db.get_all_expenses); print('OK')"`
Expected: prints function reference and `OK`

- [ ] **Step 3: Run full test suite one final time**

Run: `venv/bin/pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "refactor(db): verify clean decomposition, all tests green"
```

---

## Summary of Changes

| Before | After |
|--------|-------|
| `src/database.py` (1194 lines, 6 concerns) | `src/db/` package (7 modules, ~same LOC total) |
| 7 routes with `if demo:` branching | 7 routes using `DataContext` |
| Duplicated monthly_amount logic in Income/Expense | `MonthlyMixin` shared by both |
| Security code interleaved with CRUD | `security.py` auditable in isolation |
| `from src import database as db` everywhere | Same imports still work via shim |
