# Remove Remaining Migration Helpers (issue #144) Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers-extended-cc:subagent-driven-development (if subagents available) or superpowers-extended-cc:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove two dead migration helper functions from `src/database.py` after confirming all production DB instances have the updated schema.

**Architecture:** `_create_tables` already creates both `categories` (with `user_id`) and `expenses` (with `category_id`, `account`, `months`) with the full schema for new databases. The three migration helpers (`_migrate_categories_add_user_id`, `_migrate_expenses_add_columns`, `_run_migrations`) only exist for pre-refactor databases. Once all live DBs have passed through `init_db`, they become dead code and can be safely deleted.

**Tech Stack:** Python 3.10+, SQLite (`sqlite3`), pytest, GitHub Actions CI

---

## Pre-flight: Context

**What the migration helpers do:**

| Function | Lines | What it does |
|---|---|---|
| `_migrate_categories_add_user_id` | 329–350 | Recreates `categories` to add `user_id` and change the UNIQUE constraint if `user_id` column is absent |
| `_migrate_expenses_add_columns` | 352–362 | Adds `category_id`, `account`, `months` columns to `expenses` if absent |
| `_run_migrations` | 365–368 | Calls the two above; invoked by `init_db()` |

**Why safe to remove:** `_create_tables` already creates both tables with all columns (confirmed at lines 278–304). Any DB that has had `init_db` run since the refactor already has the full schema. The production DB at `data/budget.db` has been confirmed to have all columns present.

---

## ## Chunk 1: Verify + Remove

### Task 1: Verify production DB is fully migrated

**Files:**
- Read-only: `data/budget.db` (production SQLite file at `/home/saabendtsen/projects/family-budget/data/budget.db`)

- [ ] **Step 1: Run PRAGMA checks on the production DB**

```bash
sqlite3 /home/saabendtsen/projects/family-budget/data/budget.db \
  "PRAGMA table_info(categories); PRAGMA table_info(expenses);"
```

Expected: `categories` has a `user_id` column (position 1). `expenses` has `category_id`, `account`, and `months` columns.

- [ ] **Step 2: Confirm result**

Both tables must have all expected columns before proceeding. If either is missing a column, **do not proceed** — file a comment on issue #144 instead.

---

### Task 2: Remove migration helpers from `src/database.py`

**Files:**
- Modify: `src/database.py:329-368`

- [ ] **Step 1: Write a failing test that asserts the dead functions are gone**

Add to `tests/test_database.py` (in a new class after `TestMonthsMigration`):

```python
class TestNoMigrationHelpers:
    """Ensure migration helper functions have been removed (issue #144)."""

    def test_migrate_categories_add_user_id_removed(self, db_module):
        assert not hasattr(db_module, "_migrate_categories_add_user_id"), \
            "_migrate_categories_add_user_id should have been removed"

    def test_migrate_expenses_add_columns_removed(self, db_module):
        assert not hasattr(db_module, "_migrate_expenses_add_columns"), \
            "_migrate_expenses_add_columns should have been removed"

    def test_run_migrations_removed(self, db_module):
        assert not hasattr(db_module, "_run_migrations"), \
            "_run_migrations should have been removed"
```

- [ ] **Step 2: Run the new tests to confirm they fail**

```bash
cd /home/saabendtsen/projects/family-budget
/home/saabendtsen/projects/family-budget/venv/bin/pytest tests/test_database.py::TestNoMigrationHelpers -v
```

Expected: 3 FAILED (functions still exist).

- [ ] **Step 3: Delete the three functions from `src/database.py`**

Remove lines 329–368 entirely (the three functions: `_migrate_categories_add_user_id`, `_migrate_expenses_add_columns`, `_run_migrations`).

The block to delete looks like this:
```python
def _migrate_categories_add_user_id(cur) -> None:
    ...

def _migrate_expenses_add_columns(cur) -> None:
    ...

def _run_migrations(cur) -> None:
    """Run schema migrations for existing databases."""
    _migrate_categories_add_user_id(cur)
    _migrate_expenses_add_columns(cur)
```

- [ ] **Step 4: Remove the `_run_migrations(cur)` call from `init_db()`**

In `src/database.py`, `init_db()` currently reads:
```python
def init_db():
    """Initialize database with schema and default data."""
    ensure_db_directory()
    conn = get_connection()
    cur = conn.cursor()
    _create_tables(cur)
    _run_migrations(cur)      # <-- delete this line
    _seed_default_categories(cur)
    conn.commit()
    conn.close()
```

Delete the `_run_migrations(cur)` line so it becomes:
```python
def init_db():
    """Initialize database with schema and default data."""
    ensure_db_directory()
    conn = get_connection()
    cur = conn.cursor()
    _create_tables(cur)
    _seed_default_categories(cur)
    conn.commit()
    conn.close()
```

- [ ] **Step 5: Run the new tests to confirm they pass**

```bash
/home/saabendtsen/projects/family-budget/venv/bin/pytest tests/test_database.py::TestNoMigrationHelpers -v
```

Expected: 3 PASSED.

---

### Task 3: Update migration-related tests

**Files:**
- Modify: `tests/test_database.py` (around line 1010)

Context: `TestMonthsMigration` (line 1010) contains two tests that verify the `months` column exists and that new expenses default to `None` months. These are valid schema-validity tests — they just have a misleading name. There are no tests that simulate a pre-migration DB state that need to be deleted.

- [ ] **Step 1: Rename `TestMonthsMigration` to `TestExpenseSchemaColumns`**

In `tests/test_database.py` at line 1010, change:
```python
class TestMonthsMigration:
    """Tests for months column migration."""
```
to:
```python
class TestExpenseSchemaColumns:
    """Tests that expense schema has all required columns."""
```

- [ ] **Step 2: Run the renamed class to verify it still passes**

```bash
/home/saabendtsen/projects/family-budget/venv/bin/pytest tests/test_database.py::TestExpenseSchemaColumns -v
```

Expected: 2 PASSED.

- [ ] **Step 3: Commit**

```bash
cd /home/saabendtsen/projects/family-budget
git add src/database.py tests/test_database.py
git commit -m "refactor: remove dead migration helpers (issue #144)

_migrate_categories_add_user_id, _migrate_expenses_add_columns, and
_run_migrations are dead code — all live DB instances have the updated
schema. _create_tables already creates the full schema for new DBs.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## ## Chunk 2: Validate + Ship

### Task 4: Run full test suite and open PR

**Files:**
- No file changes — run, verify, push.

- [ ] **Step 1: Run the full test suite**

```bash
cd /home/saabendtsen/projects/family-budget
/home/saabendtsen/projects/family-budget/venv/bin/pytest tests/ -v 2>&1 | tail -20
```

Expected: all tests pass (green). If any test fails, investigate before continuing.

- [ ] **Step 2: Create a feature branch (if not already on one)**

```bash
cd /home/saabendtsen/projects/family-budget
git checkout -b remove-migration-helpers
# If the commit was made on master, cherry-pick or rebase as needed
```

Note: per project convention (`CLAUDE.md`), never commit directly to `master`. If the commit from Task 3 was made on `master`, create the branch first, reset, and re-commit:
```bash
git checkout master
git checkout -b remove-migration-helpers
```
Then re-apply the changes on the branch.

- [ ] **Step 3: Push branch and open PR**

```bash
git push -u origin remove-migration-helpers
gh pr create \
  --repo saabendtsen/family-budget \
  --title "refactor: remove dead migration helpers (#144)" \
  --body "$(cat <<'EOF'
## Summary
- Removes `_migrate_categories_add_user_id`, `_migrate_expenses_add_columns`, and `_run_migrations` from `src/database.py`
- Removes `_run_migrations(cur)` call from `init_db()`
- Renames `TestMonthsMigration` → `TestExpenseSchemaColumns` (tests were schema-validity checks, not migration-path tests)

## Verification
Production DB at `data/budget.db` confirmed to have all migrated columns before removal:
- `categories.user_id` present
- `expenses.category_id`, `account`, `months` present

`_create_tables` already creates the full schema for new databases, so these helpers have been dead code since the `init_db` refactor (issue #133).

Closes #144

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
