"""Backward-compatibility re-export shim.

All functions have moved to budget_store.py, identity_store.py, and operations.py.
This module re-exports everything so existing imports continue working.
"""

from .budget_store import *  # noqa: F403
from .identity_store import *  # noqa: F403
from .operations import *  # noqa: F403

# Backward-compat aliases for renamed cross-domain operations
from .operations import create_user_with_default_categories as create_user  # noqa: F401
from .operations import (
    delete_account_if_unused as _delete_account_if_unused,
)
from .operations import (
    delete_category_if_unused as _delete_category_if_unused,
)
from .operations import (
    rename_account_and_cascade_expenses as update_account,  # noqa: F401
)
from .operations import (
    rename_category_and_cascade_expenses as _rename_cat,
)


def update_category(category_id: int, user_id: int, name: str, icon: str) -> int:
    """Backward-compat wrapper: returns int instead of CategoryUpdateResult."""
    return _rename_cat(category_id, user_id, name, icon).cascaded_expense_count


def delete_category(category_id: int, user_id: int) -> bool:
    """Backward-compat wrapper: returns bool instead of DeleteResult."""
    return _delete_category_if_unused(category_id, user_id).deleted


def delete_account(account_id: int, user_id: int) -> bool:
    """Backward-compat wrapper: returns bool instead of DeleteResult."""
    return _delete_account_if_unused(account_id, user_id).deleted
