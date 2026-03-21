# Decompose store.py into Domain Stores Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers-extended-cc:subagent-driven-development (if subagents available) or superpowers-extended-cc:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the 756-line `src/db/store.py` monolith into `budget_store.py`, `identity_store.py`, and `operations.py` with composable transactions and typed results, while maintaining full backward compatibility.

**Architecture:** Two domain stores (`budget_store.py` for single-table budget CRUD, `identity_store.py` for auth/user CRUD) plus an `operations.py` module for cross-domain operations with typed result objects. A `transaction()` context manager in `connection.py` enables atomic composition. The existing `store.py` becomes a re-export shim with backward-compat aliases so no route files need changes in this PR.

**Tech Stack:** Python 3.12, SQLite3, pytest, FastAPI

---

## File Structure

```
src/db/
    connection.py        # MODIFY: +transaction() context manager (~20 lines added)
    budget_store.py      # CREATE: ~370 lines - income/expense/category/account/aggregation CRUD
    identity_store.py    # CREATE: ~160 lines - user/auth/token CRUD
    operations.py        # CREATE: ~120 lines - cross-domain ops with typed results
    store.py             # MODIFY: reduce to ~15-line re-export shim
    __init__.py          # MODIFY: update import sources + add backward-compat aliases
    facade.py            # MODIFY: update imports to use new modules directly
    demo.py              # MODIFY: update _calculate_yearly_overview import
tests/
    test_operations.py   # CREATE: ~150 lines - cross-domain operation tests
    test_transaction.py  # CREATE: ~60 lines - transaction() composability tests
```

### Dependency Graph (acyclic)

```
operations.py --> budget_store.py --> connection.py, models.py, schema.py
              --> identity_store.py --> connection.py, models.py, security.py
```

### Key Design Decisions

1. **No route changes in this PR.** All routes import via `from .. import database as db` which goes through `src/database.py` (shim) -> `src/db/__init__.py` -> individual stores. Backward-compat aliases in `__init__.py` mean callers like `db.update_category(...)` still work.
2. **`transaction(conn=None)` pattern.** Every existing function keeps its auto-commit behavior (conn=None). Cross-domain operations in `operations.py` use explicit `transaction()` for atomicity.
3. **Typed results replace bare int/bool.** `CategoryUpdateResult`, `DeleteResult` dataclasses make cross-domain effects explicit.
4. **Bug fix: `create_user` atomicity.** Current code creates user in one transaction, then seeds categories in a separate transaction. `create_user_with_default_categories()` wraps both in one.

---

### Task 0: Add `transaction()` context manager to `connection.py`

**Files:**
- Modify: `src/db/connection.py:1-25`
- Test: `tests/test_transaction.py` (create)

- [ ] **Step 1: Write failing test for transaction()**

Create `tests/test_transaction.py`:

```python
"""Tests for transaction() context manager."""

import sqlite3

from src.db.connection import transaction


class TestTransaction:
    """Tests for the transaction() context manager."""

    def test_auto_commit_on_success(self, temp_db):
        """transaction() without conn should auto-commit on success."""
        with transaction() as conn:
            conn.execute("INSERT INTO users (username, password_hash, salt) VALUES ('txtest', 'h', 's')")

        # Verify committed: open new connection, check data persists
        with transaction() as conn:
            row = conn.execute("SELECT username FROM users WHERE username = 'txtest'").fetchone()
        assert row is not None
        assert row[0] == "txtest"

    def test_auto_rollback_on_exception(self, temp_db):
        """transaction() without conn should rollback on exception."""
        try:
            with transaction() as conn:
                conn.execute("INSERT INTO users (username, password_hash, salt) VALUES ('txfail', 'h', 's')")
                raise ValueError("deliberate failure")
        except ValueError:
            pass

        # Verify rolled back
        with transaction() as conn:
            row = conn.execute("SELECT username FROM users WHERE username = 'txfail'").fetchone()
        assert row is None

    def test_passthrough_existing_conn(self, temp_db):
        """transaction(conn) should yield the same conn without commit/close."""
        with transaction() as outer:
            with transaction(outer) as inner:
                assert inner is outer
                inner.execute("INSERT INTO users (username, password_hash, salt) VALUES ('txpass', 'h', 's')")
            # inner did NOT commit - outer still owns the transaction
            # Rollback outer to prove inner didn't auto-commit
            outer.rollback()

        with transaction() as conn:
            row = conn.execute("SELECT username FROM users WHERE username = 'txpass'").fetchone()
        assert row is None

    def test_row_factory_set(self, temp_db):
        """transaction() should set row_factory to sqlite3.Row."""
        with transaction() as conn:
            assert conn.row_factory is sqlite3.Row
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/saabendtsen/projects/family-budget && venv/bin/pytest tests/test_transaction.py -v`
Expected: ImportError - `cannot import name 'transaction' from 'src.db.connection'`

- [ ] **Step 3: Implement transaction() in connection.py**

Add to `src/db/connection.py` after the existing `get_connection()`:

```python
@contextmanager
def transaction(conn=None):
    """Yield a connection inside a transaction.

    If conn is provided, yield it as-is (caller owns commit/rollback).
    If conn is None, open a new connection, commit on success, rollback on exception.
    """
    if conn is not None:
        yield conn
        return
    new_conn = sqlite3.connect(DB_PATH)
    new_conn.row_factory = sqlite3.Row
    try:
        yield new_conn
        new_conn.commit()
    except BaseException:
        new_conn.rollback()
        raise
    finally:
        new_conn.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/saabendtsen/projects/family-budget && venv/bin/pytest tests/test_transaction.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
cd /home/saabendtsen/projects/family-budget
git add src/db/connection.py tests/test_transaction.py
git commit -m "feat(db): add transaction() context manager to connection.py

Enables composable atomic transactions with optional conn pass-through.
Part of #161."
```

---

### Task 1: Create `budget_store.py` with single-table budget CRUD

**Files:**
- Create: `src/db/budget_store.py`
- Reference: `src/db/store.py:25-378` (income, expense, single-table category, single-table account, aggregation)

This task moves **single-table** functions only. Cross-domain functions (`update_category`, `delete_category`, `update_account`, `delete_account`, `create_user`, `migrate_user_categories`) stay in `store.py` until Task 3 moves them to `operations.py`. Do NOT include `migrate_user_categories` (lines 341-378) in this file — it touches both `expenses` and `categories` tables.

- [ ] **Step 1: Create budget_store.py**

Create `src/db/budget_store.py` with these functions copied verbatim from `store.py`:

**Income (lines 25-91):**
- `get_all_income`
- `add_income`
- `update_income`
- `get_total_income`
- `delete_all_income`

**Expenses (lines 97-207):**
- `get_all_expenses`
- `get_expense_by_id`
- `add_expense`
- `update_expense`
- `delete_expense`
- `get_total_monthly_expenses`
- `get_expenses_by_category`
- `get_category_totals`

**Categories - single-table only (lines 214-246, 312-339):**
- `get_all_categories`
- `get_category_by_id`
- `add_category`
- `get_category_usage_count`
- `ensure_default_categories`

**Accounts - single-table only (lines 384-503):**
- `get_all_accounts`
- `get_account_by_id`
- `add_account`
- `get_account_usage_count`
- `get_account_totals`

**Aggregation (lines 698-756):**
- `_calculate_yearly_overview`
- `get_yearly_overview`

Header:
```python
"""Single-table budget CRUD and aggregation.

Each function in this module touches exactly one entity's table.
Cross-domain operations live in operations.py.
"""

import json
import sqlite3

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
```

Note: `get_yearly_overview` calls `get_all_expenses` and `get_all_income` which are in the same file - no cross-module dependency. The `__all__` list controls what `from .budget_store import *` exposes (prevents leaking `json`, `sqlite3`, etc.).

- [ ] **Step 2: Verify budget_store.py imports work**

Run: `cd /home/saabendtsen/projects/family-budget && venv/bin/python -c "from src.db.budget_store import get_all_income, get_all_expenses, get_all_categories, get_all_accounts, _calculate_yearly_overview; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd /home/saabendtsen/projects/family-budget
git add src/db/budget_store.py
git commit -m "feat(db): create budget_store.py with single-table CRUD

Moves income, expense, category, account, and aggregation functions
from store.py. No callers updated yet.
Part of #161."
```

---

### Task 2: Create `identity_store.py` with user/auth/token CRUD

**Files:**
- Create: `src/db/identity_store.py`
- Reference: `src/db/store.py:506-692` (user ops, token ops)

- [ ] **Step 1: Create identity_store.py**

Create `src/db/identity_store.py` with these functions copied from `store.py`:

**Users (lines 546-647):**
- `get_user_by_username`
- `get_user_by_email`
- `get_user_by_id`
- `authenticate_user`
- `update_user_email`
- `update_user_password`
- `update_last_login`
- `get_user_count`

**Tokens (lines 653-692):**
- `create_password_reset_token`
- `get_valid_reset_token`
- `mark_reset_token_used`

Header:
```python
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
```

Note: `authenticate_user` calls `get_user_by_username` which is in the same file. The `__all__` list controls what `from .identity_store import *` exposes.

- [ ] **Step 2: Verify identity_store.py imports work**

Run: `cd /home/saabendtsen/projects/family-budget && venv/bin/python -c "from src.db.identity_store import get_user_by_username, authenticate_user, create_password_reset_token; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd /home/saabendtsen/projects/family-budget
git add src/db/identity_store.py
git commit -m "feat(db): create identity_store.py with user/auth/token CRUD

Moves user management, authentication, and password reset token
functions from store.py. No callers updated yet.
Part of #161."
```

---

### Task 3: Create `operations.py` with cross-domain operations

**Files:**
- Create: `src/db/operations.py`
- Test: `tests/test_operations.py` (create)
- Reference: `src/db/store.py` lines 248-378 (update/delete category/account), 510-543 (create_user), 341-378 (migrate_user_categories)

- [ ] **Step 1: Write failing tests for operations**

Create `tests/test_operations.py`:

```python
"""Tests for cross-domain operations."""


class TestCategoryUpdateResult:
    """Tests for rename_category_and_cascade_expenses."""

    def test_rename_cascades_to_expenses(self, db_module):
        """Renaming a category should update all expenses with the old name."""
        from src.db.operations import rename_category_and_cascade_expenses

        user_id = db_module.create_user("catcascade1", "testpass")
        cat_id = db_module.add_category(user_id, "OldCat", "house")
        db_module.add_expense(user_id, "Rent", "OldCat", 1000, "monthly")
        db_module.add_expense(user_id, "Power", "OldCat", 200, "monthly")

        result = rename_category_and_cascade_expenses(cat_id, user_id, "NewCat", "house")

        assert result.cascaded_expense_count == 2
        expenses = db_module.get_all_expenses(user_id)
        assert all(e.category == "NewCat" for e in expenses)

    def test_rename_no_cascade_when_name_unchanged(self, db_module):
        """No cascade when only icon changes."""
        from src.db.operations import rename_category_and_cascade_expenses

        user_id = db_module.create_user("catcascade2", "testpass")
        cat_id = db_module.add_category(user_id, "SameCat", "house")
        db_module.add_expense(user_id, "Rent", "SameCat", 1000, "monthly")

        result = rename_category_and_cascade_expenses(cat_id, user_id, "SameCat", "zap")
        assert result.cascaded_expense_count == 0


class TestDeleteResult:
    """Tests for delete_category_if_unused and delete_account_if_unused."""

    def test_delete_unused_category(self, db_module):
        """Should delete category with no expenses."""
        from src.db.operations import delete_category_if_unused

        user_id = db_module.create_user("catdel1", "testpass")
        cat_id = db_module.add_category(user_id, "Empty", "house")

        result = delete_category_if_unused(cat_id, user_id)
        assert result.deleted is True
        assert result.reason == "ok"

    def test_delete_category_in_use(self, db_module):
        """Should refuse to delete category with expenses."""
        from src.db.operations import delete_category_if_unused

        user_id = db_module.create_user("catdel2", "testpass")
        cat_id = db_module.add_category(user_id, "InUse", "house")
        db_module.add_expense(user_id, "Rent", "InUse", 1000, "monthly")

        result = delete_category_if_unused(cat_id, user_id)
        assert result.deleted is False
        assert result.reason == "in_use"

    def test_delete_category_not_found(self, db_module):
        """Should return not_found for nonexistent category."""
        from src.db.operations import delete_category_if_unused

        user_id = db_module.create_user("catdel3", "testpass")
        result = delete_category_if_unused(99999, user_id)
        assert result.deleted is False
        assert result.reason == "not_found"

    def test_delete_unused_account(self, db_module):
        """Should delete account with no expenses."""
        from src.db.operations import delete_account_if_unused

        user_id = db_module.create_user("acctdel1", "testpass")
        acct_id = db_module.add_account(user_id, "Empty Acct")

        result = delete_account_if_unused(acct_id, user_id)
        assert result.deleted is True
        assert result.reason == "ok"

    def test_delete_account_in_use(self, db_module):
        """Should refuse to delete account with expenses."""
        from src.db.operations import delete_account_if_unused

        user_id = db_module.create_user("acctdel2", "testpass")
        acct_id = db_module.add_account(user_id, "UsedAcct")
        db_module.add_expense(user_id, "Rent", "Bolig", 1000, "monthly", account="UsedAcct")

        result = delete_account_if_unused(acct_id, user_id)
        assert result.deleted is False
        assert result.reason == "in_use"


class TestCreateUserWithDefaultCategories:
    """Tests for atomic user creation."""

    def test_creates_user_and_categories_atomically(self, db_module):
        """User and default categories should be created in one transaction."""
        from src.db.operations import create_user_with_default_categories

        user_id = create_user_with_default_categories("atomicuser", "testpass")
        assert user_id is not None

        categories = db_module.get_all_categories(user_id)
        assert len(categories) == 9  # DEFAULT_CATEGORIES has 9 entries

    def test_duplicate_username_returns_none(self, db_module):
        """Duplicate username should return None."""
        from src.db.operations import create_user_with_default_categories

        create_user_with_default_categories("dupuser", "testpass")
        result = create_user_with_default_categories("dupuser", "testpass2")
        assert result is None

    def test_email_hash_stored(self, db_module):
        """Email hash should be stored when email provided."""
        from src.db.operations import create_user_with_default_categories

        user_id = create_user_with_default_categories("emailuser", "testpass", email="test@example.com")
        user = db_module.get_user_by_id(user_id)
        assert user.email_hash is not None


class TestAccountRename:
    """Tests for rename_account_and_cascade_expenses."""

    def test_rename_cascades_to_expenses(self, db_module):
        """Renaming an account should update all expenses with the old name."""
        from src.db.operations import rename_account_and_cascade_expenses

        user_id = db_module.create_user("acctren1", "testpass")
        acct_id = db_module.add_account(user_id, "OldAcct")
        db_module.add_expense(user_id, "Rent", "Bolig", 1000, "monthly", account="OldAcct")

        count = rename_account_and_cascade_expenses(acct_id, user_id, "NewAcct")
        assert count == 1

        expenses = db_module.get_all_expenses(user_id)
        assert expenses[0].account == "NewAcct"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/saabendtsen/projects/family-budget && venv/bin/pytest tests/test_operations.py -v`
Expected: ImportError - `cannot import name 'rename_category_and_cascade_expenses'`

- [ ] **Step 3: Create operations.py**

Create `src/db/operations.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/saabendtsen/projects/family-budget && venv/bin/pytest tests/test_operations.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
cd /home/saabendtsen/projects/family-budget
git add src/db/operations.py tests/test_operations.py
git commit -m "feat(db): create operations.py with cross-domain operations

Typed results (CategoryUpdateResult, DeleteResult) replace bare int/bool.
Atomic create_user_with_default_categories fixes orphaned-user bug.
Part of #161."
```

---

### Task 4: Reduce `store.py` to re-export shim + update `__init__.py`

**Files:**
- Modify: `src/db/store.py` (replace 756 lines with ~15-line shim)
- Modify: `src/db/__init__.py` (update import sources, add backward-compat aliases)

- [ ] **Step 1: Replace store.py with re-export shim**

Replace entire `src/db/store.py` with:

```python
"""Backward-compatibility re-export shim.

All functions have moved to budget_store.py, identity_store.py, and operations.py.
This module re-exports everything so existing imports continue working.
"""

from .budget_store import *  # noqa: F401,F403
from .identity_store import *  # noqa: F401,F403
from .operations import *  # noqa: F401,F403

# Backward-compat aliases for renamed cross-domain operations
from .operations import create_user_with_default_categories as create_user  # noqa: F401
from .operations import delete_account_if_unused as _delete_account_if_unused  # noqa: F401
from .operations import delete_category_if_unused as _delete_category_if_unused  # noqa: F401
from .operations import rename_account_and_cascade_expenses as update_account  # noqa: F401
from .operations import rename_category_and_cascade_expenses as _rename_cat  # noqa: F401


def update_category(category_id: int, user_id: int, name: str, icon: str) -> int:
    """Backward-compat wrapper: returns int instead of CategoryUpdateResult."""
    return _rename_cat(category_id, user_id, name, icon).cascaded_expense_count


def delete_category(category_id: int, user_id: int) -> bool:
    """Backward-compat wrapper: returns bool instead of DeleteResult."""
    return _delete_category_if_unused(category_id, user_id).deleted


def delete_account(account_id: int, user_id: int) -> bool:
    """Backward-compat wrapper: returns bool instead of DeleteResult."""
    return _delete_account_if_unused(account_id, user_id).deleted
```

- [ ] **Step 2: Update __init__.py import sources**

Update `src/db/__init__.py` to import from new modules instead of store:

Replace the `from .store import (...)` block with:

```python
from .budget_store import (
    _calculate_yearly_overview,
    add_account,
    add_category,
    add_expense,
    add_income,
    delete_all_income,
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
    get_yearly_overview,
    update_expense,
    update_income,
)
from .identity_store import (
    authenticate_user,
    create_password_reset_token,
    get_user_by_email,
    get_user_by_id,
    get_user_by_username,
    get_user_count,
    get_valid_reset_token,
    mark_reset_token_used,
    update_last_login,
    update_user_email,
    update_user_password,
)
from .operations import (
    CategoryUpdateResult,
    DeleteResult,
    create_user_with_default_categories,
    delete_account_if_unused,
    delete_category_if_unused,
    migrate_user_categories,
    rename_account_and_cascade_expenses,
    rename_category_and_cascade_expenses,
)
# Backward-compat aliases (callers still use db.update_category, db.create_user, etc.)
from .store import create_user, delete_account, delete_category, update_account, update_category
```

Also add the new names to `__all__`:
- `CategoryUpdateResult`
- `DeleteResult`
- `create_user_with_default_categories`
- `delete_account_if_unused`
- `delete_category_if_unused`
- `rename_account_and_cascade_expenses`
- `rename_category_and_cascade_expenses`

Also add `transaction` to imports from connection:
```python
from .connection import DB_PATH, ensure_db_directory, get_connection, transaction
```

And add `"transaction"` to `__all__`.

- [ ] **Step 3: Verify import still works**

Run: `cd /home/saabendtsen/projects/family-budget && venv/bin/python -c "from src import database as db; print(db.create_user, db.update_category, db.delete_category, db.get_all_expenses); from src.db.facade import DataContext; print('facade OK')"`
Expected: prints function references and "facade OK" without error

- [ ] **Step 4: Commit**

```bash
cd /home/saabendtsen/projects/family-budget
git add src/db/store.py src/db/__init__.py
git commit -m "refactor(db): reduce store.py to re-export shim

store.py now re-exports from budget_store, identity_store, and operations.
Backward-compat aliases ensure all existing callers work unchanged.
Part of #161."
```

---

### Task 5: Update `facade.py` and `demo.py` imports

**Files:**
- Modify: `src/db/facade.py:19-32` (update imports)
- Modify: `src/db/demo.py:7` (update import)

- [ ] **Step 1: Update facade.py imports**

In `src/db/facade.py`, replace:
```python
from .store import (
    get_account_totals,
    ...
)
```

With:
```python
from .budget_store import (
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
```

- [ ] **Step 2: Update demo.py import**

In `src/db/demo.py`, replace:
```python
from .store import _calculate_yearly_overview
```

With:
```python
from .budget_store import _calculate_yearly_overview
```

- [ ] **Step 3: Verify imports work**

Run: `cd /home/saabendtsen/projects/family-budget && venv/bin/python -c "from src.db.facade import DataContext; from src.db.demo import get_yearly_overview_demo; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
cd /home/saabendtsen/projects/family-budget
git add src/db/facade.py src/db/demo.py
git commit -m "refactor(db): update facade.py and demo.py to import from new modules

Direct imports from budget_store instead of going through store.py shim.
Part of #161."
```

---

### Task 6: Run full test suite and verify backward compatibility

**Files:**
- No new files

- [ ] **Step 1: Run full test suite**

Run: `cd /home/saabendtsen/projects/family-budget && venv/bin/pytest -x -v 2>&1 | tail -40`
Expected: All tests pass (existing tests use `db_module` fixture which imports via `src.database` shim)

- [ ] **Step 2: Verify no ruff lint errors in new files**

Run: `cd /home/saabendtsen/projects/family-budget && venv/bin/ruff check src/db/budget_store.py src/db/identity_store.py src/db/operations.py src/db/store.py src/db/__init__.py`
Expected: No errors

- [ ] **Step 3: Fix any issues found in steps 1-2**

If tests fail, investigate and fix. Common issues:
- Missing imports in new modules
- `__all__` list not matching actual exports
- `database.py` shim not picking up new names

- [ ] **Step 4: Final commit if fixes needed**

```bash
cd /home/saabendtsen/projects/family-budget
git add -A
git commit -m "fix(db): address test/lint issues from store decomposition

Part of #161."
```

---

## Summary Table

| Module | Lines | Responsibility |
|--------|-------|---------------|
| `budget_store.py` | ~370 | Single-table CRUD: income, expenses, categories, accounts, aggregation |
| `identity_store.py` | ~160 | User/auth/token CRUD. No budget imports. |
| `operations.py` | ~120 | Cross-domain operations with typed results. Audit surface. |
| `store.py` | ~25 | Re-export shim + backward-compat wrappers |
| `connection.py` | ~45 | +`transaction()` context manager |

## What This PR Does NOT Do (future PRs)

1. **Route migration** - Routes still call `db.update_category()` etc. via aliases. Migrating routes to use `operations.py` directly is a separate PR per the issue.
2. **Remove aliases** - The backward-compat aliases in `store.py` stay until all routes are migrated.
3. **Add `conn` parameter to existing functions** - Functions still use `get_connection()` internally. Adding opt-in `conn` pass-through is a follow-up.
