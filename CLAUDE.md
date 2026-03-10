# Claude Code Project Mandates

This file defines the operational rules for Claude Code within the Family Budget project.

## 1. Project Context
- **SSOT:** Read `docs/AI_CONTEXT.md` for core project facts (Stack, DB, Architecture).
- **Standards:** Refer to `docs/PATTERNS.md` for coding standards and `docs/DESIGN_GUIDE.md` for UI patterns.

## 2. CI/CD & Deployment (Operational Facts)
- **CI Pipeline:** Tests run on all PRs/pushes to master (`.github/workflows/ci.yml`).
- **Release:** Automatic via `release-please` and `automerge-release`.
- **Manual Deploy:** `cd ~/projects/family-budget && docker compose up -d --build`.
- **Auto-Deploy:** Currently **disabled** to avoid overwriting feature branches on server.
- **Dockerfile:** When adding a new top-level directory (e.g. `static/`, `assets/`), always add a corresponding `COPY <dir>/ ./<dir>/` line to the Dockerfile.

## 3. Development Workflow
- **No Direct Commits to Master:** Use branch → PR → merge workflow.
- **Feature Branches:** 
  - `feature/last-login`: Tracking user last login.
  - `feature/email-password-reset`: Email-based reset flow.
- **Migrations:** Run migrations manually after merging PRs with DB changes.

## 4. Search Patterns (Quick Reference)
- Find routes: `grep -n "@app\." src/api.py`
- Find DB functions: `grep -n "def " src/database.py`
- Find templates: `ls templates/`
- Find tests: `grep -n "class Test" tests/*.py e2e/*.py`

## 5. Security Protocols
- PBKDF2 hashing (600k iterations) is mandatory.
- SHA-256 for session token hashing.
- SMTP config MUST be in `~/.env`.

## 6. Demo Data Maintenance
- **Advanced Demo:** When adding new user-facing features, update the advanced demo data in `src/database.py` to showcase the feature.
- Always offer to update the advanced demo when implementing features that add new UI elements or data types.
