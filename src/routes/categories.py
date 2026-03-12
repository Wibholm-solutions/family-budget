"""Category routes for Family Budget."""

import logging
import sqlite3

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

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


@router.get("/categories", response_class=HTMLResponse)
async def categories_page(request: Request):
    """Categories management page."""
    if not check_auth(request):
        return RedirectResponse(url="/budget/login", status_code=303)

    user_id = get_user_id(request)
    demo = is_demo_mode(request)

    # Use demo user (user_id = 0) for demo mode
    effective_user_id = 0 if demo else user_id
    categories = db.get_all_categories(effective_user_id)

    # Get usage count for each category (0 for demo mode since it's read-only)
    if demo:
        category_usage = {cat.name: 0 for cat in categories}
    else:
        category_usage = {cat.name: db.get_category_usage_count(cat.name, user_id) for cat in categories}

    return templates.TemplateResponse(
        "categories.html",
        {
            "request": request,
            "categories": categories,
            "category_usage": category_usage,
            "demo_mode": demo,
            "demo_advanced": is_demo_advanced(request),
        }
    )


@router.post("/categories/add")
async def add_category(
    request: Request,
    name: str = Form(...),
    icon: str = Form(...)
):
    """Add a new category."""
    if not check_auth(request):
        return RedirectResponse(url="/budget/login", status_code=303)
    if is_demo_mode(request):
        return RedirectResponse(url="/budget/categories", status_code=303)

    user_id = get_user_id(request)
    try:
        db.add_category(user_id, name, icon)
    except sqlite3.IntegrityError:
        # Category name already exists for this user (UNIQUE constraint)
        raise HTTPException(
            status_code=400,
            detail=f"Kategorien '{name}' findes allerede"
        ) from None
    return RedirectResponse(url="/budget/categories", status_code=303)


@router.post("/categories/{category_id}/edit")
async def edit_category(
    request: Request,
    category_id: int,
    name: str = Form(...),
    icon: str = Form(...),
    next: str = Form("")
):
    """Edit a category."""
    if not check_auth(request):
        return RedirectResponse(url="/budget/login", status_code=303)
    if is_demo_mode(request):
        return RedirectResponse(url="/budget/categories", status_code=303)

    user_id = get_user_id(request)
    try:
        updated_count = db.update_category(category_id, user_id, name, icon)
    except sqlite3.IntegrityError:
        # Category name already exists for this user (UNIQUE constraint)
        raise HTTPException(
            status_code=400,
            detail=f"Kategorien '{name}' findes allerede"
        ) from None
    allowed_next = {"/budget/expenses", "/budget/categories"}
    base_url = next if next in allowed_next else "/budget/categories"
    url = base_url
    if updated_count > 0:
        url += f"?updated={updated_count}"
    return RedirectResponse(url=url, status_code=303)


@router.post("/categories/{category_id}/delete")
async def delete_category(request: Request, category_id: int):
    """Delete a category for the current user.

    Categories are per-user. Deletion is only allowed for categories owned by
    the current user, and only if the category is not in use.
    """
    if not check_auth(request):
        return RedirectResponse(url="/budget/login", status_code=303)
    if is_demo_mode(request):
        return RedirectResponse(url="/budget/categories", status_code=303)

    user_id = get_user_id(request)
    try:
        success = db.delete_category(category_id, user_id)
        if not success:
            # Category is in use, doesn't exist, or not owned by user
            raise HTTPException(
                status_code=400,
                detail="Kategorien kan ikke slettes - den er stadig i brug"
            )
    except sqlite3.Error as e:
        logger.error(f"Database error deleting category: {e}")
        raise HTTPException(status_code=500, detail="Der opstod en fejl ved sletning af kategorien") from e
    return RedirectResponse(url="/budget/categories", status_code=303)
