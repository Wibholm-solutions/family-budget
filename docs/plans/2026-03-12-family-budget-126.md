# Fix Exception Chaining (B904) — Issue #126

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:executing-plans to implement this plan task-by-task.

**Goal:** Fix all 15 B904 exception chaining violations listed in issue #126 by replacing the 8 remaining `# noqa: B904` suppressions with proper `from e` / `from None` chaining.

**Architecture:** Pure mechanical fix — no behavior change. HTTP responses are identical. Only the exception `__cause__` attribute changes, improving tracebacks in logs and debuggers.

---

## Status of All 15 Locations

| File | Lines | Status |
|------|-------|--------|
| `src/helpers.py` (was api.py:110) | 118 | Already fixed (`from None`) |
| `src/routes/expenses.py` | 47, 125, 140, 157, 186, 201 | Already fixed (6 locations) |
| `src/routes/accounts.py` | 67, 113, 141 | **To fix** (3 `# noqa: B904`) |
| `src/routes/categories.py` | 71, 97, 132 | **To fix** (3 `# noqa: B904`) |
| `src/routes/income.py` | 68, 82 | **To fix** (2 `# noqa: B904`) |

## Chaining Rules

| Exception caught | HTTP status | Chain with | Reason |
|---|---|---|---|
| `sqlite3.IntegrityError` | 400 | `from None` | Hide DB internals from HTTP layer |
| `ValueError` | 400 | `from None` | Parse error irrelevant to caller |
| `sqlite3.Error as e` | 500 | `from e` | Chain for server-side debugging |
| `(ValueError, sqlite3.Error) as e` | 500 | `from e` | Chain for debugging |

---

### Task 1: Baseline — green tests and count suppressions

```bash
cd ~/projects/family-budget
grep -c "noqa: B904" src/routes/accounts.py src/routes/categories.py src/routes/income.py
python -m pytest tests/ -x -q
```

Expected: 3 + 3 + 2 = 8 suppressions, all tests pass.

Then create feature branch:
```bash
git checkout -b fix/b904-exception-chaining-126
```

---

### Task 2: Fix `src/routes/accounts.py` — 3 violations

**Line 67-70** (`add_account`, IntegrityError → 400): Remove `# noqa: B904`, add `) from None`
```python
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=400,
            detail=f"Kontoen '{name}' findes allerede"
        ) from None
```

**Line 113-116** (`edit_account`, IntegrityError → 400): Same pattern — `) from None`

**Line 141** (`delete_account`, sqlite3.Error as e → 500): Remove `# noqa: B904`, add `from e`
```python
        raise HTTPException(status_code=500, detail="Der opstod en fejl ved sletning af kontoen") from e
```

Verify + commit:
```bash
ruff check src/routes/accounts.py --select B904
git add src/routes/accounts.py && git commit -m "fix: add exception chaining in accounts routes (B904)"
```

---

### Task 3: Fix `src/routes/categories.py` — 3 violations

**Line 71-74** (`add_category`, IntegrityError → 400): `) from None`
**Line 97-100** (`edit_category`, IntegrityError → 400): `) from None`
**Line 132** (`delete_category`, sqlite3.Error as e → 500): `from e`

Keep existing comments (`# Category name already exists...`).

Verify + commit:
```bash
ruff check src/routes/categories.py --select B904
git add src/routes/categories.py && git commit -m "fix: add exception chaining in categories routes (B904)"
```

---

### Task 4: Fix `src/routes/income.py` — 2 violations

**Line 68** (inner `except ValueError` → 400): Replace `# noqa: B904` with `from None`
```python
                except ValueError:
                    raise HTTPException(status_code=400, detail=f"Ugyldigt beløb format for {name}") from None
```

**Line 82** (outer `except (ValueError, sqlite3.Error) as e` → 500): Replace `# noqa: B904` with `from e`
```python
    except (ValueError, sqlite3.Error) as e:
        logger.error(f"Error updating income: {e}")
        raise HTTPException(status_code=500, detail="Der opstod en fejl ved opdatering af indkomst") from e
```

Verify + commit:
```bash
ruff check src/routes/income.py --select B904
git add src/routes/income.py && git commit -m "fix: add exception chaining in income routes (B904)"
```

---

### Task 5: Full verification and PR

```bash
# Zero B904 suppressions remaining
grep -r "noqa: B904" src/
# Should return nothing

# Full ruff clean
ruff check src/

# Full test suite
python -m pytest tests/ -x -q
```

Push and create PR:
```bash
git push -u origin fix/b904-exception-chaining-126
gh pr create \
  --repo saabendtsen/family-budget \
  --title "fix: add exception chaining in except blocks (B904)" \
  --body "$(cat <<'EOF'
## Summary

Fixes #126. Replaces 8 `# noqa: B904` suppressions with proper exception chaining across 3 route files. The other 7 locations (expenses.py, helpers.py) were already fixed.

- `accounts.py`: 3 fixes (add/edit: `from None`, delete: `from e`)
- `categories.py`: 3 fixes (add/edit: `from None`, delete: `from e`)
- `income.py`: 2 fixes (parse 400: `from None`, outer 500: `from e`)

**No behavior change.** HTTP responses are identical. Only the exception `__cause__` changes, improving tracebacks.

## Test plan

- [ ] `ruff check --select B904 src/` passes with zero violations
- [ ] `grep -r "noqa: B904" src/` returns nothing
- [ ] Full test suite passes

Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

## Out of Scope

- Constants refactoring from closed PR #147 — separate concern
- No changes to `expenses.py` or `helpers.py` — already fixed
- No changes to `api.py` — violation was `parse_danish_amount`, now in `helpers.py` and already fixed
