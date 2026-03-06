# Issue #85: Person-tags paa indkomst

> **For Claude:** Brug `superpowers:executing-plans` til at implementere denne plan task-by-task.

**Goal:** Struktureret tilknytning af indkomstkilder til husstandsmedlemmer med per-person overblik.

**NB:** Issue #115 (indkomst fordeling) bygger oven paa denne feature. Implementer #85 foerst.

---

## 1. Kontekst

`person`-feltet i income-tabellen bruges som label/kilde-navn ("Bonus", "Boernepenge") - ikke som person-reference. Vi mangler en struktureret maade at tilknytte indkomst til personer.

## 2. Design: Ny `household_members` tabel

**Valgt: Ny tabel + `member_id` FK paa income**

```sql
CREATE TABLE household_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(user_id, name)
);

ALTER TABLE income ADD COLUMN member_id INTEGER REFERENCES household_members(id);
```

**Begrundelse:** `person`-feltet bruges til kildenavne. Separat tabel giver ren data-model og kan genbruges til fremtidig person-baseret udgiftsfordeling.

## 3. Implementation steps

### Step 1: Database (`src/database.py`)

a. `HouseholdMember` dataclass: `id, user_id, name`
b. Tilfoej `member_id: int | None = None` til `Income`
c. CREATE TABLE + migration i `init_db()`
d. CRUD: `get_household_members()`, `add_household_member()`, `delete_household_member()`
e. `get_income_by_member()` -> grupperet dict
f. `get_income_totals_by_member()` -> `{name: total}`
g. Opdater `add_income()`/`update_income()` med `member_id`

### Step 2: API (`src/api.py`)

a. Opdater `income_page()` med `household_members` i context
b. Opdater income POST handler med `member_id`
c. `POST /budget/income/members` + `DELETE /budget/income/members/{id}`
d. Dashboard: send `income_by_member` data

### Step 3: Income template (`templates/income.html`)

a. "Husstandsmedlemmer"-sektion oeverst: tags med X + tilfoej-input
b. Member dropdown per income-item
c. Opdater JS: `addIncome()` og `reindexIncomes()`

### Step 4: Dashboard (`templates/dashboard.html`)

Grupperet indkomst-visning per member (med fallback til nuvaerende visning)

### Step 5: Demo data

`DEMO_HOUSEHOLD_MEMBERS = ["Soeren", "Mette"]` + opdater advanced income

## 4. Acceptkriterier

1. Ny `household_members` tabel oprettes automatisk
2. Income kan tildeles member (valgfrit - NULL er OK)
3. Dashboard viser indkomst grupperet per person
4. Eksisterende data uden member_id fungerer stadig
5. Members kan tilfojes/fjernes fra income-siden
6. Demo viser person-baseret fordeling
7. Migration er backwards-compatible

## 5. Test plan

**Unit:** member CRUD, income med member, gruppering, delete cascade, backwards-compat
**API:** dropdown render, save med member, member CRUD endpoints
**E2E:** fuld flow + dashboard visning
