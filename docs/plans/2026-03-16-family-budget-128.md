# Deduplicate Yearly Overview Logic — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers-extended-cc:subagent-driven-development (if subagents available) or superpowers-extended-cc:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract shared aggregation logic from `get_yearly_overview` and `get_yearly_overview_demo` into a single `_calculate_yearly_overview` helper, eliminating ~60 lines of duplication.

**Architecture:** A private helper function `_calculate_yearly_overview(expenses, income_entries)` performs all aggregation; both public functions become thin wrappers that fetch data and delegate to the helper. The demo version currently uses `inc.get_monthly_amounts()` (more correct, handles month-specific income) while the DB version uses `inc.monthly_amount` — the refactor aligns both to use `get_monthly_amounts()`, which is a safe change since the behavior is identical for monthly income and more correct for non-monthly.

**Tech Stack:** Python, pytest, SQLite (via `src/database.py`)

---

## Chunk 1: Write Tests for Helper + Implement Helper

### Task 1: Write failing tests for `_calculate_yearly_overview`

**Files:**
- Modify: `tests/test_database.py` (append new `TestCalculateYearlyOverview` class after line 1133)

- [ ] **Step 1: Append test class to `tests/test_database.py`**

Add the following class at the end of `TestYearlyOverview` (after line 1133):

```python
class TestCalculateYearlyOverview:
    """Tests for the private _calculate_yearly_overview helper."""

    def test_empty_inputs_return_zero_structure(self, db_module):
        """Empty expenses and income return correct zero-filled structure."""
        result = db_module._calculate_yearly_overview([], [])
        assert result['categories'] == {}
        assert result['year_total'] == 0.0
        assert list(result['totals'].keys()) == list(range(1, 13))
        assert all(result['totals'][m] == 0 for m in range(1, 13))
        assert all(result['income'][m] == 0 for m in range(1, 13))
        assert all(result['balance'][m] == 0 for m in range(1, 13))

    def test_monthly_expense_appears_every_month(self, db_module):
        """A monthly expense spreads evenly across all 12 months."""
        from src.database import Expense
        expenses = [Expense(id=1, user_id=0, name="Husleje", category="Bolig",
                            amount=10000, frequency="monthly")]
        result = db_module._calculate_yearly_overview(expenses, [])
        assert all(result['categories']['Bolig'][m] == 10000 for m in range(1, 13))
        assert result['year_total'] == 120000

    def test_expense_with_specific_months(self, db_module):
        """Expense with months=[3,9] only appears in those months."""
        from src.database import Expense
        expenses = [Expense(id=1, user_id=0, name="Forsikring", category="Forsikring",
                            amount=6000, frequency="semi-annual", months=[3, 9])]
        result = db_module._calculate_yearly_overview(expenses, [])
        assert result['categories']['Forsikring'][3] == 3000
        assert result['categories']['Forsikring'][9] == 3000
        assert result['categories']['Forsikring'][1] == 0
        assert result['year_total'] == 6000

    def test_monthly_income_spread_evenly(self, db_module):
        """Monthly income spreads evenly across all 12 months."""
        from src.database import Income
        income = [Income(id=1, user_id=0, person="Person 1",
                         amount=30000, frequency="monthly")]
        result = db_module._calculate_yearly_overview([], income)
        assert all(result['income'][m] == 30000 for m in range(1, 13))

    def test_balance_is_income_minus_expenses(self, db_module):
        """Balance = income - totals for each month."""
        from src.database import Expense, Income
        expenses = [Expense(id=1, user_id=0, name="Husleje", category="Bolig",
                            amount=10000, frequency="monthly")]
        income = [Income(id=1, user_id=0, person="Person 1",
                         amount=30000, frequency="monthly")]
        result = db_module._calculate_yearly_overview(expenses, income)
        assert all(result['balance'][m] == 20000 for m in range(1, 13))

    def test_multiple_categories_sum_correctly(self, db_module):
        """Multiple expense categories aggregate independently."""
        from src.database import Expense
        expenses = [
            Expense(id=1, user_id=0, name="Husleje", category="Bolig",
                    amount=5000, frequency="monthly"),
            Expense(id=2, user_id=0, name="Mad", category="Mad",
                    amount=3000, frequency="monthly"),
        ]
        result = db_module._calculate_yearly_overview(expenses, [])
        assert all(result['categories']['Bolig'][m] == 5000 for m in range(1, 13))
        assert all(result['categories']['Mad'][m] == 3000 for m in range(1, 13))
        assert all(result['totals'][m] == 8000 for m in range(1, 13))

    def test_return_structure_has_all_keys(self, db_module):
        """Return value always has all five expected keys."""
        result = db_module._calculate_yearly_overview([], [])
        assert set(result.keys()) == {'categories', 'totals', 'income', 'balance', 'year_total'}
```

- [ ] **Step 2: Run tests to confirm they fail (function not yet defined)**

```bash
cd ~/projects/family-budget && python -m pytest tests/test_database.py::TestCalculateYearlyOverview -v 2>&1 | head -30
```

Expected: `AttributeError: module 'src.database' has no attribute '_calculate_yearly_overview'`

---

### Task 2: Implement `_calculate_yearly_overview` helper

**Files:**
- Modify: `src/database.py` — insert helper before line 1131 (`def get_yearly_overview`)

- [ ] **Step 1: Insert helper function into `src/database.py` before `get_yearly_overview`**

Insert this block immediately before the line `def get_yearly_overview(user_id: int) -> dict:` (currently line 1131):

```python
def _calculate_yearly_overview(expenses: list, income_entries: list) -> dict:
    """Shared aggregation logic for yearly overview.

    Args:
        expenses: List of Expense objects with get_monthly_amounts().
        income_entries: List of Income objects with get_monthly_amounts().

    Returns:
        dict with keys: categories, totals, income, balance, year_total.
    """
    # Build category breakdown
    categories: dict[str, dict[int, float]] = {}
    for exp in expenses:
        if exp.category not in categories:
            categories[exp.category] = {m: 0.0 for m in range(1, 13)}
        monthly = exp.get_monthly_amounts()
        for m in range(1, 13):
            categories[exp.category][m] += monthly[m]

    # Round all category values
    for cat in categories:
        for m in range(1, 13):
            categories[cat][m] = round(categories[cat][m], 2)

    # Totals per month
    totals = {m: round(sum(cat[m] for cat in categories.values()), 2) for m in range(1, 13)}

    # Income per month (respects months field via get_monthly_amounts)
    income = {m: 0.0 for m in range(1, 13)}
    for inc in income_entries:
        monthly_amounts = inc.get_monthly_amounts()
        for m in range(1, 13):
            income[m] += monthly_amounts[m]
    for m in range(1, 13):
        income[m] = round(income[m], 2)

    # Balance and year total
    balance = {m: round(income[m] - totals[m], 2) for m in range(1, 13)}
    year_total = round(sum(totals.values()), 2)

    return {
        'categories': categories,
        'totals': totals,
        'income': income,
        'balance': balance,
        'year_total': year_total,
    }

```

- [ ] **Step 2: Run new tests to confirm they pass**

```bash
cd ~/projects/family-budget && python -m pytest tests/test_database.py::TestCalculateYearlyOverview -v 2>&1 | tail -20
```

Expected: All 7 tests PASSED

- [ ] **Step 3: Commit**

```bash
cd ~/projects/family-budget && git add src/database.py tests/test_database.py
git commit -m "feat: add _calculate_yearly_overview helper with tests"
```

---

## Chunk 2: Refactor Public Functions + Cleanup

### Task 3: Replace `get_yearly_overview` body with helper call

**Files:**
- Modify: `src/database.py` lines 1131–1187 (the `get_yearly_overview` function)

> **Note:** After inserting the helper, line numbers have shifted by ~50. Use the function signature to find the correct location.

- [ ] **Step 1: Replace `get_yearly_overview` body**

Find `def get_yearly_overview(user_id: int) -> dict:  # noqa: C901, PLR0912` and replace the entire function (signature through `return` statement) with:

```python
def get_yearly_overview(user_id: int) -> dict:
    """Calculate yearly overview with monthly breakdown.

    Returns dict with:
        categories: {category_name: {1: amount, 2: amount, ..., 12: amount}}
        totals: {1: total, ..., 12: total}
        income: {1: amount, ..., 12: amount}
        balance: {1: amount, ..., 12: amount}
        year_total: float (total expenses for the year)
    """
    return _calculate_yearly_overview(
        get_all_expenses(user_id),
        get_all_income(user_id),
    )
```

Key change: remove `# noqa: C901, PLR0912` — complexity now lives in the helper, which is simple enough that it doesn't trigger these rules.

- [ ] **Step 2: Run existing yearly overview tests to confirm no regressions**

```bash
cd ~/projects/family-budget && python -m pytest tests/test_database.py::TestYearlyOverview -v 2>&1 | tail -20
```

Expected: All 7 tests PASSED

---

### Task 4: Replace `get_yearly_overview_demo` body with helper call

**Files:**
- Modify: `src/database.py` — the `get_yearly_overview_demo` function

- [ ] **Step 1: Replace `get_yearly_overview_demo` body**

Find `def get_yearly_overview_demo(advanced: bool = False) -> dict:` and replace the entire function with:

```python
def get_yearly_overview_demo(advanced: bool = False) -> dict:
    """Get yearly overview for demo mode."""
    return _calculate_yearly_overview(
        get_demo_expenses(advanced),
        get_demo_income(advanced),
    )
```

- [ ] **Step 2: Run full test suite to confirm no regressions**

```bash
cd ~/projects/family-budget && python -m pytest tests/ -v 2>&1 | tail -30
```

Expected: All tests PASSED. If any fail, check the error — the most likely cause is a test that relies on the old income behavior (`monthly_amount` vs `get_monthly_amounts()`).

- [ ] **Step 3: Commit**

```bash
cd ~/projects/family-budget && git add src/database.py
git commit -m "refactor: deduplicate yearly overview logic via _calculate_yearly_overview (#128)"
```

---

## Chunk 3: Branch, PR, and Cleanup

### Task 5: Open PR

- [ ] **Step 1: Verify you are on a feature branch (not master)**

```bash
cd ~/projects/family-budget && git branch --show-current
```

If on `master`, you need to move commits to a branch:

```bash
git checkout -b refactor/deduplicate-yearly-overview
```

If already on a feature branch, continue.

- [ ] **Step 2: Push branch and open PR**

```bash
cd ~/projects/family-budget && git push -u origin HEAD
gh pr create \
  --repo saabendtsen/family-budget \
  --title "refactor: deduplicate yearly overview logic (#128)" \
  --body "Extracts shared aggregation logic from \`get_yearly_overview\` and \`get_yearly_overview_demo\` into \`_calculate_yearly_overview\` helper. Eliminates ~60 lines of duplication. Both public functions become thin wrappers. Also aligns income handling to use \`get_monthly_amounts()\` consistently (previously \`get_yearly_overview\` used the simpler \`monthly_amount\` property). Closes #128."
```

- [ ] **Step 3: Verify CI passes**

```bash
gh pr checks --repo saabendtsen/family-budget
```

Wait for green. If red, read the failure and fix.

---

## Acceptance Criteria

- [ ] `_calculate_yearly_overview` exists and passes all 7 new unit tests
- [ ] `get_yearly_overview` is a ~5 line wrapper with no `noqa` suppression
- [ ] `get_yearly_overview_demo` is a ~3 line wrapper
- [ ] All existing tests in `TestYearlyOverview` still pass
- [ ] Full test suite green
- [ ] PR open on GitHub
