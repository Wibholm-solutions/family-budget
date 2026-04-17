"""Account routes for Family Budget."""

import logging
import sqlite3

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .. import database as db
from ..db.facade import DataContext
from ..dependencies import get_data, require_write
from ..helpers import (
    check_auth,
    get_user_id,
    is_demo_mode,
    templates,
)
from ..validators import validate_account

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/budget")


@router.get("/accounts", response_class=HTMLResponse)
async def accounts_page(request: Request, ctx: DataContext = Depends(get_data)):
    """Accounts management page."""
    accounts = ctx.accounts()
    account_usage = ctx.account_usage()

    return templates.TemplateResponse(request,
        "accounts.html",
        {
            "accounts": accounts,
            "account_usage": account_usage,
            "demo_mode": ctx.demo,
            "demo_advanced": ctx.advanced,
        }
    )


@router.post("/accounts/add")
async def add_account(
    request: Request,
    name: str = Form(...),
    _: None = Depends(require_write("/budget/accounts")),
):
    """Add a new account."""
    validate_account(name).raise_if_invalid()
    user_id = get_user_id(request)
    try:
        db.add_account(user_id, name)
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=400,
            detail=f"Kontoen '{name}' findes allerede"
        ) from None
    return RedirectResponse(url="/budget/accounts", status_code=303)


@router.post("/accounts/add-json")
async def add_account_json(request: Request, name: str = Form(...)):  # noqa: PLR0911
    """Add a new account and return JSON (for inline creation from expense form)."""
    if not check_auth(request):
        return JSONResponse({"success": False, "error": "Ikke logget ind"}, status_code=401)
    if is_demo_mode(request):
        return JSONResponse({"success": False, "error": "Ikke tilgængelig i demo"}, status_code=403)

    user_id = get_user_id(request)
    result = validate_account(name)
    if not result.ok:
        return JSONResponse({"success": False, "error": "; ".join(result.errors)}, status_code=400)
    name = result.parsed["name"]

    try:
        db.add_account(user_id, name)
    except sqlite3.IntegrityError:
        return JSONResponse(
            {"success": False, "error": f"Kontoen '{name}' findes allerede"},
            status_code=400,
        )
    return JSONResponse({"success": True, "name": name})


@router.post("/accounts/{account_id}/edit")
async def edit_account(
    request: Request,
    account_id: int,
    name: str = Form(...),
    _: None = Depends(require_write("/budget/accounts")),
):
    """Edit an account."""
    validate_account(name).raise_if_invalid()
    user_id = get_user_id(request)
    try:
        updated_count = db.update_account(account_id, user_id, name)
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=400,
            detail=f"Kontoen '{name}' findes allerede"
        ) from None
    url = "/budget/accounts"
    if updated_count > 0:
        url += f"?updated={updated_count}"
    return RedirectResponse(url=url, status_code=303)


@router.post("/accounts/{account_id}/delete")
async def delete_account(request: Request, account_id: int, _: None = Depends(require_write("/budget/accounts"))):
    """Delete an account for the current user."""
    user_id = get_user_id(request)
    try:
        success = db.delete_account(account_id, user_id)
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Kontoen kan ikke slettes - den er stadig i brug"
            )
    except sqlite3.Error as e:
        logger.error(f"Database error deleting account: {e}")
        raise HTTPException(status_code=500, detail="Der opstod en fejl ved sletning af kontoen") from e
    return RedirectResponse(url="/budget/accounts", status_code=303)
