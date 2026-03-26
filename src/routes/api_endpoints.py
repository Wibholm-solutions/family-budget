"""Public API endpoints for Family Budget."""

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from .. import database as db
from ..db.facade import DataContext
from ..dependencies import get_data

router = APIRouter(prefix="/budget")

DANISH_MONTHS = {
    1: "januar", 2: "februar", 3: "marts", 4: "april",
    5: "maj", 6: "juni", 7: "juli", 8: "august",
    9: "september", 10: "oktober", 11: "november", 12: "december",
}


@router.get("/health")
async def health():
    """Lightweight health check with DB connectivity verification."""
    try:
        with db.get_connection() as conn:
            conn.execute("SELECT 1")
        return {"status": "ok", "database": "ok"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "database": "error", "detail": str(e)},
        )


@router.get("/api/stats")
async def api_stats():
    """Public stats endpoint for uptime dashboard."""
    user_count = db.get_user_count()
    return {"users": user_count}


@router.get("/api/chart-data")
async def chart_data(request: Request, ctx: DataContext = Depends(get_data)):
    """API endpoint for chart visualizations.

    Returns JSON with category_totals, total_income, total_expenses, top_expenses.
    All amounts are monthly equivalents.
    """
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


@router.get("/api/export-data")
async def export_data(request: Request, ctx: DataContext = Depends(get_data)):
    """API endpoint for budget export (image/CSV).

    Returns all budget data as JSON. All amounts are monthly equivalents.
    Auth required — returns only the authenticated user's data.
    """
    now = datetime.now()
    date_label = f"{DANISH_MONTHS[now.month]} {now.year}"

    total_income = ctx.total_income()
    total_expenses = ctx.total_expenses()

    # Incomes with person and monthly amount
    incomes = [
        {"person": inc.person, "amount": inc.monthly_amount, "frequency": inc.frequency}
        for inc in ctx.income()
    ]

    # Category totals with icons
    categories = {cat.name: cat.icon for cat in ctx.categories()}
    raw_totals = ctx.category_totals()
    category_totals = {
        name: {"total": total, "icon": categories.get(name, "tag")}
        for name, total in raw_totals.items()
    }

    # Expenses by category with individual items
    expenses_by_cat = ctx.expenses_by_category()
    expenses_by_category = {
        cat_name: [
            {"name": exp.name, "amount": exp.monthly_amount, "account": exp.account}
            for exp in exps
        ]
        for cat_name, exps in expenses_by_cat.items()
    }

    return {
        "date_label": date_label,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "remaining": round(total_income - total_expenses, 2),
        "incomes": incomes,
        "category_totals": category_totals,
        "expenses_by_category": expenses_by_category,
    }
