# Extract Auth/Demo Guard into FastAPI Dependency — Issue #127

> **For agentic workers:** REQUIRED: Use superpowers-extended-cc:subagent-driven-development (if subagents available) or superpowers-extended-cc:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace 22 boilerplate `check_auth` guards and 13 `is_demo_mode` guards across route files with reusable FastAPI `Depends()` dependencies, eliminating ~70 lines of repeated boilerplate.

**Architecture:** Create `src/dependencies.py` with two custom exception classes (`AuthRequired`, `DemoBlocked`) and two dependency callables (`require_auth`, `require_write`). Register `@app.exception_handler` for each exception in `src/api.py` that converts them to the correct `RedirectResponse`. Route handlers replace two-line boilerplate guards with a single `_: None = Depends(...)` in their signature. The JSON endpoint `add_account_json` (which uses 401/403 JSON responses, not redirects) is intentionally left with explicit checks — two cases don't warrant a separate JSON variant.

**Tech Stack:** FastAPI `Depends()`, Starlette exception handlers, pytest

---

## Scope Reference

| File | `check_auth` guards | `is_demo_mode` guards | Demo redirect URL |
|------|--------------------|-----------------------|-------------------|
| `src/routes/accounts.py` | 4 (incl. 1 JSON) | 4 (incl. 1 JSON) | `/budget/accounts` (HTML), 401/403 JSON |
| `src/routes/categories.py` | 4 | 3 | `/budget/categories` |
| `src/routes/expenses.py` | 3 | 2 | `/budget/expenses` |
| `src/routes/income.py` | 2 | 1 | `/budget/` |
| `src/routes/dashboard.py` | 1 | 0 | — |
| `src/routes/settings.py` | 2 | 2 | `/budget/` |
| `src/routes/pages.py` | 2 | 0 | — |
| `src/routes/yearly.py` | 1 | 0 | — |
| `src/routes/api_endpoints.py` | 1 | 0 | — |

**Note:** Soft checks like `demo = is_demo_mode(request)` (used to select demo data, not as guards) are NOT replaced — they remain in route bodies.

---

## Chunk 1: Foundation

### Task 1: Baseline + write behavior tests

**Files:**
- Create: `tests/test_dependencies.py`

- [ ] **Step 1: Verify baseline**

```bash
cd ~/projects/family-budget
python -m pytest tests/ -x -q 2>&1 | distill "did all tests pass?"
```

Expected: all tests green.

- [ ] **Step 2: Create feature branch**

```bash
cd ~/projects/family-budget
git checkout -b feat/auth-dependency-127
```

- [ ] **Step 3: Write behavior tests**

Create `tests/test_dependencies.py`:

```python
"""Behavior tests for auth/demo guard dependencies.

These tests document the expected redirect behavior that must be preserved
after the check_auth/is_demo_mode boilerplate is replaced with Depends().
They serve as regression protection — they pass against both the old and
new implementations.
"""


class TestRequireAuth:
    """require_auth: unauthenticated requests redirect to login."""

    def test_unauthenticated_get_redirects_to_login(self, client):
        """GET /budget/expenses without session cookie should redirect to login."""
        response = client.get("/budget/expenses", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/budget/login"

    def test_unauthenticated_post_redirects_to_login(self, client):
        """POST mutation without session cookie should redirect to login."""
        response = client.post(
            "/budget/expenses/add",
            data={"name": "x", "category": "y", "amount": "1", "frequency": "monthly"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/budget/login"

    def test_authenticated_get_passes_through(self, authenticated_client):
        """GET /budget/expenses with valid session should not redirect to login."""
        response = authenticated_client.get("/budget/expenses", follow_redirects=False)
        # 200 = page rendered; 303 = some other redirect (e.g. empty state) — both are fine
        assert response.status_code in (200, 303)
        assert response.headers.get("location", "") != "/budget/login"


class TestRequireWrite:
    """require_write: demo mode is blocked on mutation routes."""

    def test_demo_add_expense_redirects_to_expenses(self, client):
        """Demo user POSTing to add expense should redirect back to expenses page."""
        client.cookies.set("budget_session", "demo")
        response = client.post(
            "/budget/expenses/add",
            data={"name": "x", "category": "y", "amount": "1", "frequency": "monthly"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/budget/expenses"

    def test_demo_add_account_redirects_to_accounts(self, client):
        """Demo user POSTing to add account should redirect back to accounts page."""
        client.cookies.set("budget_session", "demo")
        response = client.post(
            "/budget/accounts/add",
            data={"name": "Ny konto"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/budget/accounts"

    def test_demo_update_income_redirects_to_dashboard(self, client):
        """Demo user POSTing income update should redirect to dashboard."""
        client.cookies.set("budget_session", "demo")
        response = client.post("/budget/income", data={}, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/budget/"

    def test_authenticated_non_demo_can_add_expense(self, authenticated_client):
        """Authenticated non-demo user should be able to post to write routes."""
        response = authenticated_client.post(
            "/budget/expenses/add",
            data={"name": "Test", "category": "Bolig", "amount": "500", "frequency": "monthly"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/budget/expenses"


class TestDemoJsonEndpointsUnchanged:
    """JSON endpoints keep explicit 401/403 checks (not replaced by Depends)."""

    def test_add_account_json_unauthenticated_returns_401(self, client):
        """add_account_json: unauthenticated → 401 JSON, not redirect."""
        response = client.post(
            "/budget/accounts/add-json",
            data={"name": "Test"},
            follow_redirects=False,
        )
        assert response.status_code == 401
        assert response.json()["success"] is False

    def test_add_account_json_demo_returns_403(self, client):
        """add_account_json: demo mode → 403 JSON, not redirect."""
        client.cookies.set("budget_session", "demo")
        response = client.post(
            "/budget/accounts/add-json",
            data={"name": "Test"},
            follow_redirects=False,
        )
        assert response.status_code == 403
        assert response.json()["success"] is False
```

- [ ] **Step 4: Run tests to verify they pass against current code**

```bash
cd ~/projects/family-budget
python -m pytest tests/test_dependencies.py -v 2>&1 | distill "did all tests pass?"
```

Expected: all green (behavior already exists, tests lock it in).

- [ ] **Step 5: Commit baseline tests**

```bash
cd ~/projects/family-budget
git add tests/test_dependencies.py
git commit -m "test: add behavior tests for auth/demo guard dependencies (issue #127)"
```

---

### Task 2: Create `src/dependencies.py`

**Files:**
- Create: `src/dependencies.py`

- [ ] **Step 1: Create the dependencies module**

```python
# src/dependencies.py
"""FastAPI dependencies for authentication and write guards.

Usage:
    from ..dependencies import require_auth, require_write

    @router.get("/mypage")
    async def my_page(request: Request, _: None = Depends(require_auth)):
        ...

    @router.post("/mypage/add")
    async def add_item(request: Request, _: None = Depends(require_write("/mypage"))):
        ...
"""

from fastapi import Request

from .helpers import check_auth, is_demo_mode


class AuthRequired(Exception):
    """Raised by require_auth when the request has no valid session."""


class DemoBlocked(Exception):
    """Raised by require_write when a demo user attempts a write operation.

    Attributes:
        redirect_to: URL to redirect the demo user to.
    """

    def __init__(self, redirect_to: str = "/budget/") -> None:
        self.redirect_to = redirect_to


async def require_auth(request: Request) -> None:
    """Dependency: raise AuthRequired if the request is not authenticated.

    FastAPI will catch AuthRequired via the exception handler registered in
    api.py and return a 303 redirect to /budget/login.

    Example:
        @router.get("/dashboard")
        async def dashboard(request: Request, _: None = Depends(require_auth)):
            ...
    """
    if not check_auth(request):
        raise AuthRequired()


def require_write(redirect_to: str):
    """Dependency factory: require auth and block demo mode for write routes.

    Checks authentication first, then blocks demo users and redirects them
    to redirect_to.

    Args:
        redirect_to: URL to redirect demo users to (usually the resource list page).

    Returns:
        An async dependency callable suitable for use with Depends().

    Example:
        @router.post("/expenses/add")
        async def add_expense(request: Request, _: None = Depends(require_write("/budget/expenses"))):
            ...
    """
    async def _dep(request: Request) -> None:
        if not check_auth(request):
            raise AuthRequired()
        if is_demo_mode(request):
            raise DemoBlocked(redirect_to)

    return _dep
```

- [ ] **Step 2: Run dependency tests to verify module works**

```bash
cd ~/projects/family-budget
python -m pytest tests/test_dependencies.py -v 2>&1 | distill "did all tests pass?"
```

Expected: all green (module exists but handlers not yet registered — tests pass against old implementation).

---

### Task 3: Register exception handlers in `api.py`

**Files:**
- Modify: `src/api.py`

The handlers must be registered AFTER `app = FastAPI(...)` but BEFORE any routers are included. Add them just before the `from .routes.*` import block.

- [ ] **Step 1: Add imports and exception handlers to `src/api.py`**

After line 44 (`app.add_middleware(RateLimitMiddleware, ...)`), add:

```python
# Auth/demo exception handlers
from fastapi import Request as _Request  # noqa: E402
from fastapi.responses import RedirectResponse as _RedirectResponse  # noqa: E402
from .dependencies import AuthRequired, DemoBlocked  # noqa: E402


@app.exception_handler(AuthRequired)
async def _auth_required_handler(_request: _Request, _exc: AuthRequired) -> _RedirectResponse:
    return _RedirectResponse(url="/budget/login", status_code=303)


@app.exception_handler(DemoBlocked)
async def _demo_blocked_handler(_request: _Request, exc: DemoBlocked) -> _RedirectResponse:
    return _RedirectResponse(url=exc.redirect_to, status_code=303)
```

- [ ] **Step 2: Run full test suite**

```bash
cd ~/projects/family-budget
python -m pytest tests/ -x -q 2>&1 | distill "did all tests pass?"
```

Expected: all green.

- [ ] **Step 3: Commit**

```bash
cd ~/projects/family-budget
git add src/dependencies.py src/api.py
git commit -m "feat: add require_auth and require_write FastAPI dependencies (issue #127)"
```

---

## Chunk 2: Route Migration

### Task 4: Migrate `accounts.py`

**Files:**
- Modify: `src/routes/accounts.py`

The file has 5 routes: 4 HTML (replace guards with Depends) + 1 JSON (`add_account_json` — keep explicit checks).

- [ ] **Step 1: Update imports**

Replace the current import block:
```python
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from ..helpers import (
    check_auth,
    get_user_id,
    is_demo_advanced,
    is_demo_mode,
    templates,
)
```

With:
```python
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from ..dependencies import require_auth, require_write
from ..helpers import (
    check_auth,
    get_user_id,
    is_demo_advanced,
    is_demo_mode,
    templates,
)
```

*(Keep `check_auth` and `is_demo_mode` imports — still needed by `add_account_json`.)*

- [ ] **Step 2: Migrate `accounts_page` GET**

Replace:
```python
@router.get("/accounts", response_class=HTMLResponse)
async def accounts_page(request: Request):
    """Accounts management page."""
    if not check_auth(request):
        return RedirectResponse(url="/budget/login", status_code=303)
```

With:
```python
@router.get("/accounts", response_class=HTMLResponse)
async def accounts_page(request: Request, _: None = Depends(require_auth)):
    """Accounts management page."""
```

- [ ] **Step 3: Migrate `add_account` POST**

Replace:
```python
@router.post("/accounts/add")
async def add_account(
    request: Request,
    name: str = Form(...)
):
    """Add a new account."""
    if not check_auth(request):
        return RedirectResponse(url="/budget/login", status_code=303)
    if is_demo_mode(request):
        return RedirectResponse(url="/budget/accounts", status_code=303)
```

With:
```python
@router.post("/accounts/add")
async def add_account(
    request: Request,
    name: str = Form(...),
    _: None = Depends(require_write("/budget/accounts")),
):
    """Add a new account."""
```

- [ ] **Step 4: Migrate `edit_account` and `delete_account` POSTs**

Apply the same pattern — replace the two-line guard block with `_: None = Depends(require_write("/budget/accounts"))` in the signature.

`edit_account`:
```python
@router.post("/accounts/{account_id}/edit")
async def edit_account(
    request: Request,
    account_id: int,
    name: str = Form(...),
    _: None = Depends(require_write("/budget/accounts")),
):
    """Edit an account."""
```

`delete_account`:
```python
@router.post("/accounts/{account_id}/delete")
async def delete_account(request: Request, account_id: int, _: None = Depends(require_write("/budget/accounts"))):
    """Delete an account for the current user."""
```

- [ ] **Step 5: Leave `add_account_json` unchanged**

This route returns `JSONResponse` with 401/403 — the redirect-based exception handlers would not match. Leave its explicit `check_auth`/`is_demo_mode` checks in place.

- [ ] **Step 6: Run tests**

```bash
cd ~/projects/family-budget
python -m pytest tests/ -x -q 2>&1 | distill "did all tests pass?"
```

Expected: all green.

---

### Task 5: Migrate `categories.py`, `expenses.py`, `income.py`

**Files:**
- Modify: `src/routes/categories.py`
- Modify: `src/routes/expenses.py`
- Modify: `src/routes/income.py`

Apply the same pattern as Task 4 to each file.

#### `categories.py` — 4 routes

- [ ] **Step 1: Update imports in `categories.py`**

Add `Depends` to fastapi imports. Add:
```python
from ..dependencies import require_auth, require_write
```
Keep `check_auth`/`is_demo_mode` only if needed elsewhere in the file — after migration, they are not used as guards, but `is_demo_mode` is used in the route body to set `demo` variable. Adjust imports accordingly.

- [ ] **Step 2: Migrate all 4 routes**

| Route | Dependency |
|-------|-----------|
| `GET /categories` | `Depends(require_auth)` |
| `POST /categories/add` | `Depends(require_write("/budget/categories"))` |
| `POST /categories/{id}/edit` | `Depends(require_write("/budget/categories"))` |
| `POST /categories/{id}/delete` | `Depends(require_write("/budget/categories"))` |

For each: remove the two-line guard block, add `_: None = Depends(...)` to signature.

- [ ] **Step 3: Run tests**

```bash
cd ~/projects/family-budget
python -m pytest tests/ -x -q 2>&1 | distill "did all tests pass?"
```

#### `expenses.py` — 3 routes

- [ ] **Step 4: Update imports in `expenses.py`** (same pattern)

- [ ] **Step 5: Migrate all 3 routes**

| Route | Dependency |
|-------|-----------|
| `GET /expenses` | `Depends(require_auth)` |
| `POST /expenses/add` | `Depends(require_write("/budget/expenses"))` |
| `POST /expenses/{id}/delete` | `Depends(require_write("/budget/expenses"))` |
| `POST /expenses/{id}/edit` | `Depends(require_write("/budget/expenses"))` |

*(3 routes total in the issue scope — 1 GET + 2 POSTs)*

- [ ] **Step 6: Run tests**

```bash
cd ~/projects/family-budget
python -m pytest tests/ -x -q 2>&1 | distill "did all tests pass?"
```

#### `income.py` — 2 routes

- [ ] **Step 7: Update imports in `income.py`**

- [ ] **Step 8: Migrate 2 routes**

| Route | Dependency |
|-------|-----------|
| `GET /income` | `Depends(require_auth)` |
| `POST /income` | `Depends(require_write("/budget/"))` |

Note: Income mutation redirects to `/budget/` (the dashboard), not `/budget/income`.

- [ ] **Step 9: Run tests + commit**

```bash
cd ~/projects/family-budget
python -m pytest tests/ -x -q 2>&1 | distill "did all tests pass?"
git add src/routes/categories.py src/routes/expenses.py src/routes/income.py
git commit -m "refactor: migrate categories, expenses, income routes to Depends() guards (issue #127)"
```

---

### Task 6: Migrate remaining routes + final cleanup

**Files:**
- Modify: `src/routes/dashboard.py`
- Modify: `src/routes/yearly.py`
- Modify: `src/routes/api_endpoints.py`
- Modify: `src/routes/settings.py`
- Modify: `src/routes/pages.py`

#### `dashboard.py` — 1 route

- [ ] **Step 1: Migrate `dashboard_page` GET**

```python
@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, _: None = Depends(require_auth)):
```

Remove the two-line guard. Keep `demo = is_demo_mode(request)` in the body (soft check, not a guard).

#### `yearly.py` — 1 route

- [ ] **Step 2: Migrate `yearly_overview_page` GET**

```python
@router.get("/yearly", response_class=HTMLResponse)
async def yearly_overview_page(request: Request, _: None = Depends(require_auth)):
```

#### `api_endpoints.py` — 1 route

- [ ] **Step 3: Migrate `chart_data` GET**

```python
@router.get("/api/chart-data")
async def chart_data(request: Request, _: None = Depends(require_auth)):
```

#### `settings.py` — 2 routes (both use `require_write` — demo can't access settings at all)

- [ ] **Step 4: Migrate `settings_page` GET and `update_email` POST**

`settings_page` is a GET but blocks demo users — use `require_write`:
```python
@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, _: None = Depends(require_write("/budget/"))):
    """Account settings page."""
    user_id = get_user_id(request)
    ...
```

`update_email`:
```python
@router.post("/settings/email")
async def update_email(
    request: Request,
    email: str = Form(""),
    _: None = Depends(require_write("/budget/")),
):
```

#### `pages.py` — 2 routes (feedback: auth only, demo users CAN submit feedback)

- [ ] **Step 5: Migrate `feedback_page` GET and `submit_feedback` POST**

```python
@router.get("/feedback", response_class=HTMLResponse)
async def feedback_page(request: Request, _: None = Depends(require_auth)):
```

```python
@router.post("/feedback")
async def submit_feedback(
    request: Request,
    feedback_type: str = Form(...),
    description: str = Form(...),
    email: str = Form(""),
    website: str = Form(""),
    _: None = Depends(require_auth),
):
```

Note: `about_page` uses `check_auth(request)` only to determine nav display (`logged_in = check_auth(request)`) — this is NOT a guard and should NOT be changed.

#### Final verification

- [ ] **Step 6: Clean up unused imports**

After migrating all routes, each file may still import `check_auth`/`is_demo_mode` from helpers for soft checks in route bodies. Remove any that are now genuinely unused (i.e., no longer called at all in the file).

Run:
```bash
cd ~/projects/family-budget
python -m pytest tests/ -q 2>&1 | distill "did all tests pass?"
```

- [ ] **Step 7: Verify boilerplate is gone**

```bash
cd ~/projects/family-budget
grep -rn "if not check_auth" src/routes/ | grep -v "add_account_json"
grep -rn "if is_demo_mode" src/routes/ | grep -v "add_account_json"
```

Expected: zero results (both greps return nothing — all guards migrated except the JSON endpoint).

- [ ] **Step 8: Commit + push**

```bash
cd ~/projects/family-budget
git add src/routes/
git commit -m "refactor: migrate remaining route files to Depends() guards (issue #127)"
git push -u origin feat/auth-dependency-127
```

- [ ] **Step 9: Open PR**

```bash
cd ~/projects/family-budget
gh pr create \
  --title "refactor: extract auth/demo guard into FastAPI dependency (#127)" \
  --body "$(cat <<'EOF'
## Summary

Closes #127.

- Introduces `require_auth` and `require_write(redirect_to)` FastAPI dependencies in `src/dependencies.py`
- Registers `AuthRequired` and `DemoBlocked` exception handlers in `api.py`
- Replaces 22 `check_auth` guards and 13 `is_demo_mode` guards across 9 route files with `Depends()` in route signatures
- Eliminates ~70 lines of boilerplate; JSON endpoint `add_account_json` retains explicit 401/403 checks

## Test plan

- [ ] All existing tests pass
- [ ] `tests/test_dependencies.py` passes (behavior regression tests)
- [ ] `grep "if not check_auth" src/routes/` returns no results (except `add_account_json`)
- [ ] `grep "if is_demo_mode" src/routes/` returns no results (except `add_account_json`)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Notes for Implementer

1. **Order matters in `api.py`**: Exception handlers must be registered before routes are included. The current placement (after middleware, before `from .routes.*`) is correct.

2. **`require_write` returns a function, not a coroutine**: `Depends(require_write("/budget/accounts"))` is correct — FastAPI calls `require_write(...)` first to get the inner `_dep` callable, then `Depends()` wraps it. Do NOT write `Depends(require_write)`.

3. **`_: None = Depends(...)` placement**: When a route has both `Form(...)` parameters and a dependency, the `Depends` parameter can be placed anywhere in the signature. Convention: put it last for readability.

4. **Soft checks stay**: `demo = is_demo_mode(request)` inside route bodies (used to select demo vs real data) are NOT replaced. Only the two-line guard blocks at the top of each handler are eliminated.

5. **`pages.py` `about_page`**: Uses `logged_in = check_auth(request)` to conditionally show nav — this is a soft check, not a guard. Leave it unchanged.
