"""Settings routes for Family Budget."""

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import database as db
from ..helpers import (
    check_auth,
    get_user_id,
    is_demo_mode,
    templates,
)

router = APIRouter(prefix="/budget")


@router.get("/settings", response_class=HTMLResponse)
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


@router.post("/settings/email")
async def update_email(  # noqa: PLR0911
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
