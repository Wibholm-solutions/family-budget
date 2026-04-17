"""Yearly overview route for Family Budget."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from ..db.facade import DataContext
from ..dependencies import get_data
from ..helpers import templates

router = APIRouter(prefix="/budget")


@router.get("/yearly", response_class=HTMLResponse)
async def yearly_overview_page(request: Request, ctx: DataContext = Depends(get_data)):
    """Yearly overview page with monthly expense breakdown."""
    overview = ctx.yearly_overview()

    return templates.TemplateResponse(request, "yearly.html", {
        "overview": overview,
        "demo_mode": ctx.demo,
    })
