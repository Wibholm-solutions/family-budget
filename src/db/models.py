"""Domain models for Family Budget."""

from dataclasses import dataclass


class MonthlyMixin:
    """Shared monthly amount computation for Income and Expense."""
    amount: float
    frequency: str
    months: list[int] | None

    @property
    def monthly_amount(self) -> float:
        """Return the monthly equivalent amount with 2 decimal precision."""
        divisors = {'monthly': 1, 'quarterly': 3, 'semi-annual': 6, 'yearly': 12}
        result = self.amount / divisors.get(self.frequency, 1)
        return round(result, 2)

    def get_monthly_amounts(self) -> dict[int, float]:
        """Return a dict mapping month (1-12) to the amount for that month."""
        result = {m: 0.0 for m in range(1, 13)}
        if self.frequency == 'monthly' or self.months is None:
            monthly = self.monthly_amount
            for m in range(1, 13):
                result[m] = monthly
        else:
            per_month = round(self.amount / len(self.months), 2)
            for m in self.months:
                result[m] = per_month
        return result


@dataclass
class Income(MonthlyMixin):
    id: int
    user_id: int
    person: str
    amount: float
    frequency: str = 'monthly'
    months: list[int] | None = None


@dataclass
class Expense(MonthlyMixin):
    id: int
    user_id: int
    name: str
    category: str
    amount: float
    frequency: str
    account: str | None = None
    months: list[int] | None = None


@dataclass
class Account:
    id: int
    name: str


@dataclass
class Category:
    id: int
    name: str
    icon: str


@dataclass
class User:
    id: int
    username: str
    password_hash: str
    salt: str
    email_hash: str = None

    def has_email(self) -> bool:
        """Check if user has an email hash set (for password reset)."""
        return bool(self.email_hash)


@dataclass
class PasswordResetToken:
    id: int
    user_id: int
    token_hash: str
    expires_at: str
    used: bool = False
