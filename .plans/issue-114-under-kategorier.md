# Issue #114: Underkategorier

> **For Claude:** Brug `superpowers:executing-plans` til at implementere denne plan task-by-task.

**Goal:** Hierarkiske kategorier med parent/child-relation. Max 2 niveauer.

---

## 1. Kontekst

Brugeren vil organisere udgifter hierarkisk, fx "Bil" som overkategori med bilforsikring under sig. Udgiften skal kun taelle et sted. Skal vaere valgfrit - simple brugere ser ingen forskel.

## 2. Nuvaerende arkitektur

- `Category` dataclass (database.py linje 211-215): `id, name, icon`
- Kategorier er per-bruger via `user_id`, UNIQUE(user_id, name)
- Udgifter grupperes via `expenses_by_category` dict
- Dashboard viser collapsible cards per kategori
- Aars-overblik bruger `overview.categories` dict

## 3. Design beslutninger

**Valgt: `parent_id` self-referential (adjacency list)**
- Simpelt, velkendt moenster
- Bagudkompatibelt - eksisterende kategorier faar `parent_id = NULL`
- **Max 2 niveauer** (rod + under) - holder UI simpelt
- Udgift forbliver knyttet til EN kategori

**Fravalgt:**
- Tags/multi-kategori: "udgiften skal kun taelle et sted" - for kompleks
- Virtuelle grupper: kraever helt ny datamodel

## 4. Implementation steps

### Trin 1: Database migration

**Fil:** `src/database.py`

```sql
ALTER TABLE categories ADD COLUMN parent_id INTEGER REFERENCES categories(id);
CREATE INDEX IF NOT EXISTS idx_categories_parent ON categories(parent_id);
```

Opdater `Category` dataclass: tilfoej `parent_id: int | None = None`

### Trin 2: Database funktioner

**Fil:** `src/database.py`

a. Opdater `get_all_categories()` til at SELECT `parent_id`
b. Opdater `add_category()` med valgfri `parent_id` + validering (max 2 niveauer)
c. Ny: `get_categories_tree(user_id)` -> `[{category, children: [...]}]`
d. Ny: `get_expenses_by_category_tree(user_id)` -> hierarkisk gruppering
e. Opdater `delete_category()`: bloker sletning af parent med children

**Validering i `add_category()`:**
```python
if parent_id is not None:
    parent = get_category_by_id(parent_id)
    if parent and parent.parent_id is not None:
        raise ValueError("Underkategorier kan kun have et niveau")
```

### Trin 3: API routes

**Fil:** `src/api.py`

a. `categories_page()`: send trae-struktur til template
b. `add_category()`: accepter `parent_id` form field
c. `expenses_page()`: send baade flade og trae-kategorier
d. `dashboard()`: brug hierarkisk gruppering

### Trin 4: Categories template

**Fil:** `templates/categories.html`

- Vis kategorier i trae-struktur (indrykkede children)
- "Tilfoej underkategori" knap paa rod-kategorier
- Add/edit modal: valgfri "Foraeldre-kategori" dropdown

### Trin 5: Expenses template

**Fil:** `templates/expenses.html`

Category dropdown med hierarki:
```html
{% for cat in categories %}
    {% if cat.parent_id is none %}
    <option value="{{ cat.name }}">{{ cat.name }}</option>
    {% else %}
    <option value="{{ cat.name }}">  -- {{ cat.name }}</option>
    {% endif %}
{% endfor %}
```

### Trin 6: Dashboard

**Fil:** `templates/dashboard.html`

- Rodkategorier viser sum af egne + underkategoriers udgifter
- Fold-ud viser underkategorier som undergrupper

### Trin 7: Aarsoverblik

**Fil:** `templates/yearly.html`

Hierarki med summerede raekker for foraeldre-kategorier.

### Trin 8: Demo data

Opdater advanced demo med fx "Transport" (rod) -> "Bil", "Offentlig transport"

## 5. Acceptkriterier

1. Brugere kan oprette underkategorier under rod-kategorier
2. Max 2 niveauer enforced i UI og API
3. Udgifter kan tildeles baade rod- og underkategorier
4. Dashboard viser hierarkisk gruppering med summering
5. Eksisterende brugere paavirkes IKKE
6. Category dropdown viser hierarki med indrykning
7. Sletning af parent med children er blokeret
8. Demo showcaser underkategorier

## 6. Test plan

**Unit tests:**
- `test_add_subcategory` - opret med parent_id
- `test_max_depth_enforcement` - kan ikke lave under-under-kategori
- `test_get_categories_tree` - korrekt trae
- `test_delete_parent_with_children_blocked`
- `test_delete_subcategory` - fungerer normalt
- `test_existing_categories_unchanged` - migration er sikker

**API tests:**
- `test_add_category_with_parent_id`
- `test_add_category_invalid_parent`
- `test_categories_page_shows_tree`

**E2E:**
- `test_create_subcategory_flow` - fuld flow
- `test_subcategory_dashboard_aggregation`
