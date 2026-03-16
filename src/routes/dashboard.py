"""Dashboard route for Family Budget."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from .. import database as db
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
