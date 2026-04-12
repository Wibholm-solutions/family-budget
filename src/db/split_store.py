"""Income split CRUD and transfer plan calculation.

Handles the income distribution feature: split percentages,
overrides, and transfer plan generation.
"""

from dataclasses import dataclass

from .budget_store import get_account_totals, get_all_income
from .connection import get_connection


@dataclass
class AccountTransfer:
    account: str
    amount: int  # whole kroner


@dataclass
class PersonTransfer:
    person: str
    transfers: list[AccountTransfer]
    total_transfer: int
    available: int  # income minus total transfers


@dataclass
class TransferPlan:
    persons: list[PersonTransfer]
    unassigned_expenses: list[str]
    unassigned_count: int


def is_split_enabled(user_id: int) -> bool:
    """Check if income split is enabled for a user."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT income_split_enabled FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
    return bool(row and row[0])


def set_split_enabled(user_id: int, enabled: bool) -> None:
    """Enable or disable income split for a user."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET income_split_enabled = ? WHERE id = ?",
            (1 if enabled else 0, user_id)
        )
        conn.commit()


def get_split_overrides(user_id: int) -> dict[str, float | None]:
    """Get split percentage overrides for a user."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT person, percentage_override FROM income_split WHERE user_id = ?",
            (user_id,)
        )
        rows = cur.fetchall()
    return {row[0]: row[1] for row in rows}


def set_split_override(user_id: int, person: str, percentage: float | None) -> None:
    """Set or clear a split percentage override for a person."""
    with get_connection() as conn:
        cur = conn.cursor()
        if percentage is None:
            cur.execute(
                "DELETE FROM income_split WHERE user_id = ? AND person = ?",
                (user_id, person)
            )
        else:
            cur.execute(
                """INSERT INTO income_split (user_id, person, percentage_override)
                   VALUES (?, ?, ?)
                   ON CONFLICT(user_id, person) DO UPDATE SET percentage_override = excluded.percentage_override""",
                (user_id, person, percentage)
            )
        conn.commit()


def clear_split_overrides(user_id: int) -> None:
    """Remove all split overrides for a user."""
    with get_connection() as conn:
        conn.execute("DELETE FROM income_split WHERE user_id = ?", (user_id,))
        conn.commit()


def get_income_by_person(user_id: int) -> dict[str, float]:
    """Get total monthly income grouped by person."""
    incomes = get_all_income(user_id)
    totals: dict[str, float] = {}
    for inc in incomes:
        if inc.person not in totals:
            totals[inc.person] = 0.0
        totals[inc.person] += inc.monthly_amount
    return totals


def get_split_percentages(user_id: int) -> dict[str, float]:
    """Get split percentages per person.

    Uses overrides if set, otherwise calculates proportionally from income.
    """
    income_by_person = get_income_by_person(user_id)
    if not income_by_person:
        return {}

    overrides = get_split_overrides(user_id)
    total_income = sum(income_by_person.values())

    if total_income == 0:
        return {}

    # If all persons have overrides, use them
    all_overridden = all(
        person in overrides and overrides[person] is not None
        for person in income_by_person
    )
    if all_overridden:
        return {person: overrides[person] for person in income_by_person}

    # Calculate proportionally
    result = {}
    for person, income in income_by_person.items():
        if person in overrides and overrides[person] is not None:
            result[person] = overrides[person]
        else:
            result[person] = round((income / total_income) * 100, 1)

    # Ensure percentages sum to 100 by adjusting last non-overridden person
    total_pct = sum(result.values())
    if abs(total_pct - 100.0) > 0.01:
        non_overridden = [p for p in income_by_person if p not in overrides or overrides[p] is None]
        if non_overridden:
            last = non_overridden[-1]
            result[last] = round(result[last] + (100.0 - total_pct), 1)

    return result


def get_unassigned_expenses(user_id: int, limit: int = 5) -> tuple[list[str], int]:
    """Get names of expenses without an account assignment.

    Returns (first N names, total count).
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ? AND (account IS NULL OR account = '')",
            (user_id,)
        )
        count = cur.fetchone()[0]

        cur.execute(
            "SELECT name FROM expenses WHERE user_id = ? AND (account IS NULL OR account = '') ORDER BY name LIMIT ?",
            (user_id, limit)
        )
        names = [row[0] for row in cur.fetchall()]
    return names, count


def get_transfer_plan(user_id: int) -> TransferPlan:
    """Calculate the full transfer plan for a user.

    Returns per-person, per-account transfer amounts in whole kroner,
    with rounding remainder assigned to the largest payer.
    """
    percentages = get_split_percentages(user_id)
    if not percentages:
        return TransferPlan(persons=[], unassigned_expenses=[], unassigned_count=0)

    account_totals = get_account_totals(user_id)
    income_by_person = get_income_by_person(user_id)
    unassigned_names, unassigned_count = get_unassigned_expenses(user_id)

    # Find person with highest percentage (largest payer)
    largest_payer = max(percentages, key=lambda p: percentages[p])

    person_data: dict[str, list[AccountTransfer]] = {p: [] for p in percentages}

    for account, total in account_totals.items():
        # Calculate each person's share
        raw_shares = {}
        for person, pct in percentages.items():
            raw_shares[person] = total * (pct / 100.0)

        # Round to whole kroner
        rounded = {person: int(amount) for person, amount in raw_shares.items()}
        remainder = int(round(total)) - sum(rounded.values())

        # Assign remainder to largest payer
        rounded[largest_payer] += remainder

        for person, amount in rounded.items():
            person_data[person].append(AccountTransfer(account=account, amount=amount))

    # Build PersonTransfer objects
    persons = []
    for person in percentages:
        transfers = person_data[person]
        total_transfer = sum(t.amount for t in transfers)
        person_income = int(round(income_by_person.get(person, 0)))
        available = person_income - total_transfer
        persons.append(PersonTransfer(
            person=person,
            transfers=transfers,
            total_transfer=total_transfer,
            available=available,
        ))

    return TransferPlan(
        persons=persons,
        unassigned_expenses=unassigned_names,
        unassigned_count=unassigned_count,
    )
