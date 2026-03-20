"""DataContext facade — demo-transparent data access.

Construct once per request, call methods without demo branching.
Routes never see the if-demo-else-real pattern.
"""

from .demo import (
    get_demo_account_totals,
    get_demo_accounts,
    get_demo_category_totals,
    get_demo_expenses,
    get_demo_expenses_by_category,
    get_demo_income,
    get_demo_total_expenses,
    get_demo_total_income,
    get_yearly_overview_demo,
)
from .models import Account, Category, Expense, Income
from .store import (
    get_account_totals,
    get_account_usage_count,
    get_all_accounts,
    get_all_categories,
    get_all_expenses,
    get_all_income,
    get_category_totals,
    get_category_usage_count,
    get_expenses_by_category,
    get_total_income,
    get_total_monthly_expenses,
    get_yearly_overview,
)


class DataContext:
    """Demo-transparent data access.

    Construct once per request with user_id, demo flag, and optional advanced flag.
    All methods dispatch to real DB or demo data based on the demo flag.
    """

    def __init__(self, user_id: int, demo: bool, advanced: bool = False):
        self.user_id = user_id
        self.demo = demo
        self.advanced = advanced

    def expenses(self) -> list[Expense]:
        if self.demo:
            return get_demo_expenses(self.advanced)
        return get_all_expenses(self.user_id)

    def income(self) -> list[Income]:
        if self.demo:
            return get_demo_income(self.advanced)
        return get_all_income(self.user_id)

    def categories(self) -> list[Category]:
        effective_user_id = 0 if self.demo else self.user_id
        return get_all_categories(effective_user_id)

    def accounts(self) -> list[Account]:
        if self.demo:
            return get_demo_accounts(self.advanced)
        return get_all_accounts(self.user_id)

    def category_totals(self) -> dict[str, float]:
        if self.demo:
            return get_demo_category_totals(self.advanced)
        return get_category_totals(self.user_id)

    def account_totals(self) -> dict[str, float]:
        if self.demo:
            return get_demo_account_totals(self.advanced)
        return get_account_totals(self.user_id)

    def total_income(self) -> float:
        if self.demo:
            return get_demo_total_income(self.advanced)
        return get_total_income(self.user_id)

    def total_expenses(self) -> float:
        if self.demo:
            return get_demo_total_expenses(self.advanced)
        return get_total_monthly_expenses(self.user_id)

    def yearly_overview(self) -> dict:
        if self.demo:
            return get_yearly_overview_demo(self.advanced)
        return get_yearly_overview(self.user_id)

    def expenses_by_category(self) -> dict[str, list[Expense]]:
        if self.demo:
            return get_demo_expenses_by_category(self.advanced)
        return get_expenses_by_category(self.user_id)

    def category_usage(self) -> dict[str, int]:
        """Get usage count per category. Returns all zeros in demo mode."""
        cats = self.categories()
        if self.demo:
            return {cat.name: 0 for cat in cats}
        return {cat.name: get_category_usage_count(cat.name, self.user_id) for cat in cats}

    def account_usage(self) -> dict[str, int]:
        """Get usage count per account. Returns all zeros in demo mode."""
        accounts = self.accounts()
        if self.demo:
            return {acc.name: 0 for acc in accounts}
        return {acc.name: get_account_usage_count(acc.name, self.user_id) for acc in accounts}
