"""Expense routes for Family Budget."""

import logging
import sqlite3

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import database as db
from ..dependencies import require_auth, require_write
from ..helpers import (
    get_user_id,
    is_demo_advanced,
    is_demo_mode,
    parse_danish_amount,
    templates,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/budget")

VALID_FREQUENCIES = ('monthly', 'quarterly', 'semi-annual', 'yearly')

MONTHS_REQUIRED = {
    'quarterly': 4,
    'semi-annual': 2,
    'yearly': 1,
}


def parse_months(months_str: str | None, frequency: str) -> list[int] | None:
    """Parse and validate months form field.

    Returns list of month ints, or None if no months specified.
    Raises HTTPException(400) if validation fails.
    """
    if frequency == 'monthly':
        return None

    if not months_str or not months_str.strip():
        return None

    try:
        months = [int(m.strip()) for m in months_str.split(',')]
    except ValueError:
        raise HTTPException(status_code=400, detail="Ugyldige måneder") from None

    if any(m < 1 or m > 12 for m in months):
        raise HTTPException(status_code=400, detail="Måneder skal være mellem 1 og 12")

    expected = MONTHS_REQUIRED.get(frequency)
    if expected and len(months) != expected:
        raise HTTPException(status_code=400, detail=f"Vælg præcis {expected} måneder for denne frekvens")

    return sorted(months)


def validate_expense_input(
    amount_str: str,
    frequency: str,
    months_str: str | None,
) -> tuple[float, list[int] | None]:
    """Validate and parse shared expense input fields.

    Raises HTTPException(400) on any validation failure.
    Returns (amount_float, months_list).
    """
    if frequency not in VALID_FREQUENCIES:
        raise HTTPException(status_code=400, detail="Ugyldig frekvens")

    try:
        amount_float = parse_danish_amount(amount_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Ugyldigt beløb format") from None

    if amount_float < 0:
        raise HTTPException(status_code=400, detail="Beløb skal være positivt")
    if amount_float > 1000000:
        raise HTTPException(status_code=400, detail="Beløb er for stort")

    months_list = parse_months(months_str if months_str else None, frequency)

    return amount_float, months_list


@router.get("/expenses", response_class=HTMLResponse)
async def expenses_page(request: Request, _: None = Depends(require_auth)):
    """Expenses management page."""
    user_id = get_user_id(request)
    demo = is_demo_mode(request)
    advanced = is_demo_advanced(request)

    if demo:
        expenses = db.get_demo_expenses(advanced)
        expenses_by_category = db.get_demo_expenses_by_category(advanced)
        category_totals = db.get_demo_category_totals(advanced)
        # Use demo user categories (user_id = 0)
        categories = db.get_all_categories(0)
        category_usage = {cat.name: 0 for cat in categories}
        accounts = db.get_demo_accounts(advanced)
    else:
        expenses = db.get_all_expenses(user_id)
        expenses_by_category = db.get_expenses_by_category(user_id)
        category_totals = db.get_category_totals(user_id)
        categories = db.get_all_categories(user_id)
        category_usage = {cat.name: db.get_category_usage_count(cat.name, user_id) for cat in categories}
        accounts = db.get_all_accounts(user_id)

    return templates.TemplateResponse(
        "expenses.html",
        {
            "request": request,
            "expenses": expenses,
            "expenses_by_category": expenses_by_category,
            "category_totals": category_totals,
            "categories": categories,
            "category_usage": category_usage,
            "accounts": accounts,
            "demo_mode": demo,
            "demo_advanced": advanced,
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
    # Validate frequency
    if frequency not in VALID_FREQUENCIES:
        raise HTTPException(status_code=400, detail="Ugyldig frekvens")

    # Parse and validate amount
    try:
        amount_float = parse_danish_amount(amount)
    except ValueError:
        raise HTTPException(status_code=400, detail="Ugyldigt beløb format") from None

    if amount_float < 0:
        raise HTTPException(status_code=400, detail="Beløb skal være positivt")
    if amount_float > 1000000:
        raise HTTPException(status_code=400, detail="Beløb er for stort")

    months_list = parse_months(months if months else None, frequency)

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
    # Validate frequency
    if frequency not in VALID_FREQUENCIES:
        raise HTTPException(status_code=400, detail="Ugyldig frekvens")

    # Parse and validate amount
    try:
        amount_float = parse_danish_amount(amount)
    except ValueError:
        raise HTTPException(status_code=400, detail="Ugyldigt beløb format") from None

    if amount_float < 0:
        raise HTTPException(status_code=400, detail="Beløb skal være positivt")
    if amount_float > 1000000:
        raise HTTPException(status_code=400, detail="Beløb er for stort")

    months_list = parse_months(months if months else None, frequency)

    user_id = get_user_id(request)
    account_value = account if account else None
    try:
        db.update_expense(expense_id, user_id, name, category, amount_float, frequency, account_value, months=months_list)
    except sqlite3.Error as e:
        logger.error(f"Database error updating expense: {e}")
        raise HTTPException(status_code=500, detail="Der opstod en fejl ved opdatering af udgiften") from e
    return RedirectResponse(url="/budget/expenses", status_code=303)
