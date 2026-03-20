"""Yearly overview route for Family Budget."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from ..db.facade import DataContext
from ..dependencies import require_auth
from ..helpers import (
    get_user_id,
    is_demo_mode,
    templates,
)

router = APIRouter(prefix="/budget")


@router.get("/yearly", response_class=HTMLResponse)
async def yearly_overview_page(request: Request, _: None = Depends(require_auth)):
    """Yearly overview page with monthly expense breakdown."""
    user_id = get_user_id(request)
    demo = is_demo_mode(request)

    ctx = DataContext(user_id=user_id, demo=demo)
    overview = ctx.yearly_overview()

    return templates.TemplateResponse("yearly.html", {
        "request": request,
        "overview": overview,
        "demo_mode": demo,
    })
