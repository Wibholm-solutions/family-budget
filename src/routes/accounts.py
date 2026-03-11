"""Account routes for Family Budget."""

import logging
import sqlite3

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .. import database as db
from ..helpers import (
    check_auth,
    get_user_id,
    is_demo_advanced,
    is_demo_mode,
    templates,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/budget")


@router.get("/accounts", response_class=HTMLResponse)
async def accounts_page(request: Request):
    """Accounts management page."""
    if not check_auth(request):
        return RedirectResponse(url="/budget/login", status_code=303)

    user_id = get_user_id(request)
    demo = is_demo_mode(request)

    effective_user_id = 0 if demo else user_id
    accounts = db.get_all_accounts(effective_user_id)

    if demo:
        account_usage = {acc.name: 0 for acc in accounts}
    else:
        account_usage = {acc.name: db.get_account_usage_count(acc.name, user_id) for acc in accounts}

    return templates.TemplateResponse(
        "accounts.html",
        {
            "request": request,
            "accounts": accounts,
            "account_usage": account_usage,
            "demo_mode": demo,
            "demo_advanced": is_demo_advanced(request),
        }
    )


@router.post("/accounts/add")
async def add_account(
    request: Request,
    name: str = Form(...)
):
    """Add a new account."""
    if not check_auth(request):
        return RedirectResponse(url="/budget/login", status_code=303)
    if is_demo_mode(request):
        return RedirectResponse(url="/budget/accounts", status_code=303)

    user_id = get_user_id(request)
    try:
        db.add_account(user_id, name)
    except sqlite3.IntegrityError:
        raise HTTPException(  # noqa: B904
            status_code=400,
            detail=f"Kontoen '{name}' findes allerede"
        )
    return RedirectResponse(url="/budget/accounts", status_code=303)


@router.post("/accounts/add-json")
async def add_account_json(request: Request, name: str = Form(...)):  # noqa: PLR0911
    """Add a new account and return JSON (for inline creation from expense form)."""
    if not check_auth(request):
        return JSONResponse({"success": False, "error": "Ikke logget ind"}, status_code=401)
    if is_demo_mode(request):
        return JSONResponse({"success": False, "error": "Ikke tilgængelig i demo"}, status_code=403)

    user_id = get_user_id(request)
    name = name.strip()
    if not name:
        return JSONResponse({"success": False, "error": "Navn er påkrævet"}, status_code=400)

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
    name: str = Form(...)
):
    """Edit an account."""
    if not check_auth(request):
        return RedirectResponse(url="/budget/login", status_code=303)
    if is_demo_mode(request):
        return RedirectResponse(url="/budget/accounts", status_code=303)

    user_id = get_user_id(request)
    try:
        updated_count = db.update_account(account_id, user_id, name)
    except sqlite3.IntegrityError:
        raise HTTPException(  # noqa: B904
            status_code=400,
            detail=f"Kontoen '{name}' findes allerede"
        )
    url = "/budget/accounts"
    if updated_count > 0:
        url += f"?updated={updated_count}"
    return RedirectResponse(url=url, status_code=303)


@router.post("/accounts/{account_id}/delete")
async def delete_account(request: Request, account_id: int):
    """Delete an account for the current user."""
    if not check_auth(request):
        return RedirectResponse(url="/budget/login", status_code=303)
    if is_demo_mode(request):
        return RedirectResponse(url="/budget/accounts", status_code=303)

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
        raise HTTPException(status_code=500, detail="Der opstod en fejl ved sletning af kontoen")  # noqa: B904
    return RedirectResponse(url="/budget/accounts", status_code=303)
