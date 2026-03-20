"""Dashboard route for Family Budget."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from ..db.facade import DataContext
from ..dependencies import require_auth
from ..helpers import (
    get_user_id,
    is_demo_advanced,
    is_demo_mode,
    templates,
)

router = APIRouter(prefix="/budget")


@router.get("/", response_class=HTMLResponse)
@router.get("", response_class=HTMLResponse)
async def dashboard(request: Request, _: None = Depends(require_auth)):
    """Main dashboard page."""
    demo = is_demo_mode(request)
    advanced = is_demo_advanced(request)
    user_id = get_user_id(request)

    # Get data (demo or real)
    ctx = DataContext(user_id=user_id, demo=demo, advanced=advanced)
    incomes = ctx.income()
    total_income = ctx.total_income()
    total_expenses = ctx.total_expenses()
    expenses_by_category = ctx.expenses_by_category()
    category_totals = ctx.category_totals()
    account_totals = ctx.account_totals()
    yearly_overview = ctx.yearly_overview()

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
