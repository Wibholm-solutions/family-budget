# Plan: Add dashboard.healthcheck.url label to Docker container

**Issue:** #159
**Goal:** Enable server-dashboard HTTP healthcheck monitoring for family-budget by adding the `dashboard.healthcheck.url` Docker label.

**Architecture:** Family-budget already exposes a health endpoint at `GET /budget/health` on port 8086 (with DB connectivity check, returning 200/503). The server-dashboard discovers containers via Docker socket and checks for a `dashboard.healthcheck.url` label to perform HTTP healthchecks. No new code needed — only a label addition to docker-compose files.

## Files to Modify

- **`docker-compose.yml`** (dev, in repo root)
- **`~/apps/family-budget/docker-compose.yml`** (prod, outside repo)

## Tasks

### Task 1: Add label to dev docker-compose.yml

Add `labels` section to the `family-budget` service in `docker-compose.yml`:

```yaml
services:
  family-budget:
    build: .
    container_name: family-budget
    restart: unless-stopped
    ports:
      - "8086:8086"
    labels:
      - "dashboard.healthcheck.url=http://localhost:8086/budget/health"
    volumes:
      - ./data:/app/data
    environment:
      ...
```

**Verification:** `cd ~/projects/family-budget && docker compose config 2>&1 | grep healthcheck.url`

### Task 2: Add label to prod docker-compose.yml

Add `labels` section to `~/apps/family-budget/docker-compose.yml`:

```yaml
services:
  family-budget:
    image: family-budget:latest
    container_name: family-budget
    restart: unless-stopped
    ports:
      - "8086:8086"
    labels:
      - "dashboard.healthcheck.url=http://localhost:8086/budget/health"
    env_file: .env
    volumes:
      - ./data:/app/data
    environment:
      ...
    healthcheck:
      ...
```

**Verification:** `docker compose -f ~/apps/family-budget/docker-compose.yml config 2>&1 | grep healthcheck.url`

### Task 3: Redeploy and verify

1. Redeploy prod: `cd ~/apps/family-budget && docker compose up -d --force-recreate`
2. Confirm label: `docker inspect family-budget --format '{{index .Config.Labels "dashboard.healthcheck.url"}}'`
   - Expected: `http://localhost:8086/budget/health`
3. Check server-dashboard picks it up: `curl -s wibholmsolutions.com/server-dashboard/api/status | python3 -c "import sys,json; d=json.load(sys.stdin); print([c for c in d.get('containers',[]) if c.get('name')=='family-budget'])"`

## Commit

```
feat: add dashboard.healthcheck.url label for server-dashboard monitoring

Closes #159
```

## Complexity

Low — config-only change, no application code modified.
