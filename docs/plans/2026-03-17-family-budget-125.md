# Fix Database Connection Leak (Issue #125) Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers-extended-cc:subagent-driven-development (if subagents available) or superpowers-extended-cc:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate SQLite connection leaks in `src/database.py` by converting `get_connection()` to a `contextlib.contextmanager` and wrapping all 38 call sites with `with get_connection() as conn:`.

**Architecture:** The current pattern calls `conn = get_connection()` then `conn.close()` at the end — any exception between open and close leaks the connection and holds a file lock. The fix converts `get_connection()` into a `@contextmanager` that guarantees `conn.close()` in a `finally` block, then migrates every function body to use a `with` statement. Explicit `conn.commit()` calls are preserved inside the `with` blocks (no auto-commit behavior change).

**Tech Stack:** Python 3.10+, `contextlib.contextmanager`, `sqlite3`, `pytest`

---

## Chunk 1: Context Manager + Tests

### Task 1: Write failing tests for context manager behavior

**Files:**
- Create: `tests/test_connection_manager.py`

These tests verify the new `get_connection()` is a real context manager that always closes the connection, even on exceptions.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_connection_manager.py`:

```python
"""Tests for get_connection() context manager safety."""
import sqlite3
from unittest.mock import MagicMock, patch, call
import pytest


class TestGetConnectionContextManager:
    """Verify get_connection() is a context manager that prevents leaks."""

    def test_get_connection_is_context_manager(self, db_module):
        """get_connection() must be usable as a context manager."""
        with db_module.get_connection() as conn:
            assert conn is not None
            assert isinstance(conn, sqlite3.Connection)

    def test_connection_closed_on_normal_exit(self, db_module):
        """Connection must be closed after normal with-block exit."""
        with db_module.get_connection() as conn:
            captured = conn  # hold reference outside

        # After the with block, executing on the closed connection should fail
        with pytest.raises(Exception):
            captured.execute("SELECT 1")

    def test_connection_closed_on_exception(self, db_module):
        """Connection must be closed even when the with-block raises."""
        captured = None
        with pytest.raises(ValueError):
            with db_module.get_connection() as conn:
                captured = conn
                raise ValueError("simulated failure")

        # Connection should be closed despite the exception
        with pytest.raises(Exception):
            captured.execute("SELECT 1")

    def test_row_factory_set(self, db_module):
        """Connection must have row_factory = sqlite3.Row."""
        with db_module.get_connection() as conn:
            assert conn.row_factory is sqlite3.Row
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/saabendtsen/projects/family-budget && \
  /home/saabendtsen/projects/family-budget/venv/bin/pytest tests/test_connection_manager.py -v 2>&1 | \
  /home/saabendtsen/.npm-global/bin/distill "do the tests fail as expected?"
```

Expected: `test_get_connection_is_context_manager` FAILS (get_connection returns a Connection, not a context manager), others also FAIL.

- [ ] **Step 3: Commit the failing tests**

```bash
cd /home/saabendtsen/projects/family-budget && \
  git add tests/test_connection_manager.py && \
  git commit -m "test: add failing tests for get_connection context manager safety"
```

---

### Task 2: Convert get_connection() to context manager

**Files:**
- Modify: `src/database.py:1-10` (add `contextmanager` import)
- Modify: `src/database.py:240-244` (rewrite `get_connection`)

- [ ] **Step 1: Add `contextmanager` to the imports**

At line 3, the file imports `hashlib`. The `contextlib` import goes at the top of the stdlib block. Current imports (lines 3-8):

```python
import hashlib
import json
import os
import secrets
import sqlite3
from dataclasses import dataclass
from pathlib import Path
```

Change to:

```python
import hashlib
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
```

- [ ] **Step 2: Rewrite get_connection() as a context manager**

Current `src/database.py:240-244`:

```python
def get_connection() -> sqlite3.Connection:
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
```

Replace with:

```python
@contextmanager
def get_connection():
    """Get database connection as a context manager. Always closes on exit."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
```

- [ ] **Step 3: Run the new context manager tests to verify they pass**

```bash
cd /home/saabendtsen/projects/family-budget && \
  /home/saabendtsen/projects/family-budget/venv/bin/pytest tests/test_connection_manager.py -v 2>&1 | \
  /home/saabendtsen/.npm-global/bin/distill "do all 4 tests pass?"
```

Expected: All 4 PASS.

- [ ] **Step 4: Commit**

```bash
cd /home/saabendtsen/projects/family-budget && \
  git add src/database.py && \
  git commit -m "feat: convert get_connection() to contextlib context manager"
```

---

## Chunk 2: Migrate Function Bodies

### Task 3: Update init_db() and income functions (lines 380–466)

**Files:**
- Modify: `src/database.py:380-466`

**Background:** All functions follow the same mechanical pattern. For read-only functions:

```python
# BEFORE
conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT ...")
rows = cur.fetchall()
conn.close()
return rows

# AFTER
with get_connection() as conn:
    cur = conn.cursor()
    cur.execute("SELECT ...")
    rows = cur.fetchall()
return rows
```

For write functions (with `conn.commit()`):

```python
# BEFORE
conn = get_connection()
cur = conn.cursor()
cur.execute("INSERT ...")
result = cur.lastrowid
conn.commit()
conn.close()
return result

# AFTER
with get_connection() as conn:
    cur = conn.cursor()
    cur.execute("INSERT ...")
    result = cur.lastrowid
    conn.commit()
return result
```

Note: `conn.commit()` stays explicit inside the `with` block. The context manager only guarantees `close()`.

**Functions to migrate in this task:**

| Line | Function |
|------|----------|
| 380 | `init_db` |
| 396 | `get_all_income` |
| 409 | `add_income` |
| 423 | `update_income` |
| 441 | `get_total_income` |
| 461 | `delete_all_income` |

- [ ] **Step 1: Apply the with-block pattern to init_db() (~line 380)**

Current:
```python
def init_db():
    """Initialize database with schema and default data."""
    ensure_db_directory()
    conn = get_connection()
    cur = conn.cursor()
    _create_tables(cur)
    _run_migrations(cur)
    _seed_default_categories(cur)
    conn.commit()
    conn.close()
```

New:
```python
def init_db():
    """Initialize database with schema and default data."""
    ensure_db_directory()
    with get_connection() as conn:
        cur = conn.cursor()
        _create_tables(cur)
        _run_migrations(cur)
        _seed_default_categories(cur)
        conn.commit()
```

- [ ] **Step 2: Apply the pattern to get_all_income(), add_income(), update_income(), get_total_income(), delete_all_income()**

For `get_all_income` (~line 396):
```python
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
```

For `delete_all_income` (~line 461) — uses `conn.execute()` directly (no cursor):
```python
def delete_all_income(user_id: int):
    """Delete all income entries for a user."""
    with get_connection() as conn:
        conn.execute("DELETE FROM income WHERE user_id = ?", (user_id,))
        conn.commit()
```

Apply the same pattern to the remaining income functions.

- [ ] **Step 3: Run the existing income tests to verify no regressions**

```bash
cd /home/saabendtsen/projects/family-budget && \
  /home/saabendtsen/projects/family-budget/venv/bin/pytest tests/test_database.py::TestIncomeOperations -v 2>&1 | \
  /home/saabendtsen/.npm-global/bin/distill "did the income tests pass?"
```

Expected: All PASS.

- [ ] **Step 4: Commit**

```bash
cd /home/saabendtsen/projects/family-budget && \
  git add src/database.py && \
  git commit -m "refactor: migrate income and init_db functions to context manager"
```

---

### Task 4: Update expense functions

**Files:**
- Modify: `src/database.py` (expense section, roughly lines 473–600)

**Functions to migrate:**

| Approx. Line | Function |
|------|----------|
| 473 | `get_all_expenses` |
| 493 | `get_expense_by_id` |
| 510 | `add_expense` |
| ~528 | `update_expense` |
| ~543 | `delete_expense` |
| ~552 | `get_expenses_by_category` |
| ~598 | `get_total_expenses` |
| ~611 | any remaining expense helpers |

Apply the same `with get_connection() as conn:` pattern to each function, keeping `conn.commit()` for write operations. Remove the standalone `conn.close()` call from each.

- [ ] **Step 1: Migrate all expense functions**

For `get_all_expenses` (has `json.loads` post-processing outside conn block):
```python
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
```

Note: Post-processing `rows` happens outside the `with` block (rows already fetched into memory). This is correct.

Apply the same pattern to all expense functions.

- [ ] **Step 2: Run expense tests**

```bash
cd /home/saabendtsen/projects/family-budget && \
  /home/saabendtsen/projects/family-budget/venv/bin/pytest tests/test_expenses.py tests/test_database.py -v -k "expense or Expense" 2>&1 | \
  /home/saabendtsen/.npm-global/bin/distill "did all expense tests pass?"
```

Expected: All PASS.

- [ ] **Step 3: Commit**

```bash
cd /home/saabendtsen/projects/family-budget && \
  git add src/database.py && \
  git commit -m "refactor: migrate expense functions to context manager"
```

---

### Task 5: Update categories, accounts, and user functions

**Files:**
- Modify: `src/database.py` (lines ~620 onwards — categories, accounts, users, tokens, yearly overview)

**Functions to migrate (grep output shows these call sites):**

Lines with `conn = get_connection()`: 621, 638, 673, 712, 727, 744, 789, 802, 812, 829, 861, 894, 934, 968, 987, 1001, 1019, 1039, 1058, 1069, 1083, 1101, 1121

That covers: category CRUD, account CRUD, user CRUD (`create_user`, `get_user_by_username`, `update_last_login`, `update_password`, `delete_user`, etc.), password reset token functions, and any remaining helpers.

Apply the exact same `with get_connection() as conn:` pattern to each, keeping explicit `conn.commit()` for write functions and removing all `conn.close()` calls.

- [ ] **Step 1: Migrate categories functions**

Pattern (same as before):
```python
def get_categories(user_id: int) -> list[Category]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT ... WHERE user_id = ?", (user_id,))
        rows = cur.fetchall()
    return [Category(**dict(row)) for row in rows]
```

- [ ] **Step 2: Migrate accounts functions**

Same pattern. Write functions keep `conn.commit()` inside the `with` block.

- [ ] **Step 3: Migrate user CRUD and token functions**

Same pattern. Verify that `create_user` (which returns the new user id via `cur.lastrowid`) keeps the return inside the `with` block:

```python
def create_user(username: str, password: str) -> int:
    ...
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO users ...", (...))
        user_id = cur.lastrowid
        conn.commit()
    return user_id
```

- [ ] **Step 4: Run auth and user tests**

```bash
cd /home/saabendtsen/projects/family-budget && \
  /home/saabendtsen/projects/family-budget/venv/bin/pytest tests/test_auth.py tests/test_database.py -v 2>&1 | \
  /home/saabendtsen/.npm-global/bin/distill "did all auth and database tests pass?"
```

Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/saabendtsen/projects/family-budget && \
  git add src/database.py && \
  git commit -m "refactor: migrate categories, accounts, users, token functions to context manager"
```

---

## Chunk 3: Verification and PR

### Task 6: Run full test suite and verify zero conn.close() calls remain

**Files:** None (verification only)

- [ ] **Step 1: Verify no bare conn.close() calls remain in database.py**

```bash
grep -n "conn\.close()" /home/saabendtsen/projects/family-budget/src/database.py
```

Expected: No output (zero matches).

- [ ] **Step 2: Verify all get_connection() calls are inside with statements**

```bash
grep -n "conn = get_connection()" /home/saabendtsen/projects/family-budget/src/database.py
```

Expected: No output (all converted to `with get_connection() as conn:`).

- [ ] **Step 3: Run full test suite**

```bash
cd /home/saabendtsen/projects/family-budget && \
  /home/saabendtsen/projects/family-budget/venv/bin/pytest tests/ -v 2>&1 | \
  /home/saabendtsen/.npm-global/bin/distill "did all tests pass? list any failures"
```

Expected: All tests PASS.

- [ ] **Step 4: Open a PR**

```bash
cd /home/saabendtsen/projects/family-budget && \
  git push -u origin HEAD && \
  gh pr create \
    --repo saabendtsen/family-budget \
    --title "fix: eliminate database connection leak (issue #125)" \
    --body "$(cat <<'EOF'
## Summary

- Converts `get_connection()` to a `@contextmanager` that always calls `conn.close()` in a `finally` block
- Migrates all 38 call sites to `with get_connection() as conn:` pattern
- Explicit `conn.commit()` calls preserved inside `with` blocks (no transaction behavior change)
- Adds 4 tests verifying connection is closed on normal exit and on exceptions

Closes #125

## Test plan
- [ ] `tests/test_connection_manager.py` — 4 new tests for context manager safety
- [ ] Full test suite passes: `pytest tests/ -v`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
