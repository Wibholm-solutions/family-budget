"""FastAPI dependencies for authentication and write guards.

Usage:
    from ..dependencies import require_auth, require_write

    @router.get("/mypage")
    async def my_page(request: Request, _: None = Depends(require_auth)):
        ...

    @router.post("/mypage/add")
    async def add_item(request: Request, _: None = Depends(require_write("/mypage"))):
        ...
"""

from fastapi import Request

from .helpers import check_auth, is_demo_mode


class AuthRequired(Exception):
    """Raised by require_auth when the request has no valid session."""


class DemoBlocked(Exception):
    """Raised by require_write when a demo user attempts a write operation.

    Attributes:
        redirect_to: URL to redirect the demo user to.
    """

    def __init__(self, redirect_to: str = "/budget/") -> None:
        self.redirect_to = redirect_to


async def require_auth(request: Request) -> None:
    """Dependency: raise AuthRequired if the request is not authenticated.

    FastAPI will catch AuthRequired via the exception handler registered in
    api.py and return a 303 redirect to /budget/login.

    Example:
        @router.get("/dashboard")
        async def dashboard(request: Request, _: None = Depends(require_auth)):
            ...
    """
    if not check_auth(request):
        raise AuthRequired()


def require_write(redirect_to: str):
    """Dependency factory: require auth and block demo mode for write routes.

    Checks authentication first, then blocks demo users and redirects them
    to redirect_to.

    Args:
        redirect_to: URL to redirect demo users to (usually the resource list page).

    Returns:
        An async dependency callable suitable for use with Depends().

    Example:
        @router.post("/expenses/add")
        async def add_expense(request: Request, _: None = Depends(require_write("/budget/expenses"))):
            ...
    """
    async def _dep(request: Request) -> None:
        if not check_auth(request):
            raise AuthRequired()
        if is_demo_mode(request):
            raise DemoBlocked(redirect_to)

    return _dep
