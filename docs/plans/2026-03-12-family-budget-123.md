# Document Required .env Secrets for Deploy-Center — family-budget#123

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:executing-plans to implement this plan task-by-task.

**Goal:** Document all required `.env` secrets for the family-budget deploy-center configuration by creating a `.env.example` file and extending `deploy.yml` with the missing SMTP vars.

**Architecture:** The deploy.yml for family-budget lives in the `feat/family-budget-deploy` branch of the `deploy-center` repo. `compose_gen.py` maps `env_file: .env` to `env_file: [.env]` relative to the generated `docker-compose.yml` at `~/deploy-center/apps/family-budget/`. Changes go on that branch, then a PR is opened. The plan file itself lives in the family-budget repo (this repo) since that is where the issue is tracked.

**Tech Stack:** Git, YAML, deploy-center compose_gen.py, Bash

---

### Task 1: Switch to the deploy-center feature branch

**Files:**
- Working in: `~/deploy-center/` (git repo, branch `feat/family-budget-deploy`)

**Step 1: Check out the branch**

```bash
cd ~/deploy-center
git checkout feat/family-budget-deploy
git pull origin feat/family-budget-deploy
```

Expected: Branch checked out, up to date.

**Step 2: Verify the family-budget app directory exists**

```bash
ls ~/deploy-center/apps/family-budget/
```

Expected: `deploy.yml` listed.

**Step 3: Ensure data dir exists (needed for volumes)**

```bash
mkdir -p ~/deploy-center/apps/family-budget/data
```

---

### Task 2: Create `.env.example` in deploy-center family-budget app dir

**Files:**
- Create: `~/deploy-center/apps/family-budget/.env.example`

**Step 1: Create the file with this exact content**

```
# ============================================================
# family-budget — required .env secrets
# Copy to .env and fill in real values before first deploy.
# Path: ~/deploy-center/apps/family-budget/.env
# ============================================================

# --- App version (injected by CI via APP_VERSION env var) ---
# Set to any string, e.g. the git SHA or tag.
APP_VERSION=dev

# --- GitHub API token ---
# Used to fetch release notes on the changelog page.
# Requires read:public_repo scope (or repo for private repos).
# Generate at: https://github.com/settings/tokens
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxx

# --- Stripe donation links ---
# Get these from your Stripe Dashboard → Payment Links.
# Used in templates/partials/donate_modal.html via helpers.py.
STRIPE_DONATE_10=https://buy.stripe.com/...
STRIPE_DONATE_25=https://buy.stripe.com/...
STRIPE_DONATE_50=https://buy.stripe.com/...

# --- SMTP authenticated relay (optional) ---
# Only needed if your SMTP relay requires authentication.
# When omitted, the app uses unauthenticated relay (default: host:25).
# Used in: src/routes/password_reset.py
# SMTP_USER=mailuser@example.com
# SMTP_PASS=supersecretpassword
```

**Step 2: Verify the file looks correct**

```bash
cat ~/deploy-center/apps/family-budget/.env.example
```

Expected: All 7 vars documented with explanations. SMTP_USER/SMTP_PASS commented out (they're optional).

---

### Task 3: Add SMTP_USER and SMTP_PASS to deploy.yml env section

**Files:**
- Modify: `~/deploy-center/apps/family-budget/deploy.yml`

Current `deploy.yml` has no `SMTP_USER`/`SMTP_PASS` entries. Without these, the container never receives the vars even if they are set in `.env`, meaning authenticated SMTP will silently fail.

**Step 1: Open the file and add two lines after `SMTP_FROM`**

Add:
```yaml
  - SMTP_USER=${SMTP_USER:-}
  - SMTP_PASS=${SMTP_PASS:-}
```

The `:-` syntax means: use the env var if set, otherwise default to empty string. This matches what `password_reset.py` expects (`os.getenv("SMTP_USER")` returns `None`/falsy when empty).

Full updated `env:` block for reference:
```yaml
env:
  - TZ=Europe/Copenhagen
  - PYTHONUNBUFFERED=1
  - APP_VERSION=${APP_VERSION}
  - GITHUB_TOKEN=${GITHUB_TOKEN}
  - GITHUB_REPO=Wibholm-solutions/family-budget
  - SMTP_HOST=172.17.0.1
  - SMTP_PORT=25
  - SMTP_FROM=noreply@wibholmsolutions.com
  - SMTP_USER=${SMTP_USER:-}
  - SMTP_PASS=${SMTP_PASS:-}
  - STRIPE_DONATE_10=${STRIPE_DONATE_10}
  - STRIPE_DONATE_25=${STRIPE_DONATE_25}
  - STRIPE_DONATE_50=${STRIPE_DONATE_50}
```

**Step 2: Verify deploy-center unit tests still pass**

```bash
cd ~/deploy-center && python -m pytest tests/test_compose_gen.py tests/test_config.py -v 2>&1 | tail -20
```

Expected: All tests pass.

---

### Task 4: Commit changes to deploy-center feature branch

**Step 1: Stage only the two changed files**

```bash
cd ~/deploy-center
git add apps/family-budget/.env.example apps/family-budget/deploy.yml
git status
```

Expected: Only those two files staged.

**Step 2: Commit**

```bash
git commit -m "$(cat <<'EOF'
docs(family-budget): add .env.example and document required secrets

- Add .env.example with all 7 required/optional secrets documented
- Add SMTP_USER and SMTP_PASS to deploy.yml env list (optional, default empty)

Ref: saabendtsen/family-budget#123

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
git push origin feat/family-budget-deploy
```

---

### Task 5: Commit the plan file to family-budget repo and open PR

**Files:**
- Add: `docs/plans/2026-03-12-family-budget-123.md` (this file)

```bash
cd ~/projects/family-budget
git checkout -b docs/issue-123-env-secrets
git add docs/plans/2026-03-12-family-budget-123.md
git commit -m "$(cat <<'EOF'
docs: add implementation plan for .env secrets documentation (issue #123)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
git push -u origin docs/issue-123-env-secrets
gh pr create \
  --title "docs: document required .env secrets for deploy-center (#123)" \
  --body "$(cat <<'EOF'
## Summary
- Adds implementation plan for issue #123
- Actual changes live in deploy-center repo on `feat/family-budget-deploy` branch

Closes #123
EOF
)"
```

---

## Out-of-scope observations

- `GITHUB_PAT` in the local dev `.env` doesn't match `GITHUB_TOKEN` expected by `docker-compose.yml` — the key name differs between dev and prod environments.
- `BUDGET_DB_PATH` is also configurable via env but intentionally not in deploy.yml (volume mount handles data persistence).
