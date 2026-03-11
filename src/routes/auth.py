"""Authentication routes for Family Budget."""

import secrets
from urllib.parse import urlparse

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import database as db
from ..helpers import (
    DEMO_SESSION_ID,
    SESSIONS,
    get_user_id,
    hash_token,
    is_demo_mode,
    save_sessions,
    templates,
)

router = APIRouter(prefix="/budget")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Show login page."""
    if get_user_id(request) is not None:
        return RedirectResponse(url="/budget/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
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


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Show registration page."""
    if get_user_id(request) is not None:
        return RedirectResponse(url="/budget/", status_code=303)
    return templates.TemplateResponse("register.html", {"request": request})


@router.post("/register")
async def register(  # noqa: PLR0911
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


@router.get("/demo")
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


@router.get("/demo/toggle")
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


@router.get("/logout")
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
