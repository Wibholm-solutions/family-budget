"""Income routes for Family Budget."""

import logging
import sqlite3

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import database as db
from ..helpers import (
    check_auth,
    get_user_id,
    is_demo_advanced,
    is_demo_mode,
    parse_danish_amount,
    templates,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/budget")


@router.get("/income", response_class=HTMLResponse)
async def income_page(request: Request):
    """Income edit page."""
    if not check_auth(request):
        return RedirectResponse(url="/budget/login", status_code=303)

    demo = is_demo_mode(request)
    advanced = is_demo_advanced(request)
    user_id = get_user_id(request)

    if demo:
        incomes = db.get_demo_income(advanced)
    else:
        incomes = db.get_all_income(user_id)

    return templates.TemplateResponse(
        "income.html",
        {"request": request, "incomes": incomes, "demo_mode": demo, "demo_advanced": advanced}
    )


@router.post("/income")
async def update_income(request: Request):
    """Update income values - handles dynamic number of income sources."""
    if not check_auth(request):
        return RedirectResponse(url="/budget/login", status_code=303)
    if is_demo_mode(request):
        return RedirectResponse(url="/budget/", status_code=303)

    user_id = get_user_id(request)
    form = await request.form()

    try:
        # Parse dynamic form fields: income_name_0, income_amount_0, income_frequency_0, etc.
        incomes_to_save = []
        i = 0
        while f"income_name_{i}" in form:
            name = form.get(f"income_name_{i}", "").strip()
            amount_str = form.get(f"income_amount_{i}", "0")
            frequency = form.get(f"income_frequency_{i}", "monthly")
            if name:  # Only save if name is provided
                try:
                    amount = parse_danish_amount(amount_str) if amount_str else 0.00
                except ValueError:
                    raise HTTPException(status_code=400, detail=f"Ugyldigt beløb format for {name}") from None
                # Validate frequency
                if frequency not in ('monthly', 'quarterly', 'semi-annual', 'yearly'):
                    frequency = 'monthly'
                incomes_to_save.append((name, amount, frequency))
            i += 1

        # Clear existing and save new
        db.delete_all_income(user_id)
        for name, amount, frequency in incomes_to_save:
            db.add_income(user_id, name, amount, frequency)

    except (ValueError, sqlite3.Error) as e:
        logger.error(f"Error updating income: {e}")
        raise HTTPException(status_code=500, detail="Der opstod en fejl ved opdatering af indkomst") from e

    return RedirectResponse(url="/budget/", status_code=303)
