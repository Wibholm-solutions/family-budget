# Issue #115: Indkomst fordeling

> **For Claude:** Brug `superpowers:executing-plans` til at implementere denne plan task-by-task.

**Goal:** Beregn og vis hvor meget hver person skal overfoere til hver konto baseret paa indkomst og kontoernes udgiftstotaler.

**Tech Stack:** FastAPI, Jinja2, SQLite, TailwindCSS (ingen nye dependencies)

---

## 1. Kontekst

Brugeren har flere indkomstkilder, kontoer og udgifter tilknyttet kontoer. Det manglende stykke er **fordelingsalgoritmen**: givet total indkomst og kontotilknyttede udgifter, beregn hvor meget hver person proportionelt skal overfoere til hver konto.

## 2. Nuvaerende arkitektur

### Datamodeller (`src/database.py`)

- **Income** (linje 134-161): `id, user_id, person, amount, frequency, months`. Har `monthly_amount` property.
- **Expense** (linje 164-202): `account` er valgfrit tekst-felt der refererer til kontonavn.
- **Account** (linje 205-208): `id, name`.

### Relevante DB-funktioner:
- `get_all_income(user_id)` -> liste af Income
- `get_account_totals(user_id)` -> `dict[str, float]` (kontonavn -> maanedligt udgiftstotal)

### Dashboard (`src/api.py`, linje 625-678):
- Henter allerede baade `incomes` og `account_totals`
- Overfoerselsoversigt (dashboard.html linje 162-195) viser konto-totaler men IKKE per-person fordeling

## 3. Design beslutninger

**Valgt: Proportional fordeling baseret paa indkomstandel.**

Algoritme:
1. Beregn total maanedlig indkomst
2. Beregn hver persons andel: `person_share = person_income / total_income`
3. For hver konto: `person_transfer = account_total * person_share`

**Trade-offs:**
- Proportional (valgt): Fair - den der tjener mest betaler mest. Simpelt.
- Lige fordeling (fravalgt): 50/50 uanset indkomst - unfair.
- Manuel fordeling (fravalgt): Mere fleksibelt men kraever ekstra UI/DB. Kan tilfojes senere.

**Gruppering:** Indkomstkilder grupperes paa `person`-feltet. Samme person med flere kilder summeres.

## 4. Implementation steps

### Task 1: Fordelingsberegning i database.py

**Fil:** `src/database.py`

**Test foerst** (`tests/test_database.py`):

```python
class TestIncomeDistribution:
    def test_equal_income_splits_evenly(self, db_module):
        user_id = db_module.create_user("disttest", "pass123")
        db_module.add_income(user_id, "Person 1", 25000.0, "monthly")
        db_module.add_income(user_id, "Person 2", 25000.0, "monthly")
        db_module.add_account(user_id, "Budgetkonto")
        db_module.add_expense(user_id, "Husleje", "Bolig", 10000.0, "monthly", "Budgetkonto")
        dist = db_module.get_income_distribution(user_id)
        assert dist["Person 1"]["Budgetkonto"] == 5000.0
        assert dist["Person 2"]["Budgetkonto"] == 5000.0

    def test_unequal_income_proportional(self, db_module):
        user_id = db_module.create_user("disttest2", "pass123")
        db_module.add_income(user_id, "Person 1", 30000.0, "monthly")
        db_module.add_income(user_id, "Person 2", 10000.0, "monthly")
        db_module.add_account(user_id, "Felles")
        db_module.add_expense(user_id, "Husleje", "Bolig", 10000.0, "monthly", "Felles")
        dist = db_module.get_income_distribution(user_id)
        assert dist["Person 1"]["Felles"] == 7500.0  # 75%
        assert dist["Person 2"]["Felles"] == 2500.0  # 25%

    def test_no_accounts_returns_empty(self, db_module):
        user_id = db_module.create_user("disttest3", "pass123")
        db_module.add_income(user_id, "Person 1", 25000.0, "monthly")
        dist = db_module.get_income_distribution(user_id)
        assert dist == {}
```

**Implementation:**

```python
def get_income_distribution(user_id: int) -> dict[str, dict[str, float]]:
    """Proportional fordeling af konto-udgifter baseret paa indkomstandel.
    Returns: {person_name: {account_name: amount, "_total": income, "_remaining": unallocated}}
    """
    incomes = get_all_income(user_id)
    account_totals = get_account_totals(user_id)
    if not incomes or not account_totals:
        return {}
    total_income = sum(inc.monthly_amount for inc in incomes)
    if total_income == 0:
        return {}
    result = {}
    for inc in incomes:
        share = inc.monthly_amount / total_income
        person_dist = {}
        for account_name, account_total in account_totals.items():
            person_dist[account_name] = round(account_total * share, 2)
        person_dist["_total"] = round(inc.monthly_amount, 2)
        person_dist["_remaining"] = round(inc.monthly_amount - sum(
            v for k, v in person_dist.items() if not k.startswith("_")
        ), 2)
        result[inc.person] = person_dist
    return result
```

### Task 2: Demo-data funktion

Tilfoej `get_demo_income_distribution()` i `database.py` efter `get_demo_account_totals`.

### Task 3: Dashboard med per-person fordeling

**Filer:** `src/api.py` (dashboard route), `templates/dashboard.html`

a. Tilfoej `income_distribution` til dashboard context (baade demo og real)
b. Udvid overfoerselsoversigt-sektionen (linje 162-195) med per-person breakdown:

```html
{% if income_distribution %}
<div class="mt-3 pt-3 border-t border-gray-100 dark:border-gray-700">
    <div class="text-xs font-medium text-gray-500 mb-2">Fordeling per person</div>
    {% for person, accounts in income_distribution.items() %}
    <div class="mb-3 last:mb-0">
        <div class="flex justify-between text-sm mb-1">
            <span class="font-medium">{{ person }}</span>
            <span class="text-xs text-gray-500">Indkomst: {{ format_currency(accounts._total) }}</span>
        </div>
        {% for account_name, amount in accounts.items() %}
        {% if not account_name.startswith('_') %}
        <div class="flex justify-between text-xs text-gray-600 dark:text-gray-400 pl-4 py-0.5">
            <span>-> {{ account_name }}</span>
            <span data-monthly="{{ amount }}" data-yearly="{{ amount * 12 }}">{{ format_currency(amount) }}</span>
        </div>
        {% endif %}
        {% endfor %}
        <div class="flex justify-between text-xs pl-4 py-0.5 {% if accounts._remaining >= 0 %}text-green-600{% else %}text-red-600{% endif %}">
            <span>-> Til fri brug</span>
            <span data-monthly="{{ accounts._remaining }}" data-yearly="{{ accounts._remaining * 12 }}">{{ format_currency(accounts._remaining) }}</span>
        </div>
    </div>
    {% endfor %}
</div>
{% endif %}
```

### Task 4: Indkomstside-visning

**Filer:** `src/api.py` (income_page), `templates/income.html`

Tilfoej "Overfoersler per person"-sektion efter indkomstlisten med detaljeret fordeling per konto.

### Task 5: E2E test

```python
def test_income_distribution_visible_advanced_demo(page):
    page.goto("/budget/demo/toggle")
    page.goto("/budget/demo/toggle")  # Toggle to advanced
    page.goto("/budget/")
    expect(page.get_by_text("Fordeling per person")).to_be_visible()
```

## 5. Acceptkriterier

1. `get_income_distribution()` returnerer korrekt proportional fordeling
2. Dashboard viser per-person breakdown med beloeb per konto
3. Indkomstside viser "Overfoersler per person"-sektion
4. "Til fri brug" vises per person (indkomst minus overfoersel)
5. Demo virker korrekt
6. Maaned/aar toggle virker for fordelingsbeloeb
7. Tom tilstand: ingen fordeling vises uden kontoer/indkomst
8. Alle eksisterende tests bestaar

## 6. Test plan

- **Unit:** 5+ tests for beregningslogik (lige, ulige, tom, remaining)
- **API:** 2 tests (dashboard viser/skjuler fordeling)
- **E2E:** 1 test (advanced demo)
- **Manuel:** Opret 2 personer, kontoer, udgifter -> verificer beregning
