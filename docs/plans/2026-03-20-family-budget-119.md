# Refactor: Use feedback-api for GitHub Issue Creation

> **For agentic workers:** REQUIRED: Use superpowers-extended-cc:subagent-driven-development (if subagents available) or superpowers-extended-cc:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace direct GitHub API calls in the feedback flow with calls to the centralized `feedback-api` service.

**Architecture:** The `submit_feedback()` endpoint in `src/routes/pages.py` currently calls `api.github.com` directly using `GITHUB_TOKEN`. We replace that with an HTTP POST to `feedback-api` at `FEEDBACK_API_URL/api/feedback`. The feedback-api already handles GitHub issue creation, label mapping, and honeypot detection. Rate limiting and input validation stay in family-budget (feedback-api rate-limits by source IP, which would be the container IP — useless for per-user limiting).

**Tech Stack:** Python/FastAPI, httpx, feedback-api (Node.js/Hono on port 3102)

**References:**
- feedback-api endpoint: `POST /api/feedback` expects `{ repo, title, type, description?, _hp? }`
- feedback-api responses: `201` success, `400` validation, `429` rate limit, `502` GitHub error
- Current code: `src/routes/pages.py:66-206`
- Tests: `tests/test_feedback.py:20-129`
- Dev docker-compose: `docker-compose.yml`
- Prod docker-compose: `~/apps/family-budget/docker-compose.yml`

---

### Task 1: Update env vars in docker-compose.yml (dev)

**Files:**
- Modify: `docker-compose.yml:14-16`

- [ ] **Step 1: Remove GITHUB_TOKEN, update GITHUB_REPO, add FEEDBACK_API_URL**

Replace the GitHub env vars with FEEDBACK_API_URL. Keep GITHUB_REPO as it's needed for the feedback-api `repo` field.

```yaml
      # Feedback API (replaces direct GitHub API calls)
      - FEEDBACK_API_URL=${FEEDBACK_API_URL:-http://172.17.0.1:3102}
      - GITHUB_REPO=${GITHUB_REPO:-Wibholm-solutions/family-budget}
```

Note: `172.17.0.1` is the Docker host gateway — same pattern used for SMTP. The `FEEDBACK_API_URL` default allows dev environments to override.

- [ ] **Step 2: Commit**

```bash
git add docker-compose.yml
git commit -m "refactor: replace GITHUB_TOKEN with FEEDBACK_API_URL in docker-compose"
```

---

### Task 2: Rewrite submit_feedback() to call feedback-api

**Files:**
- Modify: `src/routes/pages.py:66-206`

- [ ] **Step 1: Write the failing test — successful feedback-api call**

In `tests/test_feedback.py`, update `test_feedback_github_api_failure` and add a new test for the feedback-api integration:

```python
def test_feedback_calls_feedback_api(self, authenticated_client, monkeypatch):
    """Feedback should POST to feedback-api instead of GitHub directly."""
    import src.routes.pages as pages_module

    monkeypatch.setattr(pages_module, "FEEDBACK_API_URL", "http://fake-feedback-api:3000")

    captured = {}

    async def mock_post(*args, **kwargs):
        # args[0] = self (AsyncClient), args[1] = url
        captured["url"] = str(args[1])
        captured["json"] = kwargs.get("json")

        class MockResponse:
            status_code = 201
            def json(self_inner):
                return {"message": "Feedback received", "issue_url": "https://github.com/test/issues/1"}
        return MockResponse()

    import httpx
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    response = authenticated_client.post(
        "/budget/feedback",
        data={
            "feedback_type": "feature",
            "description": "This is a valid feature request with enough text.",
        }
    )
    assert response.status_code == 200
    assert "Tak for din feedback" in response.text
    assert captured["url"] == "http://fake-feedback-api:3000/api/feedback"
    assert captured["json"]["repo"] == pages_module.GITHUB_REPO
    assert captured["json"]["type"] == "feature"
    assert captured["json"]["title"].startswith("Feature request:")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/projects/family-budget && venv/bin/pytest tests/test_feedback.py::TestFeedback::test_feedback_calls_feedback_api -v`
Expected: FAIL (test method doesn't exist yet / code still calls GitHub API)

- [ ] **Step 3: Rewrite the feedback code in src/routes/pages.py**

Replace lines 66-72 (module-level constants):

```python
# Feedback API configuration
FEEDBACK_API_URL = os.environ.get("FEEDBACK_API_URL", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "Wibholm-solutions/family-budget")
```

Replace lines 165-199 (the GitHub API call block) with:

```python
    # Send to feedback-api
    if FEEDBACK_API_URL:
        try:
            async with httpx.AsyncClient() as http_client:
                response = await http_client.post(
                    f"{FEEDBACK_API_URL}/api/feedback",
                    json={
                        "repo": GITHUB_REPO,
                        "title": f"{config['prefix']}: {description[:50]}...",
                        "description": "\n".join(body_parts),
                        "type": feedback_type,
                    },
                    timeout=10.0,
                )
                if response.status_code not in (200, 201):
                    logger.error(f"feedback-api error: {response.status_code} - {response.text}")
                    raise Exception("feedback-api error")
        except Exception as e:
            logger.error(f"Failed to send feedback: {e}")
            return templates.TemplateResponse(
                "feedback.html",
                {
                    "request": request,
                    "error": "Kunne ikke sende feedback. Prøv igen senere.",
                    "demo_mode": demo,
                    "demo_advanced": is_demo_advanced(request),
                }
            )
    else:
        # No feedback API configured - just log
        logger.info(f"Feedback ({feedback_type}): {description[:100]}...")
```

Key changes:
- `GITHUB_TOKEN` removed entirely — no longer needed
- `FEEDBACK_API_URL` replaces it as the "is feedback enabled" check
- Payload matches feedback-api's `FeedbackBody` interface: `{ repo, title, description, type }`
- Honeypot stays in family-budget (handled before this block) — not forwarded to feedback-api
- Rate limiting stays in family-budget (feedback-api would see container IP, not user IP)
- `record_feedback_attempt(client_ip)` at line 201 is PRESERVED — only replace lines 165-199, not beyond
- Note: `GITHUB_REPO` default changes from `saabendtsen/family-budget` to `Wibholm-solutions/family-budget` (fixes latent inconsistency — prod already used the org name)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/projects/family-budget && venv/bin/pytest tests/test_feedback.py::TestFeedback::test_feedback_calls_feedback_api -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/routes/pages.py tests/test_feedback.py
git commit -m "refactor: use feedback-api instead of direct GitHub API calls"
```

---

### Task 3: Update existing tests

**Files:**
- Modify: `tests/test_feedback.py:60-129`

- [ ] **Step 1: Update test_feedback_submit_success**

This test currently works because no `GITHUB_TOKEN` is set (falls through to log-only path). After refactor, no `FEEDBACK_API_URL` means same behavior. **No change needed** — verify it still passes.

Run: `cd ~/projects/family-budget && venv/bin/pytest tests/test_feedback.py::TestFeedback::test_feedback_submit_success -v`
Expected: PASS

- [ ] **Step 2: Update test_feedback_github_api_failure to test feedback-api failure**

Rename and update to test feedback-api connection failure:

```python
def test_feedback_api_failure(self, authenticated_client, monkeypatch):
    """feedback-api errors should show a user-friendly error message."""
    import httpx

    import src.routes.pages as pages_module

    monkeypatch.setattr(pages_module, "FEEDBACK_API_URL", "http://fake-feedback-api:3000")

    async def mock_post(*args, **kwargs):
        raise httpx.ConnectError("Connection failed")

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    response = authenticated_client.post(
        "/budget/feedback",
        data={
            "feedback_type": "feedback",
            "description": "This is a valid description with enough text.",
        }
    )
    assert response.status_code == 200
    assert "Kunne ikke sende feedback" in response.text
```

- [ ] **Step 3: Run all feedback tests**

Run: `cd ~/projects/family-budget && venv/bin/pytest tests/test_feedback.py::TestFeedback -v`
Expected: All 10 tests PASS (9 existing + 1 new)

- [ ] **Step 4: Commit**

```bash
git add tests/test_feedback.py
git commit -m "test: update feedback tests for feedback-api integration"
```

---

### Task 4: Update production docker-compose and .env

**Files:**
- Modify: `~/apps/family-budget/docker-compose.yml` (prod — NOT in git)
- Modify: `~/apps/family-budget/.env` (prod — NOT in git)
- Modify: `.env` (dev — gitignored)

- [ ] **Step 1: Update dev .env**

Remove `GITHUB_PAT` (was misnamed anyway — docker-compose used `GITHUB_TOKEN`). Add:

```
FEEDBACK_API_URL=http://172.17.0.1:3102
```

- [ ] **Step 2: Update prod docker-compose**

In `~/apps/family-budget/docker-compose.yml`, replace `GITHUB_TOKEN` and `GITHUB_REPO` env vars:

Remove from environment section:
```yaml
      - GITHUB_REPO=Wibholm-solutions/family-budget
```

Add to environment section:
```yaml
      - FEEDBACK_API_URL=http://172.17.0.1:3102
      - GITHUB_REPO=Wibholm-solutions/family-budget
```

The prod compose uses `env_file: .env`, so alternatively add `FEEDBACK_API_URL` to `~/apps/family-budget/.env`. Either approach works — environment section is more explicit.

- [ ] **Step 3: Update prod .env**

Remove `GITHUB_TOKEN` (and `GITHUB_PAT` if present — the dev `.env` used this mismatched name) from `~/apps/family-budget/.env`. Neither is needed by family-budget after this refactor. Consider revoking the PAT if no other service uses it.

- [ ] **Step 4: Verify feedback-api is running**

```bash
curl -s http://localhost:3102/api/feedback/health | head -1
```

Expected: health check response (200 OK)

- [ ] **Step 5: Commit dev changes**

```bash
# Only docker-compose.yml is tracked; .env is gitignored
git add docker-compose.yml
git commit -m "chore: remove GITHUB_TOKEN from dev docker-compose"
```

Note: Prod files at `~/apps/` are not in this git repo.

---

### Task 5: Full test suite and cleanup

**Files:**
- Verify: all test files

- [ ] **Step 1: Run full test suite**

```bash
cd ~/projects/family-budget && venv/bin/pytest -x -q
```

Expected: All tests pass

- [ ] **Step 2: Verify no remaining GITHUB_TOKEN references in tracked code**

```bash
cd ~/projects/family-budget && grep -r "GITHUB_TOKEN" src/ tests/ docker-compose.yml templates/
```

Expected: No matches (only in docs/plans or gitignored files)

- [ ] **Step 3: Squash commits or create PR**

```bash
git push -u origin <branch>
gh pr create --title "refactor: use feedback-api for GitHub issue creation" --body "Closes #119"
```
