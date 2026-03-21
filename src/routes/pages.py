"""Static page routes for Family Budget (about, help, privacy, feedback)."""

import logging
import os
import time
from collections import defaultdict

import httpx
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..dependencies import require_auth
from ..helpers import (
    DONATION_LINKS,
    check_auth,
    is_demo_advanced,
    is_demo_mode,
    templates,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/budget")


# =============================================================================
# Om (About)
# =============================================================================

@router.get("/om", response_class=HTMLResponse)
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


@router.get("/help", response_class=HTMLResponse)
async def help_redirect(request: Request):
    """Redirect old help URL to new about page."""
    return RedirectResponse(url="/budget/om", status_code=301)


# =============================================================================
# Privacy Policy
# =============================================================================

@router.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    """Privacy policy page - accessible without login."""
    return templates.TemplateResponse(
        "privacy.html",
        {"request": request, "show_nav": False}
    )


# =============================================================================
# Feedback
# =============================================================================

# Feedback API configuration
FEEDBACK_API_URL = os.environ.get("FEEDBACK_API_URL", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "Wibholm-solutions/family-budget")

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


@router.get("/feedback", response_class=HTMLResponse)
async def feedback_page(request: Request, _: None = Depends(require_auth)):
    """Feedback submission page."""
    return templates.TemplateResponse(
        "feedback.html",
        {"request": request, "demo_mode": is_demo_mode(request), "demo_advanced": is_demo_advanced(request)}
    )


@router.post("/feedback")
async def submit_feedback(  # noqa: PLR0911, PLR0912
    request: Request,
    feedback_type: str = Form(...),
    description: str = Form(...),
    email: str = Form(""),
    website: str = Form(""),  # Honeypot field
    _: None = Depends(require_auth),
):
    """Submit feedback via feedback-api."""
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

    # Send to feedback-api
    if FEEDBACK_API_URL:
        try:
            async with httpx.AsyncClient() as http_client:
                response = await http_client.post(
                    f"{FEEDBACK_API_URL}/api/feedback",
                    json={
                        "repo": GITHUB_REPO,
                        "title": f"{config['prefix']}: {description[:50]}...",
                        "description": "\n".join(body_parts),
                        "type": feedback_type,
                    },
                    timeout=10.0,
                )
                if response.status_code not in (200, 201):
                    logger.error(f"feedback-api error: {response.status_code} - {response.text}")
                    raise Exception("feedback-api error")
        except Exception as e:
            logger.error(f"Failed to send feedback: {e}")
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
        # No feedback API configured - just log
        logger.info(f"Feedback ({feedback_type}): {description[:100]}...")

    record_feedback_attempt(client_ip)

    return templates.TemplateResponse(
        "feedback.html",
        {"request": request, "success": True, "demo_mode": demo, "demo_advanced": is_demo_advanced(request)}
    )
