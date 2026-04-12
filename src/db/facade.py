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
from .split_store import (
    AccountTransfer,
    PersonTransfer,
    TransferPlan,
    get_income_by_person,
    get_split_percentages,
    get_transfer_plan,
    is_split_enabled,
)
from .budget_store import (
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

    @property
    def writable(self) -> bool:
        """True when mutations are allowed (non-demo mode)."""
        return not self.demo

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

    def split_enabled(self) -> bool:
        if self.demo:
            return self.advanced  # Demo advanced has split enabled
        return is_split_enabled(self.user_id)

    def split_percentages(self) -> dict[str, float]:
        if self.demo:
            if not self.advanced:
                return {}
            # Demo: calculate from demo income
            income = self.income()
            totals: dict[str, float] = {}
            for inc in income:
                if inc.person not in totals:
                    totals[inc.person] = 0.0
                totals[inc.person] += inc.monthly_amount
            total = sum(totals.values())
            if total == 0:
                return {}
            return {p: round((v / total) * 100, 1) for p, v in totals.items()}
        return get_split_percentages(self.user_id)

    def transfer_plan(self) -> TransferPlan | None:
        if not self.split_enabled():
            return None
        if self.demo:
            # Demo mode: calculate plan from demo data
            percentages = self.split_percentages()
            if not percentages:
                return None
            account_totals = self.account_totals()
            income_by_person: dict[str, float] = {}
            for inc in self.income():
                if inc.person not in income_by_person:
                    income_by_person[inc.person] = 0.0
                income_by_person[inc.person] += inc.monthly_amount

            largest_payer = max(percentages, key=lambda p: percentages[p])
            person_data: dict[str, list[AccountTransfer]] = {p: [] for p in percentages}

            for account, total in account_totals.items():
                rounded = {}
                for person, pct in percentages.items():
                    rounded[person] = int(total * (pct / 100.0))
                remainder = int(round(total)) - sum(rounded.values())
                rounded[largest_payer] += remainder
                for person, amount in rounded.items():
                    person_data[person].append(AccountTransfer(account=account, amount=amount))

            persons = []
            for person in percentages:
                transfers = person_data[person]
                total_transfer = sum(t.amount for t in transfers)
                available = int(round(income_by_person.get(person, 0))) - total_transfer
                persons.append(PersonTransfer(
                    person=person, transfers=transfers,
                    total_transfer=total_transfer, available=available,
                ))

            expenses = self.expenses()
            unassigned = [e.name for e in expenses if not e.account]
            return TransferPlan(persons=persons, unassigned_expenses=unassigned[:5], unassigned_count=len(unassigned))

        return get_transfer_plan(self.user_id)

    def account_usage(self) -> dict[str, int]:
        """Get usage count per account. Returns all zeros in demo mode."""
        accounts = self.accounts()
        if self.demo:
            return {acc.name: 0 for acc in accounts}
        return {acc.name: get_account_usage_count(acc.name, self.user_id) for acc in accounts}
