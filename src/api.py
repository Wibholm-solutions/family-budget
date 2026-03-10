"""FastAPI application for Family Budget."""

import hashlib
import json
import logging
import os
import secrets
import smtplib
import sqlite3
import time
from collections import defaultdict
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from . import __version__
from . import database as db

# Initialize database at startup
db.init_db()

# Configure logging
logger = logging.getLogger(__name__)


# =============================================================================
# Rate limiting
# =============================================================================

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple rate limiting for login attempts."""

    def __init__(self, app, max_attempts: int = 5, window_seconds: int = 300):
        super().__init__(app)
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.attempts: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        # Only rate limit login POST requests
        if request.url.path == "/budget/login" and request.method == "POST":
            client_ip = request.client.host if request.client else "unknown"
            now = time.time()

            # Clean old attempts for this IP
            self.attempts[client_ip] = [
                t for t in self.attempts[client_ip]
                if now - t < self.window_seconds
            ]

            # Remove IP key entirely if no recent attempts (prevents memory leak)
            if not self.attempts[client_ip]:
                del self.attempts[client_ip]
            else:
                # Check if rate limited
                if len(self.attempts[client_ip]) >= self.max_attempts:
                    return HTMLResponse(
                        content="For mange login forsøg. Prøv igen om 5 minutter.",
                        status_code=429
                    )

            # Record this attempt
            self.attempts[client_ip].append(now)

        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security headers to every response."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://unpkg.com https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self';"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


# Load environment
load_dotenv(Path(__file__).parent.parent / ".env")

# Stripe donation payment links (override with env vars for production)
DONATION_LINKS = {
    10: os.getenv("STRIPE_DONATE_10", "https://buy.stripe.com/test_28E14hdiw6eb5Z70Jl9IQ00"),
    25: os.getenv("STRIPE_DONATE_25", "https://buy.stripe.com/test_aFa4gt3HW0TR0ENdw79IQ01"),
    50: os.getenv("STRIPE_DONATE_50", "https://buy.stripe.com/test_5kQ6oB5Q40TRevDfEf9IQ02"),
}


# Session management (file-based for persistence)
# Sessions map hashed tokens to user_ids
SESSIONS_FILE = Path(__file__).parent.parent / "data" / "sessions.json"


def hash_token(token: str) -> str:
    """Hash a session token for secure storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def load_sessions() -> dict:
    """Load sessions from file.

    Returns dict mapping hashed tokens to user_ids.
    Note: Basic implementation without locking for simplicity/portability,
    relying on atomic file operations if needed.
    """
    if SESSIONS_FILE.exists():
        try:
            with open(SESSIONS_FILE) as f:
                try:
                    data = json.load(f)
                    # Migrate from old format (list) to new format (dict)
                    if isinstance(data, list):
                        return {}  # Clear old sessions, users need to re-login
                    return data
                except (json.JSONDecodeError, OSError) as e:
                    logging.warning(f"Could not load sessions file: {e}")
        except Exception as e:
            logging.warning(f"Unexpected error loading sessions: {e}")
    return {}


def save_sessions(sessions: dict):
    """Save sessions to file.

    Writes to a temporary file and renames to prevent corruption.
    """
    SESSIONS_FILE.parent.mkdir(exist_ok=True)
    temp_file = SESSIONS_FILE.with_suffix(".tmp")
    with open(temp_file, 'w') as f:
        json.dump(sessions, f)
    # Atomic rename (on Unix, mostly on Windows too if file not open)
    try:
        if SESSIONS_FILE.exists():
            os.replace(temp_file, SESSIONS_FILE)
        else:
            temp_file.rename(SESSIONS_FILE)
    except OSError as e:
        logging.error(f"Failed to save sessions: {e}")


SESSIONS = load_sessions()  # Maps hashed tokens to user_ids

# Templates
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

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


@app.get("/budget/health")
async def health():
    return {"status": "ok"}


# =============================================================================
# Template helpers
# =============================================================================

def parse_danish_amount(amount_str: str) -> float:
    """Parse Danish currency format to float.

    Accepts:
    - "1234,50" -> 1234.50
    - "1.234,50" -> 1234.50
    - "1234.5" -> 1234.50
    - "1234" -> 1234.00

    Returns float with 2 decimal precision.
    Raises ValueError for invalid input.
    """
    if not amount_str or not isinstance(amount_str, str):
        raise ValueError("Invalid amount")

    # Remove whitespace
    amount_str = amount_str.strip()

    # Remove thousands separator (period)
    amount_str = amount_str.replace('.', '')

    # Replace comma with period for float parsing
    amount_str = amount_str.replace(',', '.')

    try:
        amount = float(amount_str)
        # Round to 2 decimals to prevent floating point errors
        return round(amount, 2)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid amount format: {amount_str}")


def format_currency(amount: float) -> str:
    """Format amount as Danish currency with 2 decimal places."""
    # Format: 1234.50 -> "1.234,50 kr"
    formatted = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return formatted + " kr"


# Add to Jinja2 globals
templates.env.globals["format_currency"] = format_currency


def format_currency_short(amount: float) -> str:
    """Format amount as short Danish currency (no 'kr' suffix, no decimals for whole numbers)."""
    if amount == 0:
        return "0"
    if amount == int(amount):
        formatted = f"{int(amount):,}".replace(",", ".")
    else:
        formatted = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return formatted


templates.env.globals["format_currency_short"] = format_currency_short
templates.env.globals["app_version"] = app.state.version


# =============================================================================
# Authentication
# =============================================================================

DEMO_SESSION_ID = "demo"  # Special marker for demo mode


def check_auth(request: Request) -> bool:
    """Check if request is authenticated (including demo mode)."""
    session_id = request.cookies.get("budget_session")
    if not session_id:
        return False
    # Demo mode
    if session_id == DEMO_SESSION_ID:
        return True
    # Compare hashed token
    return hash_token(session_id) in SESSIONS


def get_user_id(request: Request) -> int | None:
    """Get user_id from session. Returns None for demo mode or invalid sessions."""
    session_id = request.cookies.get("budget_session")
    if not session_id or session_id == DEMO_SESSION_ID:
        return None
    hashed = hash_token(session_id)
    return SESSIONS.get(hashed)


def is_demo_mode(request: Request) -> bool:
    """Check if request is in demo mode (read-only)."""
    return request.cookies.get("budget_session") == DEMO_SESSION_ID


def is_demo_advanced(request: Request) -> bool:
    """Check if demo mode is set to advanced view."""
    return is_demo_mode(request) and request.cookies.get("demo_level") == "advanced"


@app.get("/budget/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Show login page."""
    if get_user_id(request) is not None:
        return RedirectResponse(url="/budget/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/budget/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    """Login with username and password."""
    user = db.authenticate_user(username, password)
    if user:
        db.update_last_login(user.id)
        session_id = secrets.token_urlsafe(32)
        # Store hashed token mapped to user_id
        SESSIONS[hash_token(session_id)] = user.id
        save_sessions(SESSIONS)

        response = RedirectResponse(url="/budget/", status_code=303)
        response.set_cookie(
            key="budget_session",
            value=session_id,
            httponly=True,
            secure=True,       # Only send over HTTPS
            samesite="lax",    # CSRF protection
            max_age=86400 * 30  # 30 days
        )
        return response
    else:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Forkert brugernavn eller adgangskode"}
        )


@app.get("/budget/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Show registration page."""
    if get_user_id(request) is not None:
        return RedirectResponse(url="/budget/", status_code=303)
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/budget/register")
async def register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...)
):
    """Register a new user."""
    # Validate input
    if len(username) < 3:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Brugernavn skal være mindst 3 tegn"}
        )

    if len(password) < 6:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Adgangskode skal være mindst 6 tegn"}
        )

    if password != password_confirm:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Adgangskoderne matcher ikke"}
        )

    # Create user
    new_user_id = db.create_user(username, password)
    if new_user_id is None:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Brugernavnet er allerede taget"}
        )

    # Auto-login after registration
    session_id = secrets.token_urlsafe(32)
    SESSIONS[hash_token(session_id)] = new_user_id
    save_sessions(SESSIONS)

    response = RedirectResponse(url="/budget/", status_code=303)
    response.set_cookie(
        key="budget_session",
        value=session_id,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=86400 * 30
    )
    return response


# =============================================================================
# Password Reset
# =============================================================================

def send_password_reset_email(to_email: str, reset_url: str) -> bool:
    """Send password reset email via SMTP.

    Returns True if email was sent successfully, False otherwise.
    """
    smtp_host = os.getenv("SMTP_HOST", "localhost")
    smtp_port = int(os.getenv("SMTP_PORT", "25"))
    smtp_from = os.getenv("SMTP_FROM", "noreply@wibholmsolutions.com")
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Nulstil din adgangskode - Budget"
    msg["From"] = smtp_from
    msg["To"] = to_email

    # Plain text version
    text = f"""Hej,

Du har anmodet om at nulstille din adgangskode til Budget.

Klik på linket nedenfor for at vælge en ny adgangskode:
{reset_url}

Linket udløber om 1 time.

Hvis du ikke har anmodet om dette, kan du ignorere denne email.

Med venlig hilsen,
Budget
"""

    # HTML version
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #3b82f6;">Nulstil din adgangskode</h2>
        <p>Hej,</p>
        <p>Du har anmodet om at nulstille din adgangskode til Budget.</p>
        <p>
            <a href="{reset_url}" style="display: inline-block; background-color: #3b82f6; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: 500;">
                Nulstil adgangskode
            </a>
        </p>
        <p style="color: #666; font-size: 14px;">Linket udløber om 1 time.</p>
        <p style="color: #666; font-size: 14px;">Hvis du ikke har anmodet om dette, kan du ignorere denne email.</p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="color: #999; font-size: 12px;">Med venlig hilsen,<br>Budget</p>
    </div>
</body>
</html>
"""

    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            if smtp_user and smtp_pass:
                server.starttls()
                server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_from, to_email, msg.as_string())
        logger.info(f"Password reset email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send password reset email: {e}")
        return False


@app.get("/budget/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    """Show forgot password page."""
    if get_user_id(request) is not None:
        return RedirectResponse(url="/budget/", status_code=303)
    return templates.TemplateResponse("forgot-password.html", {"request": request})


@app.post("/budget/forgot-password")
async def forgot_password(request: Request, email: str = Form(...)):
    """Handle forgot password request."""
    email = email.strip().lower()

    # Always show success message to prevent email enumeration
    success_message = "Hvis emailen findes i vores system, har vi sendt et link til at nulstille din adgangskode."

    # Find user by email
    user = db.get_user_by_email(email)
    if user:
        # Generate secure token
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expires_at = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")

        # Store token
        db.create_password_reset_token(user.id, token_hash, expires_at)

        # Build reset URL
        host = request.headers.get("host", "localhost")
        scheme = "https" if request.url.scheme == "https" or "localhost" not in host else "http"
        reset_url = f"{scheme}://{host}/budget/reset-password/{token}"

        # Send email
        send_password_reset_email(email, reset_url)

    return templates.TemplateResponse(
        "forgot-password.html",
        {"request": request, "success": success_message}
    )


@app.get("/budget/reset-password/{token}", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str):
    """Show reset password page."""
    # Validate token
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    reset_token = db.get_valid_reset_token(token_hash)

    if not reset_token:
        return templates.TemplateResponse(
            "reset-password.html",
            {"request": request, "invalid_token": "Dette link er ugyldigt eller udløbet. Anmod om et nyt link."}
        )

    return templates.TemplateResponse(
        "reset-password.html",
        {"request": request, "token": token}
    )


@app.post("/budget/reset-password/{token}")
async def reset_password(
    request: Request,
    token: str,
    password: str = Form(...),
    password_confirm: str = Form(...)
):
    """Handle password reset."""
    # Validate token
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    reset_token = db.get_valid_reset_token(token_hash)

    if not reset_token:
        return templates.TemplateResponse(
            "reset-password.html",
            {"request": request, "invalid_token": "Dette link er ugyldigt eller udløbet. Anmod om et nyt link."}
        )

    # Validate password
    if len(password) < 6:
        return templates.TemplateResponse(
            "reset-password.html",
            {"request": request, "token": token, "error": "Adgangskoden skal være mindst 6 tegn"}
        )

    if password != password_confirm:
        return templates.TemplateResponse(
            "reset-password.html",
            {"request": request, "token": token, "error": "Adgangskoderne matcher ikke"}
        )

    # Update password
    db.update_user_password(reset_token.user_id, password)

    # Mark token as used
    db.mark_reset_token_used(reset_token.id)

    return templates.TemplateResponse(
        "reset-password.html",
        {"request": request, "success": "Din adgangskode er blevet nulstillet. Du kan nu logge ind."}
    )


@app.get("/budget/demo")
async def demo_mode(request: Request):
    """Enter demo mode with pre-filled example data."""
    response = RedirectResponse(url="/budget/", status_code=303)
    response.set_cookie(
        key="budget_session",
        value=DEMO_SESSION_ID,
        httponly=True,
        secure=True,       # Only send over HTTPS
        samesite="lax",
        max_age=3600  # Demo expires after 1 hour
    )
    return response


@app.get("/budget/demo/toggle")
async def demo_toggle(request: Request):
    """Toggle between simple and advanced demo mode."""
    if not is_demo_mode(request):
        return RedirectResponse(url="/budget/login", status_code=303)

    current = request.cookies.get("demo_level", "simple")
    new_level = "simple" if current == "advanced" else "advanced"

    # Redirect back to referring page, or dashboard (validate to prevent open redirect)
    referer = request.headers.get("referer", "/budget/")
    parsed = urlparse(referer)
    if parsed.scheme or parsed.netloc:
        referer = "/budget/"
    response = RedirectResponse(url=referer, status_code=303)
    response.set_cookie(
        key="demo_level",
        value=new_level,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=3600,
    )
    return response


@app.get("/budget/logout")
async def logout(request: Request):
    """Logout and clear session."""
    session_id = request.cookies.get("budget_session")
    if session_id:
        hashed = hash_token(session_id)
        if hashed in SESSIONS:
            del SESSIONS[hashed]
            save_sessions(SESSIONS)

    response = RedirectResponse(url="/budget/login", status_code=303)
    response.delete_cookie("budget_session")
    response.delete_cookie("demo_level")
    return response


# =============================================================================
# Dashboard
# =============================================================================

@app.get("/budget/", response_class=HTMLResponse)
@app.get("/budget", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page."""
    if not check_auth(request):
        return RedirectResponse(url="/budget/login", status_code=303)

    demo = is_demo_mode(request)
    advanced = is_demo_advanced(request)
    user_id = get_user_id(request)

    # Get data (demo or real)
    if demo:
        incomes = db.get_demo_income(advanced)
        total_income = db.get_demo_total_income(advanced)
        total_expenses = db.get_demo_total_expenses(advanced)
        expenses_by_category = db.get_demo_expenses_by_category(advanced)
        category_totals = db.get_demo_category_totals(advanced)
        account_totals = db.get_demo_account_totals(advanced)
        yearly_overview = db.get_yearly_overview_demo(advanced)
    else:
        incomes = db.get_all_income(user_id)
        total_income = db.get_total_income(user_id)
        total_expenses = db.get_total_monthly_expenses(user_id)
        expenses_by_category = db.get_expenses_by_category(user_id)
        category_totals = db.get_category_totals(user_id)
        account_totals = db.get_account_totals(user_id)
        yearly_overview = db.get_yearly_overview(user_id)

    remaining = total_income - total_expenses

    # Calculate percentages for progress bars
    category_percentages = {}
    if total_expenses > 0:
        for cat, total in category_totals.items():
            category_percentages[cat] = (total / total_expenses) * 100

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "incomes": incomes,
            "total_income": total_income,
            "total_expenses": total_expenses,
            "remaining": remaining,
            "expenses_by_category": expenses_by_category,
            "category_totals": category_totals,
            "category_percentages": category_percentages,
            "account_totals": account_totals,
            "yearly_overview": yearly_overview,
            "demo_mode": demo,
            "demo_advanced": advanced,
        }
    )


# =============================================================================
# Income
# =============================================================================

@app.get("/budget/income", response_class=HTMLResponse)
async def income_page(request: Request):
    """Income edit page."""
    if not check_auth(request):
        return RedirectResponse(url="/budget/login", status_code=303)

    demo = is_demo_mode(request)
    advanced = is_demo_advanced(request)
    user_id = get_user_id(request)

    if demo:
        incomes = db.get_demo_income(advanced)
    else:
        incomes = db.get_all_income(user_id)

    return templates.TemplateResponse(
        "income.html",
        {"request": request, "incomes": incomes, "demo_mode": demo, "demo_advanced": advanced}
    )


@app.post("/budget/income")
async def update_income(request: Request):
    """Update income values - handles dynamic number of income sources."""
    if not check_auth(request):
        return RedirectResponse(url="/budget/login", status_code=303)
    if is_demo_mode(request):
        return RedirectResponse(url="/budget/", status_code=303)

    user_id = get_user_id(request)
    form = await request.form()

    try:
        # Parse dynamic form fields: income_name_0, income_amount_0, income_frequency_0, etc.
        incomes_to_save = []
        i = 0
        while f"income_name_{i}" in form:
            name = form.get(f"income_name_{i}", "").strip()
            amount_str = form.get(f"income_amount_{i}", "0")
            frequency = form.get(f"income_frequency_{i}", "monthly")
            if name:  # Only save if name is provided
                try:
                    amount = parse_danish_amount(amount_str) if amount_str else 0.00
                except ValueError:
                    raise HTTPException(status_code=400, detail=f"Ugyldigt beløb format for {name}")
                # Validate frequency
                if frequency not in ('monthly', 'quarterly', 'semi-annual', 'yearly'):
                    frequency = 'monthly'
                incomes_to_save.append((name, amount, frequency))
            i += 1

        # Clear existing and save new
        db.delete_all_income(user_id)
        for name, amount, frequency in incomes_to_save:
            db.add_income(user_id, name, amount, frequency)

    except (ValueError, sqlite3.Error) as e:
        logger.error(f"Error updating income: {e}")
        raise HTTPException(status_code=500, detail="Der opstod en fejl ved opdatering af indkomst")

    return RedirectResponse(url="/budget/", status_code=303)


# =============================================================================
# Expenses
# =============================================================================

@app.get("/budget/expenses", response_class=HTMLResponse)
async def expenses_page(request: Request):
    """Expenses management page."""
    if not check_auth(request):
        return RedirectResponse(url="/budget/login", status_code=303)

    user_id = get_user_id(request)
    demo = is_demo_mode(request)
    advanced = is_demo_advanced(request)

    if demo:
        expenses = db.get_demo_expenses(advanced)
        expenses_by_category = db.get_demo_expenses_by_category(advanced)
        category_totals = db.get_demo_category_totals(advanced)
        # Use demo user categories (user_id = 0)
        categories = db.get_all_categories(0)
        category_usage = {cat.name: 0 for cat in categories}
        accounts = db.get_demo_accounts(advanced)
    else:
        expenses = db.get_all_expenses(user_id)
        expenses_by_category = db.get_expenses_by_category(user_id)
        category_totals = db.get_category_totals(user_id)
        categories = db.get_all_categories(user_id)
        category_usage = {cat.name: db.get_category_usage_count(cat.name, user_id) for cat in categories}
        accounts = db.get_all_accounts(user_id)

    return templates.TemplateResponse(
        "expenses.html",
        {
            "request": request,
            "expenses": expenses,
            "expenses_by_category": expenses_by_category,
            "category_totals": category_totals,
            "categories": categories,
            "category_usage": category_usage,
            "accounts": accounts,
            "demo_mode": demo,
            "demo_advanced": advanced,
        }
    )


VALID_FREQUENCIES = ('monthly', 'quarterly', 'semi-annual', 'yearly')

MONTHS_REQUIRED = {
    'quarterly': 4,
    'semi-annual': 2,
    'yearly': 1,
}


def parse_months(months_str: str | None, frequency: str) -> list[int] | None:
    """Parse and validate months form field.

    Returns list of month ints, or None if no months specified.
    Raises HTTPException(400) if validation fails.
    """
    if frequency == 'monthly':
        return None

    if not months_str or not months_str.strip():
        return None

    try:
        months = [int(m.strip()) for m in months_str.split(',')]
    except ValueError:
        raise HTTPException(status_code=400, detail="Ugyldige måneder")

    if any(m < 1 or m > 12 for m in months):
        raise HTTPException(status_code=400, detail="Måneder skal være mellem 1 og 12")

    expected = MONTHS_REQUIRED.get(frequency)
    if expected and len(months) != expected:
        raise HTTPException(status_code=400, detail=f"Vælg præcis {expected} måneder for denne frekvens")

    return sorted(months)


@app.post("/budget/expenses/add")
async def add_expense(
    request: Request,
    name: str = Form(...),
    category: str = Form(...),
    amount: str = Form(...),
    frequency: str = Form(...),
    account: str = Form(""),
    months: str = Form(""),
):
    """Add a new expense."""
    if not check_auth(request):
        return RedirectResponse(url="/budget/login", status_code=303)
    if is_demo_mode(request):
        return RedirectResponse(url="/budget/expenses", status_code=303)

    # Validate frequency
    if frequency not in VALID_FREQUENCIES:
        raise HTTPException(status_code=400, detail="Ugyldig frekvens")

    # Parse and validate amount
    try:
        amount_float = parse_danish_amount(amount)
    except ValueError:
        raise HTTPException(status_code=400, detail="Ugyldigt beløb format")

    if amount_float < 0:
        raise HTTPException(status_code=400, detail="Beløb skal være positivt")
    if amount_float > 1000000:
        raise HTTPException(status_code=400, detail="Beløb er for stort")

    months_list = parse_months(months if months else None, frequency)

    user_id = get_user_id(request)
    account_value = account if account else None
    try:
        db.add_expense(user_id, name, category, amount_float, frequency, account_value, months=months_list)
    except sqlite3.Error as e:
        logger.error(f"Database error adding expense: {e}")
        raise HTTPException(status_code=500, detail="Der opstod en fejl ved tilfoejelse af udgiften")
    return RedirectResponse(url="/budget/expenses", status_code=303)


@app.post("/budget/expenses/{expense_id}/delete")
async def delete_expense(request: Request, expense_id: int):
    """Delete an expense."""
    if not check_auth(request):
        return RedirectResponse(url="/budget/login", status_code=303)
    if is_demo_mode(request):
        return RedirectResponse(url="/budget/expenses", status_code=303)

    user_id = get_user_id(request)
    try:
        db.delete_expense(expense_id, user_id)
    except sqlite3.Error as e:
        logger.error(f"Database error deleting expense: {e}")
        raise HTTPException(status_code=500, detail="Der opstod en fejl ved sletning af udgiften")
    return RedirectResponse(url="/budget/expenses", status_code=303)


@app.post("/budget/expenses/{expense_id}/edit")
async def edit_expense(
    request: Request,
    expense_id: int,
    name: str = Form(...),
    category: str = Form(...),
    amount: str = Form(...),
    frequency: str = Form(...),
    account: str = Form(""),
    months: str = Form(""),
):
    """Edit an expense."""
    if not check_auth(request):
        return RedirectResponse(url="/budget/login", status_code=303)
    if is_demo_mode(request):
        return RedirectResponse(url="/budget/expenses", status_code=303)

    # Validate frequency
    if frequency not in VALID_FREQUENCIES:
        raise HTTPException(status_code=400, detail="Ugyldig frekvens")

    # Parse and validate amount
    try:
        amount_float = parse_danish_amount(amount)
    except ValueError:
        raise HTTPException(status_code=400, detail="Ugyldigt beløb format")

    if amount_float < 0:
        raise HTTPException(status_code=400, detail="Beløb skal være positivt")
    if amount_float > 1000000:
        raise HTTPException(status_code=400, detail="Beløb er for stort")

    months_list = parse_months(months if months else None, frequency)

    user_id = get_user_id(request)
    account_value = account if account else None
    try:
        db.update_expense(expense_id, user_id, name, category, amount_float, frequency, account_value, months=months_list)
    except sqlite3.Error as e:
        logger.error(f"Database error updating expense: {e}")
        raise HTTPException(status_code=500, detail="Der opstod en fejl ved opdatering af udgiften")
    return RedirectResponse(url="/budget/expenses", status_code=303)


# =============================================================================
# Categories
# =============================================================================

@app.get("/budget/categories", response_class=HTMLResponse)
async def categories_page(request: Request):
    """Categories management page."""
    if not check_auth(request):
        return RedirectResponse(url="/budget/login", status_code=303)

    user_id = get_user_id(request)
    demo = is_demo_mode(request)

    # Use demo user (user_id = 0) for demo mode
    effective_user_id = 0 if demo else user_id
    categories = db.get_all_categories(effective_user_id)

    # Get usage count for each category (0 for demo mode since it's read-only)
    if demo:
        category_usage = {cat.name: 0 for cat in categories}
    else:
        category_usage = {cat.name: db.get_category_usage_count(cat.name, user_id) for cat in categories}

    return templates.TemplateResponse(
        "categories.html",
        {
            "request": request,
            "categories": categories,
            "category_usage": category_usage,
            "demo_mode": demo,
            "demo_advanced": is_demo_advanced(request),
        }
    )


@app.post("/budget/categories/add")
async def add_category(
    request: Request,
    name: str = Form(...),
    icon: str = Form(...)
):
    """Add a new category."""
    if not check_auth(request):
        return RedirectResponse(url="/budget/login", status_code=303)
    if is_demo_mode(request):
        return RedirectResponse(url="/budget/categories", status_code=303)

    user_id = get_user_id(request)
    try:
        db.add_category(user_id, name, icon)
    except sqlite3.IntegrityError:
        # Category name already exists for this user (UNIQUE constraint)
        raise HTTPException(
            status_code=400,
            detail=f"Kategorien '{name}' findes allerede"
        )
    return RedirectResponse(url="/budget/categories", status_code=303)


@app.post("/budget/categories/{category_id}/edit")
async def edit_category(
    request: Request,
    category_id: int,
    name: str = Form(...),
    icon: str = Form(...),
    next: str = Form("")
):
    """Edit a category."""
    if not check_auth(request):
        return RedirectResponse(url="/budget/login", status_code=303)
    if is_demo_mode(request):
        return RedirectResponse(url="/budget/categories", status_code=303)

    user_id = get_user_id(request)
    try:
        updated_count = db.update_category(category_id, user_id, name, icon)
    except sqlite3.IntegrityError:
        # Category name already exists for this user (UNIQUE constraint)
        raise HTTPException(
            status_code=400,
            detail=f"Kategorien '{name}' findes allerede"
        )
    allowed_next = {"/budget/expenses", "/budget/categories"}
    base_url = next if next in allowed_next else "/budget/categories"
    url = base_url
    if updated_count > 0:
        url += f"?updated={updated_count}"
    return RedirectResponse(url=url, status_code=303)


@app.post("/budget/categories/{category_id}/delete")
async def delete_category(request: Request, category_id: int):
    """Delete a category for the current user.

    Categories are per-user. Deletion is only allowed for categories owned by
    the current user, and only if the category is not in use.
    """
    if not check_auth(request):
        return RedirectResponse(url="/budget/login", status_code=303)
    if is_demo_mode(request):
        return RedirectResponse(url="/budget/categories", status_code=303)

    user_id = get_user_id(request)
    try:
        success = db.delete_category(category_id, user_id)
        if not success:
            # Category is in use, doesn't exist, or not owned by user
            raise HTTPException(
                status_code=400,
                detail="Kategorien kan ikke slettes - den er stadig i brug"
            )
    except sqlite3.Error as e:
        logger.error(f"Database error deleting category: {e}")
        raise HTTPException(status_code=500, detail="Der opstod en fejl ved sletning af kategorien")
    return RedirectResponse(url="/budget/categories", status_code=303)


# =============================================================================
# Accounts
# =============================================================================

@app.get("/budget/accounts", response_class=HTMLResponse)
async def accounts_page(request: Request):
    """Accounts management page."""
    if not check_auth(request):
        return RedirectResponse(url="/budget/login", status_code=303)

    user_id = get_user_id(request)
    demo = is_demo_mode(request)

    effective_user_id = 0 if demo else user_id
    accounts = db.get_all_accounts(effective_user_id)

    if demo:
        account_usage = {acc.name: 0 for acc in accounts}
    else:
        account_usage = {acc.name: db.get_account_usage_count(acc.name, user_id) for acc in accounts}

    return templates.TemplateResponse(
        "accounts.html",
        {
            "request": request,
            "accounts": accounts,
            "account_usage": account_usage,
            "demo_mode": demo,
            "demo_advanced": is_demo_advanced(request),
        }
    )


@app.post("/budget/accounts/add")
async def add_account(
    request: Request,
    name: str = Form(...)
):
    """Add a new account."""
    if not check_auth(request):
        return RedirectResponse(url="/budget/login", status_code=303)
    if is_demo_mode(request):
        return RedirectResponse(url="/budget/accounts", status_code=303)

    user_id = get_user_id(request)
    try:
        db.add_account(user_id, name)
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=400,
            detail=f"Kontoen '{name}' findes allerede"
        )
    return RedirectResponse(url="/budget/accounts", status_code=303)


@app.post("/budget/accounts/add-json")
async def add_account_json(request: Request, name: str = Form(...)):
    """Add a new account and return JSON (for inline creation from expense form)."""
    if not check_auth(request):
        return JSONResponse({"success": False, "error": "Ikke logget ind"}, status_code=401)
    if is_demo_mode(request):
        return JSONResponse({"success": False, "error": "Ikke tilgængelig i demo"}, status_code=403)

    user_id = get_user_id(request)
    name = name.strip()
    if not name:
        return JSONResponse({"success": False, "error": "Navn er påkrævet"}, status_code=400)

    try:
        db.add_account(user_id, name)
    except sqlite3.IntegrityError:
        return JSONResponse(
            {"success": False, "error": f"Kontoen '{name}' findes allerede"},
            status_code=400,
        )
    return JSONResponse({"success": True, "name": name})


@app.post("/budget/accounts/{account_id}/edit")
async def edit_account(
    request: Request,
    account_id: int,
    name: str = Form(...)
):
    """Edit an account."""
    if not check_auth(request):
        return RedirectResponse(url="/budget/login", status_code=303)
    if is_demo_mode(request):
        return RedirectResponse(url="/budget/accounts", status_code=303)

    user_id = get_user_id(request)
    try:
        updated_count = db.update_account(account_id, user_id, name)
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=400,
            detail=f"Kontoen '{name}' findes allerede"
        )
    url = "/budget/accounts"
    if updated_count > 0:
        url += f"?updated={updated_count}"
    return RedirectResponse(url=url, status_code=303)


@app.post("/budget/accounts/{account_id}/delete")
async def delete_account(request: Request, account_id: int):
    """Delete an account for the current user."""
    if not check_auth(request):
        return RedirectResponse(url="/budget/login", status_code=303)
    if is_demo_mode(request):
        return RedirectResponse(url="/budget/accounts", status_code=303)

    user_id = get_user_id(request)
    try:
        success = db.delete_account(account_id, user_id)
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Kontoen kan ikke slettes - den er stadig i brug"
            )
    except sqlite3.Error as e:
        logger.error(f"Database error deleting account: {e}")
        raise HTTPException(status_code=500, detail="Der opstod en fejl ved sletning af kontoen")
    return RedirectResponse(url="/budget/accounts", status_code=303)


# =============================================================================
# Om (About)
# =============================================================================

@app.get("/budget/om", response_class=HTMLResponse)
async def about_page(request: Request):
    """About page with user guide and self-hosting info."""
    logged_in = check_auth(request)
    demo_mode = is_demo_mode(request)
    return templates.TemplateResponse(
        "om.html",
        {
            "request": request,
            "demo_mode": demo_mode,
            "demo_advanced": is_demo_advanced(request),
            "show_nav": logged_in or demo_mode,
            "donation_links": DONATION_LINKS if not demo_mode else {},
        }
    )


@app.get("/budget/help", response_class=HTMLResponse)
async def help_redirect(request: Request):
    """Redirect old help URL to new about page."""
    return RedirectResponse(url="/budget/om", status_code=301)


# =============================================================================
# Privacy Policy
# =============================================================================

@app.get("/budget/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    """Privacy policy page - accessible without login."""
    return templates.TemplateResponse(
        "privacy.html",
        {"request": request, "show_nav": False}
    )


# =============================================================================
# Feedback
# =============================================================================

# GitHub repository for feedback issues
GITHUB_REPO = os.environ.get("GITHUB_REPO", "saabendtsen/family-budget")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# Rate limiting for feedback (IP -> list of timestamps)
feedback_attempts: dict[str, list[float]] = defaultdict(list)
FEEDBACK_RATE_LIMIT = 5  # max submissions
FEEDBACK_RATE_WINDOW = 3600  # per hour


def check_feedback_rate_limit(client_ip: str) -> bool:
    """Check if client has exceeded feedback rate limit."""
    now = time.time()
    # Clean old attempts
    feedback_attempts[client_ip] = [
        t for t in feedback_attempts[client_ip]
        if now - t < FEEDBACK_RATE_WINDOW
    ]
    return len(feedback_attempts[client_ip]) < FEEDBACK_RATE_LIMIT


def record_feedback_attempt(client_ip: str):
    """Record a feedback submission attempt."""
    feedback_attempts[client_ip].append(time.time())


@app.get("/budget/feedback", response_class=HTMLResponse)
async def feedback_page(request: Request):
    """Feedback submission page."""
    if not check_auth(request):
        return RedirectResponse(url="/budget/login", status_code=303)

    return templates.TemplateResponse(
        "feedback.html",
        {"request": request, "demo_mode": is_demo_mode(request), "demo_advanced": is_demo_advanced(request)}
    )


@app.post("/budget/feedback")
async def submit_feedback(
    request: Request,
    feedback_type: str = Form(...),
    description: str = Form(...),
    email: str = Form(""),
    website: str = Form("")  # Honeypot field
):
    """Submit feedback - creates a GitHub issue."""
    if not check_auth(request):
        return RedirectResponse(url="/budget/login", status_code=303)

    demo = is_demo_mode(request)
    client_ip = request.client.host if request.client else "unknown"

    # Honeypot check (bots fill hidden fields)
    if website:
        logger.warning(f"Honeypot triggered from {client_ip}")
        # Pretend success to fool bots
        return templates.TemplateResponse(
            "feedback.html",
            {"request": request, "success": True, "demo_mode": demo, "demo_advanced": is_demo_advanced(request)}
        )

    # Rate limiting
    if not check_feedback_rate_limit(client_ip):
        return templates.TemplateResponse(
            "feedback.html",
            {
                "request": request,
                "error": "For mange henvendelser. Prøv igen senere.",
                "demo_mode": demo,
                "demo_advanced": is_demo_advanced(request),
            }
        )

    # Validate input
    if len(description.strip()) < 10:
        return templates.TemplateResponse(
            "feedback.html",
            {
                "request": request,
                "error": "Beskrivelsen skal være mindst 10 tegn.",
                "demo_mode": demo,
                "demo_advanced": is_demo_advanced(request),
            }
        )

    # Map feedback type to label and title prefix
    type_config = {
        "feedback": {"label": "feedback", "prefix": "Feedback"},
        "feature": {"label": "enhancement", "prefix": "Feature request"},
        "bug": {"label": "bug", "prefix": "Bug report"},
    }
    config = type_config.get(feedback_type, type_config["feedback"])

    # Build issue body
    body_parts = [description.strip()]
    if email:
        body_parts.append(f"\n---\n**Kontakt email:** {email}")
    body_parts.append("\n---\n*Sendt via Budget app feedback*")

    # Create GitHub issue if token is configured
    if GITHUB_TOKEN:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api.github.com/repos/{GITHUB_REPO}/issues",
                    headers={
                        "Authorization": f"Bearer {GITHUB_TOKEN}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    json={
                        "title": f"{config['prefix']}: {description[:50]}...",
                        "body": "\n".join(body_parts),
                        "labels": [config["label"], "from-app"],
                    },
                    timeout=10.0,
                )
                if response.status_code not in (200, 201):
                    logger.error(f"GitHub API error: {response.status_code} - {response.text}")
                    raise Exception("GitHub API error")
        except Exception as e:
            logger.error(f"Failed to create GitHub issue: {e}")
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
        # No token configured - just log the feedback
        logger.info(f"Feedback ({feedback_type}): {description[:100]}...")

    record_feedback_attempt(client_ip)

    return templates.TemplateResponse(
        "feedback.html",
        {"request": request, "success": True, "demo_mode": demo, "demo_advanced": is_demo_advanced(request)}
    )


# =============================================================================
# Public API (for uptime dashboard)
# =============================================================================

@app.get("/budget/api/stats")
async def api_stats():
    """Public stats endpoint for uptime dashboard."""
    user_count = db.get_user_count()
    return {"users": user_count}


@app.get("/budget/api/chart-data")
async def chart_data(request: Request):
    """API endpoint for chart visualizations.

    Returns JSON with category_totals, total_income, total_expenses, top_expenses.
    All amounts are monthly equivalents.
    """
    if not check_auth(request):
        return RedirectResponse(url="/budget/login", status_code=303)

    demo = is_demo_mode(request)
    advanced = is_demo_advanced(request)
    user_id = get_user_id(request)

    # Get data based on mode
    if demo:
        category_totals = db.get_demo_category_totals(advanced)
        total_income = db.get_demo_total_income(advanced)
        total_expenses = db.get_demo_total_expenses(advanced)
        expenses = db.get_demo_expenses(advanced)
    else:
        category_totals = db.get_category_totals(user_id)
        total_income = db.get_total_income(user_id)
        total_expenses = db.get_total_monthly_expenses(user_id)
        expenses = db.get_all_expenses(user_id)

    # Get top 5 expenses by monthly amount
    sorted_expenses = sorted(expenses, key=lambda e: e.monthly_amount, reverse=True)
    top_expenses = [
        {
            "name": exp.name,
            "amount": exp.monthly_amount,
            "category": exp.category
        }
        for exp in sorted_expenses[:5]
    ]

    # Group small categories as "Andet (samlet)" if more than 6 categories
    if len(category_totals) > 6:
        sorted_cats = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
        top_cats = dict(sorted_cats[:6])
        other_total = sum(amount for _, amount in sorted_cats[6:])
        if other_total > 0:
            top_cats["Andet (samlet)"] = other_total
        category_totals = top_cats

    return {
        "category_totals": category_totals,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "top_expenses": top_expenses
    }


# =============================================================================
# Settings
# =============================================================================

@app.get("/budget/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Account settings page."""
    if not check_auth(request):
        return RedirectResponse(url="/budget/login", status_code=303)
    if is_demo_mode(request):
        return RedirectResponse(url="/budget/", status_code=303)

    user_id = get_user_id(request)
    user = db.get_user_by_id(user_id)

    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "username": user.username if user else "Ukendt",
            "has_email": user.has_email() if user else False
        }
    )


@app.post("/budget/settings/email")
async def update_email(
    request: Request,
    email: str = Form("")
):
    """Update user email hash.

    Only the email hash is stored for password reset verification.
    The actual email is never stored.
    """
    if not check_auth(request):
        return RedirectResponse(url="/budget/login", status_code=303)
    if is_demo_mode(request):
        return RedirectResponse(url="/budget/", status_code=303)

    user_id = get_user_id(request)
    user = db.get_user_by_id(user_id)
    email = email.strip() if email else None

    # If clearing email
    if not email:
        db.update_user_email(user_id, None)
        return templates.TemplateResponse(
            "settings.html",
            {
                "request": request,
                "username": user.username if user else "Ukendt",
                "has_email": False,
                "success": "Email fjernet"
            }
        )

    # Validate email format
    if "@" not in email:
        return templates.TemplateResponse(
            "settings.html",
            {
                "request": request,
                "username": user.username if user else "Ukendt",
                "has_email": user.has_email() if user else False,
                "error": "Ugyldig email-adresse"
            }
        )

    # Save email hash
    db.update_user_email(user_id, email)

    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "username": user.username if user else "Ukendt",
            "has_email": True,
            "success": "Email tilføjet"
        }
    )


# =============================================================================
# Yearly overview
# =============================================================================

@app.get("/budget/yearly", response_class=HTMLResponse)
async def yearly_overview_page(request: Request):
    """Yearly overview page with monthly expense breakdown."""
    if not check_auth(request):
        return RedirectResponse(url="/budget/login", status_code=303)

    user_id = get_user_id(request)
    demo = is_demo_mode(request)

    if demo:
        overview = db.get_yearly_overview_demo()
    else:
        overview = db.get_yearly_overview(user_id)

    return templates.TemplateResponse("yearly.html", {
        "request": request,
        "overview": overview,
        "demo_mode": demo,
    })


# =============================================================================
# Run with: python -m src.api
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8086)
