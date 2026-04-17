"""Category routes for Family Budget."""

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
from ..validators import validate_category

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/budget")


@router.get("/categories", response_class=HTMLResponse)
async def categories_page(request: Request, ctx: DataContext = Depends(get_data)):
    """Categories management page."""
    categories = ctx.categories()
    category_usage = ctx.category_usage()

    return templates.TemplateResponse(request,
        "categories.html",
        {
            "categories": categories,
            "category_usage": category_usage,
            "demo_mode": ctx.demo,
            "demo_advanced": ctx.advanced,
        }
    )


@router.post("/categories/add")
async def add_category(
    request: Request,
    name: str = Form(...),
    icon: str = Form(...),
    _: None = Depends(require_write("/budget/categories")),
):
    """Add a new category."""
    validate_category(name, icon).raise_if_invalid()
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
    next: str = Form(""),
    _: None = Depends(require_write("/budget/categories")),
):
    """Edit a category."""
    validate_category(name, icon).raise_if_invalid()
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
async def delete_category(request: Request, category_id: int, _: None = Depends(require_write("/budget/categories"))):
    """Delete a category for the current user.

    Categories are per-user. Deletion is only allowed for categories owned by
    the current user, and only if the category is not in use.
    """
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
