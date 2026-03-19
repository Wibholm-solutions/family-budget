# Add DB-Aware Health Endpoint — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers-extended-cc:subagent-driven-development (if subagents available) or superpowers-extended-cc:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance the existing `/budget/health` endpoint to include database connectivity checks, returning structured status with appropriate HTTP codes.

**Architecture:** The existing bare `{"status": "ok"}` endpoint in `src/routes/api_endpoints.py` is enhanced to run `SELECT 1` via `database.get_connection()`. Returns 200 with `{"status": "ok", "database": "ok"}` when healthy, or 503 with `{"status": "degraded", "database": "error", "detail": "..."}` when DB is unreachable. No authentication required.

**Tech Stack:** FastAPI, SQLite, pytest + TestClient

---

## File Structure

- **Modify:** `src/routes/api_endpoints.py` — enhance `health()` endpoint
- **Create:** `tests/test_health.py` — dedicated health endpoint tests

---

### Task 1: Write failing tests for DB-aware health endpoint

**Files:**
- Create: `tests/test_health.py`

- [ ] **Step 1: Create test file with two test cases**

```python
"""Tests for /budget/health endpoint."""

from unittest.mock import patch


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_returns_ok_with_db_status(self, client):
        """Health endpoint should return 200 with database status."""
        response = client.get("/budget/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["database"] == "ok"

    def test_health_returns_503_when_db_unavailable(self, client):
        """Health endpoint should return 503 when database is unreachable."""
        with patch("src.routes.api_endpoints.db.get_connection") as mock_conn:
            mock_conn.side_effect = Exception("DB unavailable")
            response = client.get("/budget/health")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert data["database"] == "error"
        assert "detail" in data
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/projects/family-budget && venv/bin/pytest tests/test_health.py -v`
Expected: FAIL — current endpoint returns `{"status": "ok"}` without `database` key, and doesn't return 503 on DB failure.

---

### Task 2: Enhance /budget/health with DB connectivity check

**Files:**
- Modify: `src/routes/api_endpoints.py:16-18`

- [ ] **Step 1: Update the health endpoint**

Replace the existing `health()` function (lines 16-18) with:

```python
from fastapi.responses import JSONResponse

@router.get("/health")
async def health():
    """Lightweight health check with DB connectivity verification."""
    try:
        with db.get_connection() as conn:
            conn.execute("SELECT 1")
        return {"status": "ok", "database": "ok"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "database": "error", "detail": str(e)},
        )
```

Note: `JSONResponse` import must be added to the imports at line 3. The `db` module is already imported at line 5.

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd ~/projects/family-budget && venv/bin/pytest tests/test_health.py -v`
Expected: PASS (2 tests)

- [ ] **Step 3: Run full test suite to check for regressions**

Run: `cd ~/projects/family-budget && venv/bin/pytest tests/ -v 2>&1 | /home/saabendtsen/.npm-global/bin/distill "did all tests pass?"`
Expected: All tests pass. The E2E conftest polls `/budget/health` for readiness — it only checks for a successful HTTP response, so the new JSON shape won't break it.

---

### Task 3: Commit and create PR

- [ ] **Step 1: Commit changes**

```bash
cd ~/projects/family-budget
git checkout -b feat/health-endpoint-122
git add tests/test_health.py src/routes/api_endpoints.py
git commit -m "feat: add DB connectivity check to /budget/health endpoint

Closes #122"
```

- [ ] **Step 2: Push and create PR**

```bash
git push -u origin feat/health-endpoint-122
gh pr create --base master --title "feat: add DB connectivity check to health endpoint" \
  --body "Closes #122. Enhances /budget/health to verify DB connectivity."
```
