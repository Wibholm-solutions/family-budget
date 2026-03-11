"""Yearly overview route for Family Budget."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import database as db
from ..helpers import (
    check_auth,
    get_user_id,
    is_demo_mode,
    templates,
)

router = APIRouter(prefix="/budget")


@router.get("/yearly", response_class=HTMLResponse)
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
