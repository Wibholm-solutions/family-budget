"""Settings routes for Family Budget."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse

from .. import database as db
from ..dependencies import require_write
from ..helpers import (
    get_user_id,
    templates,
)

router = APIRouter(prefix="/budget")


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, _: None = Depends(require_write("/budget/"))):
    """Account settings page."""
    user_id = get_user_id(request)
    user = db.get_user_by_id(user_id)

    return templates.TemplateResponse(request,
        "settings.html",
        {
            "username": user.username if user else "Ukendt",
            "has_email": user.has_email() if user else False
        }
    )


@router.post("/settings/email")
async def update_email(  # noqa: PLR0911
    request: Request,
    email: str = Form(""),
    _: None = Depends(require_write("/budget/")),
):
    """Update user email hash.

    Only the email hash is stored for password reset verification.
    The actual email is never stored.
    """
    user_id = get_user_id(request)
    user = db.get_user_by_id(user_id)
    email = email.strip() if email else None

    # If clearing email
    if not email:
        db.update_user_email(user_id, None)
        return templates.TemplateResponse(request,
            "settings.html",
            {
                "username": user.username if user else "Ukendt",
                "has_email": False,
                "success": "Email fjernet"
            }
        )

    # Validate email format
    if "@" not in email:
        return templates.TemplateResponse(request,
            "settings.html",
            {
                "username": user.username if user else "Ukendt",
                "has_email": user.has_email() if user else False,
                "error": "Ugyldig email-adresse"
            }
        )

    # Save email hash
    db.update_user_email(user_id, email)

    return templates.TemplateResponse(request,
        "settings.html",
        {
            "username": user.username if user else "Ukendt",
            "has_email": True,
            "success": "Email tilføjet"
        }
    )
