# Seal DataContext Facade with Dependency Injection (Issue #160)

> **For agentic workers:** REQUIRED: Use superpowers-extended-cc:subagent-driven-development (if subagents available) or superpowers-extended-cc:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove DataContext construction boilerplate from 7 route files by injecting it via a single FastAPI dependency, add a BudgetReader Protocol for type safety, and expose a `writable` property.

**Architecture:** A new `get_data` FastAPI dependency in `dependencies.py` consolidates auth checking + cookie inspection + DataContext construction into one injectable. Routes receive `ctx: DataContext = Depends(get_data)` instead of manually calling `is_demo_mode()`, `is_demo_advanced()`, `get_user_id()`, and constructing DataContext. A `BudgetReader` Protocol in `src/db/ports.py` provides a type contract for test substitution.

**Tech Stack:** Python 3.12, FastAPI, pytest

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `src/db/ports.py` | `BudgetReader` Protocol (type contract) |
| Modify | `src/db/facade.py:42-45` | Add `writable` property to DataContext |
| Modify | `src/dependencies.py:15-17` | Add `get_data` dependency |
| Modify | `src/routes/dashboard.py:6-13,20-27` | Use `Depends(get_data)`, remove boilerplate |
| Modify | `src/routes/expenses.py:10-18,89-95` | Use `Depends(get_data)`, remove boilerplate |
| Modify | `src/routes/income.py:10-18,26-32` | Use `Depends(get_data)`, remove boilerplate |
| Modify | `src/routes/categories.py:10-17,25-30` | Use `Depends(get_data)`, remove boilerplate |
| Modify | `src/routes/accounts.py:10-18,26-31` | Use `Depends(get_data)`, remove boilerplate |
| Modify | `src/routes/yearly.py:6-12,18-23` | Use `Depends(get_data)`, remove boilerplate |
| Modify | `src/routes/api_endpoints.py:7-13,40-51` | Use `Depends(get_data)`, remove boilerplate |
| Create | `tests/test_get_data.py` | Tests for `get_data` dependency |
| Modify | `tests/test_data_context.py` | Add Protocol conformance test |

**Not modified:**
- `src/routes/pages.py` — uses `is_demo_mode()` directly for template-only rendering (no DataContext)
- `src/routes/settings.py` — uses `get_user_id()` for write ops only
- `src/routes/auth.py`, `password_reset.py` — no DataContext usage
- `require_write` — stays separate (write routes have different guard semantics)
- JSON endpoints in `accounts.py:add_account_json` — keeps explicit 401/403 checks

---

### Task 1: Add BudgetReader Protocol and writable property

**Files:**
- Create: `src/db/ports.py`
- Modify: `src/db/facade.py:42-45`
- Modify: `tests/test_data_context.py`

- [ ] **Step 1: Write Protocol conformance test**

Add to `tests/test_data_context.py`:

```python
class TestBudgetReaderProtocol:
    """DataContext must satisfy BudgetReader at runtime."""

    def test_datacontext_satisfies_budget_reader(self):
        from src.db.facade import DataContext
        from src.db.ports import BudgetReader
        ctx = DataContext(user_id=0, demo=True)
        assert isinstance(ctx, BudgetReader)
```

- [ ] **Step 2: Write writable property test**

Add to `tests/test_data_context.py`:

```python
class TestWritableProperty:
    """writable is False in demo, True in real mode."""

    def test_demo_not_writable(self):
        from src.db.facade import DataContext
        ctx = DataContext(user_id=0, demo=True)
        assert ctx.writable is False

    def test_real_is_writable(self):
        from src.db.facade import DataContext
        ctx = DataContext(user_id=1, demo=False)
        assert ctx.writable is True
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd ~/projects/family-budget && venv/bin/pytest tests/test_data_context.py -v -k "Protocol or Writable" 2>&1 | distill "did the tests fail?"`
Expected: FAIL — `ports` module not found, `writable` attribute missing.

- [ ] **Step 4: Create `src/db/ports.py` with BudgetReader Protocol**

```python
"""Port interfaces for data access.

BudgetReader defines the read-only contract that DataContext satisfies.
Use for type-checking and test substitution (FakeReader).
"""

from typing import Protocol, runtime_checkable

from .models import Account, Category, Expense, Income


@runtime_checkable
class BudgetReader(Protocol):
    """Read-only budget data access contract."""

    def expenses(self) -> list[Expense]: ...
    def income(self) -> list[Income]: ...
    def categories(self) -> list[Category]: ...
    def accounts(self) -> list[Account]: ...
    def category_totals(self) -> dict[str, float]: ...
    def account_totals(self) -> dict[str, float]: ...
    def total_income(self) -> float: ...
    def total_expenses(self) -> float: ...
    def yearly_overview(self) -> dict: ...
    def expenses_by_category(self) -> dict[str, list[Expense]]: ...
    def category_usage(self) -> dict[str, int]: ...
    def account_usage(self) -> dict[str, int]: ...
```

- [ ] **Step 5: Add `writable` property to DataContext**

In `src/db/facade.py`, after line 45 (`self.advanced = advanced`), add:

```python
    @property
    def writable(self) -> bool:
        """True when mutations are allowed (non-demo mode)."""
        return not self.demo
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd ~/projects/family-budget && venv/bin/pytest tests/test_data_context.py -v -k "Protocol or Writable" 2>&1 | distill "did the tests pass?"`
Expected: 3 PASSED.

- [ ] **Step 7: Commit**

```bash
cd ~/projects/family-budget
git add src/db/ports.py src/db/facade.py tests/test_data_context.py
git commit -m "feat: add BudgetReader Protocol and writable property (#160)"
```

---

### Task 2: Add `get_data` dependency

**Files:**
- Modify: `src/dependencies.py:15-17`
- Create: `tests/test_get_data.py`

- [ ] **Step 1: Write baseline tests for `get_data`**

Create `tests/test_get_data.py`:

```python
"""Tests for get_data dependency — resolves auth + demo + DataContext."""
import pytest
from unittest.mock import patch

from starlette.testclient import TestClient


class TestGetDataDependency:
    """get_data returns correctly configured DataContext."""

    def test_demo_mode_returns_demo_context(self, client):
        """Demo session → ctx.demo=True."""
        client.cookies.set("budget_session", "demo")
        response = client.get("/budget/", follow_redirects=False)
        # If we reach 200, the dependency resolved successfully
        assert response.status_code == 200

    def test_unauthenticated_redirects_to_login(self, client):
        """No session → AuthRequired → redirect to login."""
        response = client.get("/budget/", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/budget/login"

    def test_authenticated_returns_real_context(self, authenticated_client):
        """Valid session → ctx.demo=False, real data."""
        response = authenticated_client.get("/budget/", follow_redirects=False)
        assert response.status_code == 200
```

- [ ] **Step 2: Run tests to verify they pass (baseline)**

Run: `cd ~/projects/family-budget && venv/bin/pytest tests/test_get_data.py -v 2>&1 | distill "did the tests pass?"`
Expected: PASS (tests exercise existing routes, establishing baseline before migration).

- [ ] **Step 3: Add `get_data` dependency to `src/dependencies.py`**

Add imports and function after the existing `require_write` function:

```python
from .db.facade import DataContext
from .helpers import check_auth, get_user_id, is_demo_advanced, is_demo_mode


async def get_data(request: Request) -> DataContext:
    """Dependency: resolve auth + demo state + DataContext in one step.

    Raises AuthRequired if unauthenticated. Routes using Depends(get_data)
    don't need a separate Depends(require_auth).
    """
    if not check_auth(request):
        raise AuthRequired()
    demo = is_demo_mode(request)
    advanced = is_demo_advanced(request)
    user_id = get_user_id(request)
    return DataContext(user_id=user_id, demo=demo, advanced=advanced)
```

Note: The existing import `from .helpers import check_auth, is_demo_mode` on line 17 must be updated to include `get_user_id` and `is_demo_advanced`.

- [ ] **Step 4: Run tests to verify they still pass**

Run: `cd ~/projects/family-budget && venv/bin/pytest tests/test_get_data.py tests/test_dependencies.py -v 2>&1 | distill "did the tests pass?"`
Expected: All PASS. `get_data` exists but isn't wired into routes yet.

- [ ] **Step 5: Commit**

```bash
cd ~/projects/family-budget
git add src/dependencies.py tests/test_get_data.py
git commit -m "feat: add get_data dependency for DataContext injection (#160)"
```

---

### Task 3: Migrate 7 route files to `Depends(get_data)`

**Files:**
- Modify: `src/routes/dashboard.py`
- Modify: `src/routes/expenses.py`
- Modify: `src/routes/income.py`
- Modify: `src/routes/categories.py`
- Modify: `src/routes/accounts.py`
- Modify: `src/routes/yearly.py`
- Modify: `src/routes/api_endpoints.py`

Each route follows the same mechanical pattern. The migration for each file is:

1. Replace `from ..dependencies import require_auth` with `from ..dependencies import get_data` (keep `require_write` where used)
2. Remove `from ..db.facade import DataContext` import (DataContext comes via the dependency now — but keep the import for type annotation)
3. Remove unused `is_demo_mode`, `is_demo_advanced`, `get_user_id` from helpers import (keep any still used by write routes or template-only usage)
4. Change `_: None = Depends(require_auth)` to `ctx: DataContext = Depends(get_data)` in GET route signatures
5. Delete the 3-4 line construction block (`demo = ...`, `advanced = ...`, `user_id = ...`, `ctx = DataContext(...)`)
6. Replace `demo` with `ctx.demo` and `advanced` with `ctx.advanced` in template context dicts

- [ ] **Step 1: Migrate `dashboard.py`**

Before:
```python
from ..db.facade import DataContext
from ..dependencies import require_auth
from ..helpers import (
    get_user_id,
    is_demo_advanced,
    is_demo_mode,
    templates,
)

async def dashboard(request: Request, _: None = Depends(require_auth)):
    demo = is_demo_mode(request)
    advanced = is_demo_advanced(request)
    user_id = get_user_id(request)
    ctx = DataContext(user_id=user_id, demo=demo, advanced=advanced)
    ...
    "demo_mode": demo,
    "demo_advanced": advanced,
```

After:
```python
from ..db.facade import DataContext
from ..dependencies import get_data
from ..helpers import templates

async def dashboard(request: Request, ctx: DataContext = Depends(get_data)):
    ...
    "demo_mode": ctx.demo,
    "demo_advanced": ctx.advanced,
```

- [ ] **Step 2: Migrate `expenses.py`** (GET route only)

Only change `expenses_page`. Write routes (`add_expense`, `delete_expense`, `edit_expense`) keep `require_write` and manual `get_user_id`.

Before:
```python
from ..db.facade import DataContext
from ..dependencies import require_auth, require_write
from ..helpers import (
    get_user_id,
    is_demo_advanced,
    is_demo_mode,
    parse_danish_amount,
    templates,
)

async def expenses_page(request: Request, _: None = Depends(require_auth)):
    user_id = get_user_id(request)
    demo = is_demo_mode(request)
    advanced = is_demo_advanced(request)
    ctx = DataContext(user_id=user_id, demo=demo, advanced=advanced)
    ...
    "demo_mode": demo,
    "demo_advanced": advanced,
```

After:
```python
from ..db.facade import DataContext
from ..dependencies import get_data, require_write
from ..helpers import (
    get_user_id,
    parse_danish_amount,
    templates,
)

async def expenses_page(request: Request, ctx: DataContext = Depends(get_data)):
    ...
    "demo_mode": ctx.demo,
    "demo_advanced": ctx.advanced,
```

Note: Keep `get_user_id` — it's used in write routes (`add_expense`, `edit_expense`, `delete_expense`).
Remove `is_demo_mode`, `is_demo_advanced` — no longer used after migration.

- [ ] **Step 3: Migrate `income.py`** (GET route only)

Write route (`update_income`) keeps `require_write` and `get_user_id`.

After:
```python
from ..db.facade import DataContext
from ..dependencies import get_data, require_write
from ..helpers import (
    get_user_id,
    parse_danish_amount,
    templates,
)

async def income_page(request: Request, ctx: DataContext = Depends(get_data)):
    incomes = ctx.income()
    return templates.TemplateResponse(
        "income.html",
        {"request": request, "incomes": incomes, "demo_mode": ctx.demo, "demo_advanced": ctx.advanced}
    )
```

- [ ] **Step 4: Migrate `categories.py`** (GET route only)

Write routes keep `require_write` and `get_user_id`.

After:
```python
from ..db.facade import DataContext
from ..dependencies import get_data, require_write
from ..helpers import (
    get_user_id,
    templates,
)

async def categories_page(request: Request, ctx: DataContext = Depends(get_data)):
    categories = ctx.categories()
    category_usage = ctx.category_usage()
    return templates.TemplateResponse(
        "categories.html",
        {
            "request": request,
            "categories": categories,
            "category_usage": category_usage,
            "demo_mode": ctx.demo,
            "demo_advanced": ctx.advanced,
        }
    )
```

Note: The old code called `is_demo_advanced(request)` separately in the template dict. Now it's `ctx.advanced`.

- [ ] **Step 5: Migrate `accounts.py`** (GET route only)

Write routes and `add_account_json` keep their existing patterns.

After:
```python
from ..db.facade import DataContext
from ..dependencies import get_data, require_write
from ..helpers import (
    check_auth,
    get_user_id,
    is_demo_mode,
    templates,
)

async def accounts_page(request: Request, ctx: DataContext = Depends(get_data)):
    accounts = ctx.accounts()
    account_usage = ctx.account_usage()
    return templates.TemplateResponse(
        "accounts.html",
        {
            "request": request,
            "accounts": accounts,
            "account_usage": account_usage,
            "demo_mode": ctx.demo,
            "demo_advanced": ctx.advanced,
        }
    )
```

Note: Keep `check_auth`, `is_demo_mode`, `get_user_id` — used by `add_account_json` and write routes. Remove `is_demo_advanced` — was only used in `accounts_page`.

- [ ] **Step 6: Migrate `yearly.py`**

This file has only one route and no write routes.

After:
```python
from ..db.facade import DataContext
from ..dependencies import get_data
from ..helpers import templates

async def yearly_overview_page(request: Request, ctx: DataContext = Depends(get_data)):
    overview = ctx.yearly_overview()
    return templates.TemplateResponse("yearly.html", {
        "request": request,
        "overview": overview,
        "demo_mode": ctx.demo,
    })
```

- [ ] **Step 7: Migrate `api_endpoints.py`** (chart_data only)

`health` and `api_stats` are public (no auth). Only `chart_data` uses DataContext.

After:
```python
from ..db.facade import DataContext
from ..dependencies import get_data
from ..helpers import (empty — remove entire helpers import if not needed)
```

After:
```python
from .. import database as db
from ..db.facade import DataContext
from ..dependencies import get_data

# Remove the entire `from ..helpers import (...)` block — no helpers needed after migration.

async def chart_data(request: Request, ctx: DataContext = Depends(get_data)):
    category_totals = ctx.category_totals()
    total_income = ctx.total_income()
    total_expenses = ctx.total_expenses()
    expenses = ctx.expenses()
    ...
```

- [ ] **Step 8: Run full test suite**

Run: `cd ~/projects/family-budget && venv/bin/pytest -x 2>&1 | distill "did all tests pass? how many?"`
Expected: All 396+ tests PASS. No behavior change — the dependency resolves identically.

- [ ] **Step 9: Commit**

```bash
cd ~/projects/family-budget
git add src/routes/dashboard.py src/routes/expenses.py src/routes/income.py \
        src/routes/categories.py src/routes/accounts.py src/routes/yearly.py \
        src/routes/api_endpoints.py
git commit -m "refactor: migrate 7 routes to Depends(get_data) (#160)"
```

---

### Task 4: Final verification and cleanup

**Files:**
- All modified files from Tasks 1-3

- [ ] **Step 1: Run ruff linter**

Run: `cd ~/projects/family-budget && venv/bin/ruff check src/ 2>&1 | distill "any lint errors?"`
Expected: Clean. Fix any unused import warnings.

- [ ] **Step 2: Run full test suite one more time**

Run: `cd ~/projects/family-budget && venv/bin/pytest -x 2>&1 | distill "did all tests pass? how many?"`
Expected: All tests PASS.

- [ ] **Step 3: Verify no remaining boilerplate**

Run: `grep -rn "DataContext(user_id=" src/routes/`
Expected: Zero matches. All DataContext construction now happens in `get_data`.

- [ ] **Step 4: Commit any cleanup**

If ruff found unused imports, commit the fix:
```bash
git add -u && git commit -m "chore: remove unused imports after DI migration (#160)"
```
