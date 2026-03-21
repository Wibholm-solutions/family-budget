# Plan: Add dashboard.healthcheck.url label to Docker container

**Issue:** #159
**Goal:** Enable server-dashboard HTTP healthcheck monitoring for family-budget by adding the `dashboard.healthcheck.url` Docker label.

**Architecture:** Family-budget already exposes a health endpoint at `GET /budget/health` on port 8086 (with DB connectivity check, returning 200/503). The server-dashboard discovers containers via Docker socket and checks for a `dashboard.healthcheck.url` label to perform HTTP healthchecks. No new code needed — only a label addition to docker-compose files.

## Files to Modify

- **`docker-compose.yml`** (dev, in repo root)
- **`~/apps/family-budget/docker-compose.yml`** (prod, outside repo)

## Tasks

### Task 1: Add label to dev docker-compose.yml

Add `labels` section to the `family-budget` service:

```yaml
labels:
  - "dashboard.healthcheck.url=http://localhost:8086/budget/health"
```

### Task 2: Add label to prod docker-compose.yml

Same label addition to `~/apps/family-budget/docker-compose.yml`.

### Task 3: Verify

- `docker compose config` validates YAML syntax
- Redeploy: `docker compose up -d --build` (or `--force-recreate` in prod)
- Confirm label: `docker inspect family-budget --format '{{index .Config.Labels "dashboard.healthcheck.url"}}'`
- Check server-dashboard `/api/status` shows family-budget healthcheck

## Commit

```
feat: add dashboard.healthcheck.url label for server-dashboard monitoring

Closes #159
```
