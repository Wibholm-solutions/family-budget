"""Password reset routes for Family Budget."""

import hashlib
import logging
import os
import secrets
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import database as db
from ..helpers import get_user_id, templates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/budget")


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


@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    """Show forgot password page."""
    if get_user_id(request) is not None:
        return RedirectResponse(url="/budget/", status_code=303)
    return templates.TemplateResponse("forgot-password.html", {"request": request})


@router.post("/forgot-password")
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


@router.get("/reset-password/{token}", response_class=HTMLResponse)
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


@router.post("/reset-password/{token}")
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
