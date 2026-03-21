"""Demo data and demo-specific query functions.

Hardcoded data for demo mode. Reuses _calculate_yearly_overview from store.
"""

from .models import Account, Expense, Income
from .budget_store import _calculate_yearly_overview

# Demo data - typical Danish household budget
DEMO_INCOME = [
    # (person, amount, frequency, months)
    ("Person 1", 28000, "monthly", None),
    ("Person 2", 22000, "monthly", None),
    ("Bonus", 30000, "semi-annual", [6, 12]),
]

DEMO_EXPENSES = [
    # (name, category, amount, frequency, months)
    ("Husleje/boliglån", "Bolig", 12000, "monthly", None),
    ("Ejendomsskat", "Bolig", 18000, "yearly", [1, 7]),
    ("Varme", "Forbrug", 800, "monthly", None),
    ("El", "Forbrug", 600, "monthly", None),
    ("Vand", "Forbrug", 2400, "quarterly", [3, 6, 9, 12]),
    ("Internet", "Forbrug", 299, "monthly", None),
    ("Bil - lån", "Transport", 2500, "monthly", None),
    ("Benzin", "Transport", 1500, "monthly", None),
    ("Vægtafgift", "Transport", 3600, "yearly", [4]),
    ("Bilforsikring", "Transport", 6000, "yearly", [2]),
    ("Bilservice", "Transport", 4500, "semi-annual", [3, 9]),
    ("Institution", "Børn", 3200, "monthly", None),
    ("Fritidsaktiviteter", "Børn", 2400, "semi-annual", [1, 8]),
    ("Dagligvarer", "Mad", 6000, "monthly", None),
    ("Indboforsikring", "Forsikring", 1800, "yearly", [6]),
    ("Ulykkesforsikring", "Forsikring", 1200, "yearly", [6]),
    ("Tandlægeforsikring", "Forsikring", 600, "quarterly", [3, 6, 9, 12]),
    ("Netflix", "Abonnementer", 129, "monthly", None),
    ("Spotify", "Abonnementer", 99, "monthly", None),
    ("Fitness", "Abonnementer", 299, "monthly", None),
    ("Opsparing", "Opsparing", 3000, "monthly", None),
    ("Telefon", "Andet", 199, "monthly", None),
]

DEMO_INCOME_ADVANCED = [
    ("Person 1", 28000, "monthly", None),
    ("Person 2", 22000, "monthly", None),
    ("Bonus", 30000, "semi-annual", [6, 12]),
    ("Børnepenge", 6264, "quarterly", [1, 4, 7, 10]),
]

DEMO_EXPENSES_ADVANCED = [
    # (name, category, amount, frequency, account, months)
    ("Husleje/boliglån", "Bolig", 12000, "monthly", "Budgetkonto", None),
    ("Ejendomsskat", "Bolig", 18000, "yearly", "Budgetkonto", [1, 7]),
    ("Varme", "Forbrug", 800, "monthly", "Budgetkonto", None),
    ("El", "Forbrug", 600, "monthly", "Budgetkonto", None),
    ("Vand", "Forbrug", 2400, "quarterly", "Budgetkonto", [3, 6, 9, 12]),
    ("Internet", "Forbrug", 299, "monthly", "Budgetkonto", None),
    ("Bil - lån", "Transport", 2500, "monthly", "Budgetkonto", None),
    ("Benzin", "Transport", 1500, "monthly", "Forbrugskonto", None),
    ("Vægtafgift", "Transport", 3600, "yearly", "Budgetkonto", [4]),
    ("Bilforsikring", "Transport", 6000, "yearly", "Budgetkonto", [2]),
    ("Bilservice", "Transport", 4500, "semi-annual", "Budgetkonto", [3, 9]),
    ("Institution", "Børn", 3200, "monthly", "Budgetkonto", None),
    ("Fritidsaktiviteter", "Børn", 2400, "semi-annual", "Forbrugskonto", [1, 8]),
    ("Dagligvarer", "Mad", 6000, "monthly", "Forbrugskonto", None),
    ("Indboforsikring", "Forsikring", 1800, "yearly", "Budgetkonto", [6]),
    ("Ulykkesforsikring", "Forsikring", 1200, "yearly", "Budgetkonto", [6]),
    ("Tandlægeforsikring", "Forsikring", 600, "quarterly", "Budgetkonto", [3, 6, 9, 12]),
    ("Netflix", "Abonnementer", 129, "monthly", "Person 1 konto", None),
    ("Spotify", "Abonnementer", 99, "monthly", "Person 2 konto", None),
    ("Fitness", "Abonnementer", 299, "monthly", "Person 1 konto", None),
    ("Opsparing", "Opsparing", 3000, "monthly", "Opsparingskonto", None),
    ("Telefon", "Andet", 199, "monthly", "Person 2 konto", None),
]


def get_demo_income(advanced: bool = False) -> list[Income]:
    source = DEMO_INCOME_ADVANCED if advanced else DEMO_INCOME
    return [Income(id=i+1, user_id=0, person=person, amount=amount, frequency=freq, months=months)
            for i, (person, amount, freq, months) in enumerate(source)]


def get_demo_total_income(advanced: bool = False) -> float:
    return sum(inc.monthly_amount for inc in get_demo_income(advanced))


def get_demo_expenses(advanced: bool = False) -> list[Expense]:
    if advanced:
        return [Expense(id=i+1, user_id=0, name=name, category=cat, amount=amount, frequency=freq, account=acct, months=months)
                for i, (name, cat, amount, freq, acct, months) in enumerate(DEMO_EXPENSES_ADVANCED)]
    return [Expense(id=i+1, user_id=0, name=name, category=cat, amount=amount, frequency=freq, account=None, months=months)
            for i, (name, cat, amount, freq, months) in enumerate(DEMO_EXPENSES)]


def get_demo_expenses_by_category(advanced: bool = False) -> dict[str, list[Expense]]:
    expenses = get_demo_expenses(advanced)
    grouped = {}
    for exp in expenses:
        if exp.category not in grouped:
            grouped[exp.category] = []
        grouped[exp.category].append(exp)
    return grouped


def get_demo_category_totals(advanced: bool = False) -> dict[str, float]:
    expenses = get_demo_expenses(advanced)
    totals = {}
    for exp in expenses:
        if exp.category not in totals:
            totals[exp.category] = 0
        totals[exp.category] += exp.monthly_amount
    return totals


def get_demo_total_expenses(advanced: bool = False) -> float:
    return sum(exp.monthly_amount for exp in get_demo_expenses(advanced))


def get_demo_account_totals(advanced: bool = False) -> dict[str, float]:
    if not advanced:
        return {}
    expenses = get_demo_expenses(advanced=True)
    totals = {}
    for exp in expenses:
        if exp.account:
            if exp.account not in totals:
                totals[exp.account] = 0
            totals[exp.account] += exp.monthly_amount
    return totals


def get_demo_accounts(advanced: bool = False) -> list[Account]:
    if not advanced:
        return []
    names = ["Budgetkonto", "Forbrugskonto", "Person 1 konto", "Person 2 konto", "Opsparingskonto"]
    return [Account(id=i+1, name=name) for i, name in enumerate(names)]


def get_yearly_overview_demo(advanced: bool = False) -> dict:
    return _calculate_yearly_overview(
        get_demo_expenses(advanced),
        get_demo_income(advanced),
    )
