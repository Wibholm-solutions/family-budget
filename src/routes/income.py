"""Income routes for Family Budget."""

import logging
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import database as db
from ..db.facade import DataContext
from ..dependencies import get_data, require_write
from ..helpers import (
    get_user_id,
    templates,
)
from ..validators import validate_income

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/budget")


@router.get("/income", response_class=HTMLResponse)
async def income_page(request: Request, ctx: DataContext = Depends(get_data)):
    """Income edit page."""
    incomes = ctx.income()
    split_enabled = ctx.split_enabled()
    split_percentages = ctx.split_percentages()

    # Get unique persons for split display
    persons = list(dict.fromkeys(inc.person for inc in incomes))

    return templates.TemplateResponse(
        "income.html",
        {
            "request": request,
            "incomes": incomes,
            "demo_mode": ctx.demo,
            "demo_advanced": ctx.advanced,
            "split_enabled": split_enabled,
            "split_percentages": split_percentages,
            "persons": persons,
        }
    )


@router.post("/income")
async def update_income(request: Request, _: None = Depends(require_write("/budget/"))):
    """Update income values - handles dynamic number of income sources."""
    user_id = get_user_id(request)
    form = await request.form()

    try:
        # Handle split toggle
        split_enabled = form.get("split_enabled") == "on"
        db.set_split_enabled(user_id, split_enabled)

        # Parse dynamic form fields
        incomes_to_save = []
        i = 0
        while f"income_name_{i}" in form:
            name = form.get(f"income_name_{i}", "").strip()
            source = form.get(f"income_source_{i}", "Løn").strip() or "Løn"
            amount_str = form.get(f"income_amount_{i}", "0")
            frequency = form.get(f"income_frequency_{i}", "monthly")
            if name:
                result = validate_income(name, amount_str if amount_str else "0", frequency)
                result.raise_if_invalid()
                incomes_to_save.append((result.parsed["name"], source, result.parsed["amount"], result.parsed["frequency"]))
            i += 1

        # Clear existing and save new
        db.delete_all_income(user_id)
        for name, source, amount, frequency in incomes_to_save:
            db.add_income(user_id, name, amount, frequency, source)

        # Handle split overrides if enabled
        if split_enabled:
            persons = list(dict.fromkeys(name for name, _, _, _ in incomes_to_save))
            db.clear_split_overrides(user_id)
            has_overrides = False
            for person in persons:
                override_str = form.get(f"split_pct_{person}")
                if override_str:
                    try:
                        pct = float(override_str.replace(",", "."))
                        db.set_split_override(user_id, person, pct)
                        has_overrides = True
                    except ValueError:
                        pass
            if not has_overrides:
                db.clear_split_overrides(user_id)

    except (ValueError, sqlite3.Error) as e:
        logger.error(f"Error updating income: {e}")
        raise HTTPException(status_code=500, detail="Der opstod en fejl ved opdatering af indkomst") from e

    return RedirectResponse(url="/budget/", status_code=303)
