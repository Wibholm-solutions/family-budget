"""FastAPI application for Family Budget."""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import __version__
from . import database as db
from .helpers import (  # noqa: F401 -- backward compat for tests
    DEMO_SESSION_ID,
    DONATION_LINKS,
    SESSIONS,
    check_auth,
    format_currency,
    format_currency_short,
    get_user_id,
    hash_token,
    is_demo_advanced,
    is_demo_mode,
    parse_danish_amount,
    save_sessions,
    templates,
)
from .middleware import RateLimitMiddleware, SecurityHeadersMiddleware

# Initialize database at startup
db.init_db()

# Configure logging
logger = logging.getLogger(__name__)

# Create app
app = FastAPI(
    title="Family Budget",
    description="A simple family budget tracker",
    version=__version__
)
app.state.version = __version__

# Add security and rate limiting middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, max_attempts=5, window_seconds=300)

# Serve static files
STATIC_DIR = Path(__file__).parent.parent / "static"
app.mount("/budget/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Include route modules
from .routes.accounts import router as accounts_router  # noqa: E402
from .routes.api_endpoints import router as api_router  # noqa: E402
from .routes.auth import router as auth_router  # noqa: E402
from .routes.categories import router as categories_router  # noqa: E402
from .routes.dashboard import router as dashboard_router  # noqa: E402
from .routes.expenses import router as expenses_router  # noqa: E402
from .routes.income import router as income_router  # noqa: E402
from .routes.pages import router as pages_router  # noqa: E402
from .routes.password_reset import router as password_reset_router  # noqa: E402
from .routes.settings import router as settings_router  # noqa: E402
from .routes.yearly import router as yearly_router  # noqa: E402

app.include_router(auth_router)
app.include_router(password_reset_router)
app.include_router(dashboard_router)
app.include_router(income_router)
app.include_router(expenses_router)
app.include_router(categories_router)
app.include_router(accounts_router)
app.include_router(pages_router)
app.include_router(api_router)
app.include_router(settings_router)
app.include_router(yearly_router)


# =============================================================================
# Run with: python -m src.api
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8086)
