# Family Budget

A web application for household budget management, built with FastAPI and SQLite. The application provides a clear overview of income and expenses, facilitating monthly financial planning.

## Features

- **Dashboard**: Central overview of total income, fixed expenses, and disposable income.
- **Expense Management**: Register both monthly and annual expenses. Annual expenses are automatically converted to monthly amounts.
- **Categorization**: Organize expenses into customizable categories with icons (e.g., Housing, Food, Transport, Savings).
- **User Management**: Secure login and registration with password hashing (PBKDF2).
- **Security**: Rate limiting on login attempts and session management via cookies.
- **Demo Mode**: Try the application with sample data without creating an account.

## Technical Stack

- **Backend**: [FastAPI](https://fastapi.tiangolo.com/) (Python)
- **Frontend**: [Jinja2 Templates](https://jinja.palletsprojects.com/), [Tailwind CSS](https://tailwindcss.com/), [Lucide Icons](https://lucide.dev/)
- **Database**: [SQLite](https://sqlite.org/) (file-based for portability)
- **Testing**: [Pytest](https://docs.pytest.org/), [Playwright](https://playwright.dev/) (E2E)

## Getting Started

### Prerequisites

- Python 3.10+
- pip

### Installation

1. **Clone the repository**:
    ```bash
    git clone https://github.com/Wibholm-solutions/family-budget.git
    cd family-budget
    ```

2. **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3. **Run the application**:
    ```bash
    python -m src.api
    ```
    The application will be available at `http://localhost:8086/budget/`

## Running it locally

### With Docker

```bash
git clone https://github.com/Wibholm-solutions/family-budget.git
cd family-budget
docker compose up -d --build
```

The application runs on `http://localhost:8086/budget/` with the database persisted in `./data`.

`docker-compose.yml` in this repository is **for local development only**. It builds from the
working tree (`build: .`), publishes port 8086 on the machine you run it on, and keeps its
database in `./data` next to the checkout. It is deliberately *not* the file the deployed
instance runs; see [Deployment](#deployment) below for that one. Nothing in this repository
deploys anything by itself.

### Without Docker

```bash
sudo apt update
sudo apt install python3-pip python3-venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m src.api
```

This is a development convenience. The deployed instance runs the published container image,
never a checkout — see [Deployment](#deployment).

## Deployment

The deployed instance is **not** built, pulled or updated on the server. It runs an immutable
image identified by digest, and the digest is changed by a reviewed commit in a separate
infrastructure repository.

### The lane, end to end

1. **Test and publish.** `.github/workflows/ci.yml` runs the unit, integration and Playwright
   suites on the trusted development-PC CI lane. On a push to `master` it builds the image and
   pushes it to `ghcr.io/wibholm-solutions/family-budget` with an SBOM and SLSA provenance bound
   to the source repository and commit. The **digest** (`sha256:…`) is the identity; the
   `sha-<commit>` tag is provenance only. No `latest` or semantic alias is published, precisely
   so that no tag can authorise a deployment.
2. **Pin.** `saabendtsen/home-server` holds the desired runtime state at
   `applications/family-budget/`. `desired-state.json` pins the exact digest that should be
   running, together with the source commit and the workflow run that produced it.
   `compose.yaml` there is the real server wiring: no `build:`, the image comes from
   `FAMILY_BUDGET_IMAGE` which the deployment lane resolves from `desired-state.json`.
3. **Converge.** The development-PC deployment lane applies that state to the server over SSH.
   The application runs from `/srv/homelab-deploy/family-budget/`, with persistent data on a
   bind mount at `/srv/homelab-deploy/family-budget/data` and runtime configuration from
   `/srv/homelab-deploy/family-budget/family-budget.env` — both outside the image, so replacing
   the image never touches them.
4. **Verify or roll back.** `applications/family-budget/verification.json` states what "up"
   means: the container reaching `healthy`, `GET /budget/health` answering `200`, and no fatal
   log patterns. A promotion that fails verification restores the previous known-good digest;
   a verified one is recorded in `history.jsonl` and becomes the new `known-good.json`.

A rollback is therefore a different digest and nothing else.

### Route and TLS

The live route is `https://wibholmsolutions.com/budget`. There is no dedicated hostname for
this application. TLS terminates at the **shared Caddy instance** on the server, which matches
a `handle /budget*` path block on `wibholmsolutions.com` and reverse-proxies it to the
container's port 8086. The Caddy configuration lives with the server's infrastructure, not in
this repository, and the application must keep serving under the `/budget` path prefix.

Because requests arrive through that proxy, `TRUSTED_PROXY_IPS` must name the address the
proxy's requests actually originate from — see the table below.

### The database holds live personal data

`/srv/homelab-deploy/family-budget/data/budget.db` is the deployed SQLite database. It contains
real accounts and real household budgets belonging to members of the public.

- **No command in this README, and no command in this repository, may be run against it.** In
  particular nothing that resets, recreates, migrates or seeds a database, and nothing that
  removes or replaces the `data/` bind mount.
- The `./data` directory used by `docker compose up` is a *local* directory next to your
  checkout. It is not the deployed one, and the two must never be swapped.
- A release that changes the schema in a way the previous image cannot read is not safe for
  unattended promotion: it must be declared in `verification.json` under `rollback_safety`, so
  it fails closed for human review instead of deploying automatically.

### Environment variables (deployment)

| Variable | Default | Purpose |
| --- | --- | --- |
| `ENVIRONMENT` | `production` | `development`/`dev`/`local` enables the interactive API docs (`/docs`, `/redoc`, `/openapi.json`). Anything else keeps them disabled. |
| `TRUSTED_PROXY_IPS` | `127.0.0.1,::1` | Comma separated IPs/CIDRs whose `X-Forwarded-For` may be trusted. Rate limiting keys on the forwarded client address only for requests arriving from these proxies; headers from anywhere else are ignored. Set it to the address the proxy's requests actually arrive from. Behind Docker this is a gateway address, but not necessarily the default bridge: if the proxy is host-networked and reaches a published port, requests re-originate from the Compose project network's gateway. Confirm it rather than assuming - `docker network inspect <project>_default` - and cross-check against the peer address in the container's request log. A wrong value fails closed: the header is ignored and every client shares one rate-limit bucket. |

## Project Structure

- `src/`: Backend logic and database operations.
    - `api.py`: FastAPI routes and middleware.
    - `database.py`: Database schema and SQL operations.
- `templates/`: Jinja2 HTML templates.
- `tests/`: Unit and integration tests.
- `e2e/`: End-to-end tests with Playwright.
- `data/`: (Auto-generated) Contains the SQLite database and session files.

## Testing

To run the test suite:

```bash
# Run all tests
pytest

# Run E2E tests (requires Playwright installation)
playwright install
pytest e2e/
```

## License

This project is developed for private use, but the code is freely available for reference.

## Sikkerhed / Security

Rapporter sårbarheder privat — opret ikke et offentligt issue. Se
[SECURITY.md](SECURITY.md) for fremgangsmåden.

*Report vulnerabilities privately; see [SECURITY.md](SECURITY.md).*
