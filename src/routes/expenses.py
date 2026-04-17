"""Expense routes for Family Budget."""

import logging
import sqlite3

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import database as db
from ..db.facade import DataContext
from ..dependencies import get_data, require_write
from ..helpers import (
    get_user_id,
    templates,
)
from ..validators import (
    MONTHS_REQUIRED,  # noqa: F401
    VALID_FREQUENCIES,  # noqa: F401
    validate_expense,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/budget")

def validate_expense_input(
    amount_str: str,
    frequency: str,
    months_str: str | None,
) -> tuple[float, list[int] | None]:
    """Shim: delegates to validate_expense() for backward compatibility."""
    result = validate_expense(None, amount_str, frequency, months_str, None)
    non_name_errors = [e for e in result.errors if "navn" not in e.lower()]
    if non_name_errors:
        raise HTTPException(status_code=400, detail=non_name_errors[0])
    return result.parsed["amount"], result.parsed["months"]


@router.get("/expenses", response_class=HTMLResponse)
async def expenses_page(request: Request, ctx: DataContext = Depends(get_data)):
    """Expenses management page."""
    expenses = ctx.expenses()
    expenses_by_category = ctx.expenses_by_category()
    category_totals = ctx.category_totals()
    categories = ctx.categories()
    category_usage = ctx.category_usage()
    accounts = ctx.accounts()

    return templates.TemplateResponse(request,
        "expenses.html",
        {
            "expenses": expenses,
            "expenses_by_category": expenses_by_category,
            "category_totals": category_totals,
            "categories": categories,
            "category_usage": category_usage,
            "accounts": accounts,
            "demo_mode": ctx.demo,
            "demo_advanced": ctx.advanced,
        }
    )


@router.post("/expenses/add")
async def add_expense(  # noqa: PLR0913
    request: Request,
    name: str = Form(...),
    category: str = Form(...),
    amount: str = Form(...),
    frequency: str = Form(...),
    account: str = Form(""),
    months: str = Form(""),
    _: None = Depends(require_write("/budget/expenses")),
):
    """Add a new expense."""
    amount_float, months_list = validate_expense_input(amount, frequency, months)

    user_id = get_user_id(request)
    account_value = account if account else None
    try:
        db.add_expense(user_id, name, category, amount_float, frequency, account_value, months=months_list)
    except sqlite3.Error as e:
        logger.error(f"Database error adding expense: {e}")
        raise HTTPException(status_code=500, detail="Der opstod en fejl ved tilfoejelse af udgiften") from e
    return RedirectResponse(url="/budget/expenses", status_code=303)


@router.post("/expenses/{expense_id}/delete")
async def delete_expense(request: Request, expense_id: int, _: None = Depends(require_write("/budget/expenses"))):
    """Delete an expense."""
    user_id = get_user_id(request)
    try:
        db.delete_expense(expense_id, user_id)
    except sqlite3.Error as e:
        logger.error(f"Database error deleting expense: {e}")
        raise HTTPException(status_code=500, detail="Der opstod en fejl ved sletning af udgiften") from e
    return RedirectResponse(url="/budget/expenses", status_code=303)


@router.post("/expenses/{expense_id}/edit")
async def edit_expense(  # noqa: PLR0913
    request: Request,
    expense_id: int,
    name: str = Form(...),
    category: str = Form(...),
    amount: str = Form(...),
    frequency: str = Form(...),
    account: str = Form(""),
    months: str = Form(""),
    _: None = Depends(require_write("/budget/expenses")),
):
    """Edit an expense."""
    amount_float, months_list = validate_expense_input(amount, frequency, months)

    user_id = get_user_id(request)
    account_value = account if account else None
    try:
        db.update_expense(expense_id, user_id, name, category, amount_float, frequency, account_value, months=months_list)
    except sqlite3.Error as e:
        logger.error(f"Database error updating expense: {e}")
        raise HTTPException(status_code=500, detail="Der opstod en fejl ved opdatering af udgiften") from e
    return RedirectResponse(url="/budget/expenses", status_code=303)
