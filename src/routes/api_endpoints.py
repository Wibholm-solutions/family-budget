"""Public API endpoints for Family Budget."""

from fastapi import APIRouter, Depends, Request

from .. import database as db
from ..db.facade import DataContext
from ..dependencies import require_auth
from ..helpers import (
    get_user_id,
    is_demo_advanced,
    is_demo_mode,
)

router = APIRouter(prefix="/budget")


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/api/stats")
async def api_stats():
    """Public stats endpoint for uptime dashboard."""
    user_count = db.get_user_count()
    return {"users": user_count}


@router.get("/api/chart-data")
async def chart_data(request: Request, _: None = Depends(require_auth)):
    """API endpoint for chart visualizations.

    Returns JSON with category_totals, total_income, total_expenses, top_expenses.
    All amounts are monthly equivalents.
    """
    demo = is_demo_mode(request)
    advanced = is_demo_advanced(request)
    user_id = get_user_id(request)

    # Get data based on mode
    ctx = DataContext(user_id=user_id, demo=demo, advanced=advanced)
    category_totals = ctx.category_totals()
    total_income = ctx.total_income()
    total_expenses = ctx.total_expenses()
    expenses = ctx.expenses()

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
