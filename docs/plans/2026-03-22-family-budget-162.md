# Extract Per-Entity Validators into src/validators.py

> **For agentic workers:** REQUIRED: Use superpowers-extended-cc:subagent-driven-development (if subagents available) or superpowers-extended-cc:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate fragmented input validation into a single `src/validators.py` module with consistent error handling, fixing the income silent-frequency-fallback bug and adding name validation for all entities.

**Architecture:** A new `src/validators.py` with a frozen `ValidationResult` dataclass and one `validate_*` function per entity type (expense, income, category, account). Private helpers (`_validate_name`, `_parse_and_validate_amount`, `_validate_frequency`, `_parse_and_validate_months`) handle shared logic. Routes call `result.raise_if_invalid()` for the HTTP bridge. Existing `validate_expense_input` becomes a 3-line shim for backward compatibility with 16 existing tests.

**Tech Stack:** Python 3.12, FastAPI, pytest

**Previous attempt:** PR #167 (branch `feat/extract-validators-162`) — closed due to merge conflicts. The implementation was complete and correct. Master has since caught up (no divergence). This plan refines the approach based on review feedback.

---

## File Structure

```
src/
    validators.py            # CREATE: ~150 lines - ValidationResult + per-entity validators
    routes/expenses.py       # MODIFY: shim validate_expense_input, re-export VALID_FREQUENCIES
    routes/income.py         # MODIFY: use validate_income(), fix silent frequency bug
    routes/categories.py     # MODIFY: use validate_category(), add pre-validation
    routes/accounts.py       # MODIFY: use validate_account(), add pre-validation
    helpers.py               # NO CHANGE: parse_danish_amount stays here
tests/
    test_validators.py       # CREATE: ~200 lines - unit tests for all validators
    test_expense_validation.py  # NO CHANGE in this PR (shim preserves compatibility)
```

### Dependency Graph

```
src/validators.py --> src/helpers.py (parse_danish_amount only)
src/routes/expenses.py --> src/validators.py (validate_expense, VALID_FREQUENCIES)
src/routes/income.py --> src/validators.py (validate_income)
src/routes/categories.py --> src/validators.py (validate_category)
src/routes/accounts.py --> src/validators.py (validate_account)
```

### Key Design Decisions

1. **`parse_danish_amount` stays in `helpers.py`** — it's also used for display formatting. `validators.py` imports it.
2. **Shim in `expenses.py`** — `validate_expense_input()` delegates to `validate_expense()` so existing 16 tests pass unchanged. The shim passes `name=None` and skips name validation errors by filtering them from the result. Shim removal is a follow-up PR.
3. **`VALID_FREQUENCIES` re-exported from `expenses.py`** — templates may reference it via the module. The canonical definition moves to `validators.py`; `expenses.py` re-imports with `# noqa: F401`.
4. **Error accumulation** — each validator collects ALL errors before returning (unlike current early-exit pattern). `raise_if_invalid()` joins errors with `"; "`.
5. **Name validation** — new `_validate_name()` rejects None, empty, whitespace-only, and names > 200 chars. Applied to all entities.
6. **Income frequency bug fix** — `validate_income()` rejects invalid frequencies with an error instead of silently defaulting to `'monthly'`.
7. **`add_account_json` special case** — this route returns `JSONResponse` (not `HTTPException`). Use `validate_account()` but check `result.ok` and return `JSONResponse` on failure instead of `raise_if_invalid()`.
8. **ValidationResult.ok as property** — computed from `len(self.errors) == 0` rather than a stored field, ensuring consistency.

---

## Phase 1: Create validators.py with ValidationResult and expense validator

TDD: write tests first, then implement.

### Step 1.1: Write test_validators.py with expense and ValidationResult tests
- [ ] Create `tests/test_validators.py`
- [ ] `TestValidationResult`:
  - `test_ok_when_no_errors` — `ValidationResult(errors=[], parsed={"amount": 100.0})` → `ok is True`
  - `test_not_ok_with_errors` — `ValidationResult(errors=["bad"], parsed={})` → `ok is False`
  - `test_raise_if_invalid_raises_400` — two errors → `HTTPException(400)` with both in detail
  - `test_raise_if_invalid_noop_when_ok` — no errors → no exception
- [ ] `TestValidateExpense` — port all 16 existing test cases asserting on `ValidationResult`:
  - `test_valid_monthly_expense` — `("Husleje", "1000", "monthly", "", None)` → ok, amount=1000.0, months=None
  - `test_danish_decimal_amount` — `"1.500,50"` → amount=1500.50
  - `test_quarterly_with_months` — `"3,6,9,12"` → months=[3,6,9,12]
  - `test_semi_annual_with_months` — `"1,7"` → months=[1,7]
  - `test_yearly_with_month` — `"1"` → months=[1]
  - `test_invalid_frequency` — `"biweekly"` → not ok, error mentions "frekvens"
  - `test_invalid_amount_format` — `"not-a-number"` → not ok
  - `test_negative_amount` — `"-1"` → not ok, error mentions "positivt"
  - `test_zero_amount_allowed` — `"0"` → ok, amount=0.0
  - `test_amount_at_upper_limit` — `"1000000"` → ok
  - `test_amount_over_limit` — `"1000001"` → not ok, error mentions "stor"
  - `test_invalid_months_format` — `"a,b,c,d"` → not ok
  - `test_months_out_of_range` — `"0,6,9,13"` → not ok
  - `test_wrong_month_count` — quarterly with 2 months → not ok
- [ ] Run tests: all should FAIL (module doesn't exist yet — red phase)

### Step 1.2: Create src/validators.py with expense validation
- [ ] `ValidationResult` dataclass (frozen): `errors: list[str]`, `parsed: dict[str, object]`, `ok` property, `raise_if_invalid()` method
- [ ] Constants: `VALID_FREQUENCIES`, `MONTHS_REQUIRED`
- [ ] `_validate_name(name: str | None, entity: str, errors: list[str]) -> str | None` — rejects None/empty/whitespace/len>200
- [ ] `_parse_and_validate_amount(amount_str: str, errors: list[str]) -> float | None` — uses `parse_danish_amount`, checks <0 and >1M
- [ ] `_validate_frequency(freq: str, errors: list[str]) -> str | None` — checks against `VALID_FREQUENCIES`
- [ ] `_parse_and_validate_months(months_str: str | None, freq: str, errors: list[str]) -> list[int] | None` — parses comma-separated ints, validates range and count
- [ ] `validate_expense(name, amount_str, frequency, months_str, account) -> ValidationResult`
- [ ] Run tests: all expense tests GREEN

### Step 1.3: Wire expense shim in routes/expenses.py
- [ ] Import `VALID_FREQUENCIES`, `MONTHS_REQUIRED`, `validate_expense` from `..validators`
- [ ] Re-export with `# noqa: F401` for backward compat
- [ ] Remove local `VALID_FREQUENCIES`, `MONTHS_REQUIRED` constants
- [ ] Delete `parse_months()` function (logic now in `_parse_and_validate_months`)
- [ ] Replace `validate_expense_input` body with shim:
  ```python
  def validate_expense_input(amount_str, frequency, months_str):
      """Shim: delegates to validate_expense() for backward compatibility."""
      result = validate_expense(None, amount_str, frequency, months_str, None)
      non_name_errors = [e for e in result.errors if "navn" not in e.lower()]
      if non_name_errors:
          raise HTTPException(status_code=400, detail=non_name_errors[0])
      return result.parsed["amount"], result.parsed["months"]
  ```
- [ ] Remove `parse_danish_amount` import from `expenses.py` (no longer needed)
- [ ] Run `test_expense_validation.py` — all 16 tests pass
- [ ] Run `test_validators.py` — all green

---

## Phase 2: Income, category, and account validators

### Step 2.1: Write income validator tests and implement
- [ ] `TestValidateIncome` in `test_validators.py`:
  - `test_valid_income` — `("Løn", "30000", "monthly")` → ok, name="Løn", amount=30000.0, frequency="monthly"
  - `test_invalid_frequency_is_error` — `"biweekly"` → not ok (BUG FIX: currently silently defaults to monthly)
  - `test_invalid_amount_format` — `"abc"` → not ok
  - `test_negative_amount` — `"-500"` → not ok
  - `test_empty_name` — `""` → not ok
  - `test_error_accumulation` — `("", "abc", "biweekly")` → 3 errors (name + amount + frequency)
- [ ] Implement `validate_income(name, amount_str, frequency)` in `validators.py`
- [ ] Run tests: income tests GREEN

### Step 2.2: Write category validator tests and implement
- [ ] `TestValidateCategory` in `test_validators.py`:
  - `test_valid_category` — `("Mad", "🍕")` → ok, name="Mad", icon="🍕"
  - `test_empty_name` — `""` → not ok
  - `test_whitespace_name` — `"   "` → not ok
  - `test_name_too_long` — `"A" * 201` → not ok
  - `test_empty_icon` — `""` → not ok
  - `test_both_invalid` — `("", "")` → 2 errors
- [ ] Implement `validate_category(name, icon)` in `validators.py`
- [ ] Run tests: category tests GREEN

### Step 2.3: Write account validator tests and implement
- [ ] `TestValidateAccount` in `test_validators.py`:
  - `test_valid_account` — `"Nordea"` → ok, name="Nordea"
  - `test_empty_name` — `""` → not ok
  - `test_whitespace_name` — `"   "` → not ok
  - `test_name_too_long` — `"A" * 201` → not ok
- [ ] Implement `validate_account(name)` in `validators.py`
- [ ] Run tests: account tests GREEN

---

## Phase 3: Wire remaining routes

### Step 3.1: Update income.py to use validate_income()
- [ ] Import `validate_income` from `..validators`
- [ ] Replace inline validation (lines 50-63) with per-entry validation:
  ```python
  if name:
      result = validate_income(name, amount_str if amount_str else "0", frequency)
      result.raise_if_invalid()
      incomes_to_save.append((result.parsed["name"], result.parsed["amount"], result.parsed["frequency"]))
  ```
- [ ] Remove `parse_danish_amount` import (no longer used directly)
- [ ] This fixes the silent frequency fallback bug — invalid frequency now returns 400
- [ ] Run full test suite

### Step 3.2: Update categories.py to use validate_category()
- [ ] Import `validate_category` from `..validators`
- [ ] Add `validate_category(name, icon).raise_if_invalid()` before `db.add_category()` in `add_category` route
- [ ] Add `validate_category(name, icon).raise_if_invalid()` before `db.update_category()` in `edit_category` route
- [ ] Run full test suite

### Step 3.3: Update accounts.py to use validate_account()
- [ ] Import `validate_account` from `..validators`
- [ ] `add_account` route: add `validate_account(name).raise_if_invalid()` before DB call
- [ ] `add_account_json` route: **special case** — replace existing `name.strip()` / empty check with:
  ```python
  result = validate_account(name)
  if not result.ok:
      return JSONResponse({"success": False, "error": "; ".join(result.errors)}, status_code=400)
  name = result.parsed["name"]
  ```
- [ ] `edit_account` route: add `validate_account(name).raise_if_invalid()` before DB call
- [ ] Run full test suite

---

## Phase 4: Final verification

### Step 4.1: Full test suite, lint, and import checks
- [ ] Run `pytest -x` — all tests pass (existing + new)
- [ ] Run `ruff check src/validators.py tests/test_validators.py` — no lint errors
- [ ] Verify no circular imports: `python -c "from src.validators import validate_expense"`
- [ ] Verify backward compat: `python -c "from src.routes.expenses import validate_expense_input, VALID_FREQUENCIES"`
- [ ] Run full `ruff check src/ tests/` — no new lint errors

---

## Testable Behaviors Summary

| # | Behavior | Validator | Test |
|---|----------|-----------|------|
| 1 | ValidationResult.ok is True when no errors | ValidationResult | test_ok_when_no_errors |
| 2 | ValidationResult.ok is False when errors exist | ValidationResult | test_not_ok_with_errors |
| 3 | raise_if_invalid() raises HTTPException(400) with joined errors | ValidationResult | test_raise_if_invalid_raises_400 |
| 4 | raise_if_invalid() is no-op when ok | ValidationResult | test_raise_if_invalid_noop_when_ok |
| 5 | Valid monthly expense parses correctly | validate_expense | test_valid_monthly_expense |
| 6 | Danish decimal amount parsed | validate_expense | test_danish_decimal_amount |
| 7 | Quarterly requires 4 months | validate_expense | test_quarterly_with_months |
| 8 | Semi-annual requires 2 months | validate_expense | test_semi_annual_with_months |
| 9 | Yearly requires 1 month | validate_expense | test_yearly_with_month |
| 10 | Invalid frequency rejected | validate_expense | test_invalid_frequency |
| 11 | Invalid amount format rejected | validate_expense | test_invalid_amount_format |
| 12 | Negative amount rejected | validate_expense | test_negative_amount |
| 13 | Zero amount allowed | validate_expense | test_zero_amount_allowed |
| 14 | Amount at 1M limit allowed | validate_expense | test_amount_at_upper_limit |
| 15 | Amount over 1M rejected | validate_expense | test_amount_over_limit |
| 16 | Invalid months format rejected | validate_expense | test_invalid_months_format |
| 17 | Months out of range rejected | validate_expense | test_months_out_of_range |
| 18 | Wrong month count rejected | validate_expense | test_wrong_month_count |
| 19 | Income: valid input parses correctly | validate_income | test_valid_income |
| 20 | Income: invalid frequency is error (not silent fallback) | validate_income | test_invalid_frequency_is_error |
| 21 | Income: invalid amount rejected | validate_income | test_invalid_amount_format |
| 22 | Income: negative amount rejected | validate_income | test_negative_amount |
| 23 | Income: empty name rejected | validate_income | test_empty_name |
| 24 | Income: multiple errors accumulated | validate_income | test_error_accumulation |
| 25 | Category: valid name+icon | validate_category | test_valid_category |
| 26 | Category: empty name rejected | validate_category | test_empty_name |
| 27 | Category: whitespace-only name rejected | validate_category | test_whitespace_name |
| 28 | Category: name > 200 chars rejected | validate_category | test_name_too_long |
| 29 | Category: empty icon rejected | validate_category | test_empty_icon |
| 30 | Category: both invalid → 2 errors | validate_category | test_both_invalid |
| 31 | Account: valid name | validate_account | test_valid_account |
| 32 | Account: empty name rejected | validate_account | test_empty_name |
| 33 | Account: whitespace-only rejected | validate_account | test_whitespace_name |
| 34 | Account: name > 200 chars rejected | validate_account | test_name_too_long |
| 35 | Shim: validate_expense_input backward compat | shim | existing 16 tests in test_expense_validation.py |

## Notes

- **Parallel-safe with #160 and #161**: This changes route body logic (validation), not `Depends()` signatures (#160) or DB layer (#161).
- **Previous PR #167 (closed):** Branch `feat/extract-validators-162` has a complete implementation. Create a fresh branch from current master. The old branch can be used as reference but should not be rebased (cleaner to start fresh).
- **`add_account_json` special case**: This route returns `JSONResponse` instead of raising `HTTPException`. Use `validate_account()` for validation but convert errors to `JSONResponse` manually (don't use `raise_if_invalid()`).
- **Name validation is new behavior**: Categories and accounts currently accept empty names. Adding validation may reject previously-accepted input. This is intentional (fixing a gap), but should be noted in the PR description.
- **Shim design**: The shim passes `name=None` to `validate_expense()`, which produces a name error. The shim filters errors containing "navn" (Danish for "name") before checking for failures. This is intentional — the original `validate_expense_input` didn't validate names.
