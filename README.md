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
    git clone https://github.com/saabendtsen/family-budget.git
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

## Self-Hosting Guide

### Quick Start with Docker

```bash
git clone https://github.com/saabendtsen/family-budget.git
cd family-budget
docker compose up -d --build
```

The application runs on `http://localhost:8086/budget/` with the database persisted in `./data`.

### Production Setup with Auto-Deploy

For a production server with automatic deployments when you push to GitHub:

#### 1. Clone and Initial Setup

```bash
cd ~/projects
git clone https://github.com/YOUR_USERNAME/family-budget.git
cd family-budget
docker compose up -d --build
```

#### 2. Create Deploy Script

Create `scripts/deploy.sh`:
```bash
#!/bin/bash
set -e
cd ~/projects/family-budget

BRANCH="main"
if ! git show-ref --verify --quiet "refs/remotes/origin/$BRANCH"; then
    BRANCH="master"
fi

git fetch origin "$BRANCH" --quiet
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse "origin/$BRANCH")

if [ "$LOCAL" = "$REMOTE" ]; then
    exit 0
fi

echo "[$(date)] New commits detected, deploying..."
git reset --hard "origin/$BRANCH"
export APP_VERSION=$(cat VERSION)
docker compose build --quiet
docker compose down
docker compose up -d

sleep 3
if curl -sf http://localhost:8086/budget/login > /dev/null; then
    echo "[$(date)] Deploy successful: $(git log -1 --oneline)"
else
    echo "[$(date)] Health check failed!"
    exit 1
fi
```

Make it executable: `chmod +x scripts/deploy.sh`

#### 3. Create Systemd Timer (Auto-Deploy)

Create `~/.config/systemd/user/family-budget-deploy.service`:
```ini
[Unit]
Description=Family Budget Auto-Deploy
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/home/YOUR_USER/projects/family-budget
ExecStart=/home/YOUR_USER/projects/family-budget/scripts/deploy.sh
StandardOutput=journal
StandardError=journal
```

Create `~/.config/systemd/user/family-budget-deploy.timer`:
```ini
[Unit]
Description=Family Budget Auto-Deploy Timer

[Timer]
OnBootSec=1min
OnUnitActiveSec=1min

[Install]
WantedBy=timers.target
```

Enable and start:
```bash
systemctl --user daemon-reload
systemctl --user enable --now family-budget-deploy.timer
loginctl enable-linger $USER  # Keep timer running without login
```

#### 4. Reverse Proxy (Optional)

For HTTPS, use a reverse proxy like Caddy or nginx. Example Caddy config:
```
budget.yourdomain.com {
    reverse_proxy localhost:8086
}
```

### Manual Setup (Without Docker)

```bash
sudo apt update
sudo apt install python3-pip python3-venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m src.api
```

For production, use uvicorn with a process manager:
```bash
pip install uvicorn
uvicorn src.api:app --host 0.0.0.0 --port 8086
```

### Environment variables (deployment)

| Variable | Default | Purpose |
| --- | --- | --- |
| `ENVIRONMENT` | `production` | `development`/`dev`/`local` enables the interactive API docs (`/docs`, `/redoc`, `/openapi.json`). Anything else keeps them disabled. |
| `TRUSTED_PROXY_IPS` | `127.0.0.1,::1` | Comma separated IPs/CIDRs whose `X-Forwarded-For` may be trusted. Rate limiting keys on the forwarded client address only for requests arriving from these proxies; headers from anywhere else are ignored. Set it to the reverse proxy's address (behind Docker, the bridge gateway, e.g. `172.17.0.1`). |

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
