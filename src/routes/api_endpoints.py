"""Public API endpoints for Family Budget."""

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from .. import database as db
from ..helpers import (
    check_auth,
    get_user_id,
    is_demo_advanced,
    is_demo_mode,
)

router = APIRouter(prefix="/budget")


@router.get("/api/stats")
async def api_stats():
    """Public stats endpoint for uptime dashboard."""
    user_count = db.get_user_count()
    return {"users": user_count}


@router.get("/api/chart-data")
async def chart_data(request: Request):
    """API endpoint for chart visualizations.

    Returns JSON with category_totals, total_income, total_expenses, top_expenses.
    All amounts are monthly equivalents.
    """
    if not check_auth(request):
        return RedirectResponse(url="/budget/login", status_code=303)

    demo = is_demo_mode(request)
    advanced = is_demo_advanced(request)
    user_id = get_user_id(request)

    # Get data based on mode
    if demo:
        category_totals = db.get_demo_category_totals(advanced)
        total_income = db.get_demo_total_income(advanced)
        total_expenses = db.get_demo_total_expenses(advanced)
        expenses = db.get_demo_expenses(advanced)
    else:
        category_totals = db.get_category_totals(user_id)
        total_income = db.get_total_income(user_id)
        total_expenses = db.get_total_monthly_expenses(user_id)
        expenses = db.get_all_expenses(user_id)

    # Get top 5 expenses by monthly amount
    sorted_expenses = sorted(expenses, key=lambda e: e.monthly_amount, reverse=True)
    top_expenses = [
        {
            "name": exp.name,
            "amount": exp.monthly_amount,
            "category": exp.category
        }
        for exp in sorted_expenses[:5]
    ]

    # Group small categories as "Andet (samlet)" if more than 6 categories
    if len(category_totals) > 6:
        sorted_cats = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
        top_cats = dict(sorted_cats[:6])
        other_total = sum(amount for _, amount in sorted_cats[6:])
        if other_total > 0:
            top_cats["Andet (samlet)"] = other_total
        category_totals = top_cats

    return {
        "category_totals": category_totals,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "top_expenses": top_expenses
    }
