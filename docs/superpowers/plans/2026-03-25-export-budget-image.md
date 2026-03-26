# Export Budget Image Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers-extended-cc:subagent-driven-development (if subagents available) or superpowers-extended-cc:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users export their budget overview as a mobile-optimized PNG image from the Konto page.

**Architecture:** New `/budget/api/export-data` endpoint returns all budget data as JSON. Client-side JavaScript on the Konto page (`settings.html`) builds a hidden export div, renders a Chart.js doughnut to `<img>`, then uses `html-to-image` to convert to PNG and trigger download.

**Tech Stack:** FastAPI (endpoint), html-to-image (CDN), Chart.js (pie chart), TailwindCSS (layout)

**Spec:** `docs/superpowers/specs/2026-03-25-export-budget-image-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/routes/api_endpoints.py` | New `GET /budget/api/export-data` endpoint |
| `templates/settings.html` | "Eksporter" section with buttons + export JS |
| `tests/test_export.py` | Unit tests for export-data endpoint |

---

### Task 0: Create Feature Branch

- [ ] **Step 1: Create and switch to feature branch**

```bash
git checkout -b feature/export-budget-image
```

---

### Task 1: Export Data Endpoint — Tests

**Files:**
- Create: `tests/test_export.py`

- [ ] **Step 1: Write failing tests for export-data endpoint**

Model after `tests/test_charts.py`. Create `tests/test_export.py`:

```python
"""Tests for export data API endpoint."""


class TestExportDataEndpoint:
    """Tests for /budget/api/export-data endpoint."""

    def test_export_data_requires_auth(self, client):
        """Export data endpoint should require authentication."""
        response = client.get("/budget/api/export-data", follow_redirects=False)
        assert response.status_code == 303

    def test_export_data_returns_json(self, authenticated_client):
        """Endpoint should return valid JSON."""
        response = authenticated_client.get("/budget/api/export-data")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    def test_export_data_has_required_fields(self, authenticated_client):
        """Response should include all required fields."""
        response = authenticated_client.get("/budget/api/export-data")
        data = response.json()

        assert "date_label" in data
        assert "total_income" in data
        assert "total_expenses" in data
        assert "remaining" in data
        assert "incomes" in data
        assert "category_totals" in data
        assert "expenses_by_category" in data

        assert isinstance(data["date_label"], str)
        assert isinstance(data["total_income"], (int, float))
        assert isinstance(data["total_expenses"], (int, float))
        assert isinstance(data["remaining"], (int, float))
        assert isinstance(data["incomes"], list)
        assert isinstance(data["category_totals"], dict)
        assert isinstance(data["expenses_by_category"], dict)

    def test_export_data_empty_user(self, authenticated_client):
        """New user with no data should return zero values."""
        response = authenticated_client.get("/budget/api/export-data")
        data = response.json()

        assert data["total_income"] == 0
        assert data["total_expenses"] == 0
        assert data["remaining"] == 0
        assert data["incomes"] == []
        assert data["category_totals"] == {}
        assert data["expenses_by_category"] == {}

    def test_export_data_with_data(self, authenticated_client, db_module):
        """Endpoint should return structured data with expenses and income."""
        user_id = authenticated_client.user_id

        db_module.add_income(user_id, "Salary", 30000, "monthly")
        db_module.add_expense(user_id, "Rent", "Bolig", 12000, "monthly")
        db_module.add_expense(user_id, "Car", "Transport", 6000, "yearly")

        response = authenticated_client.get("/budget/api/export-data")
        data = response.json()

        assert data["total_income"] == 30000
        assert data["total_expenses"] == 12500  # 12000 + 6000/12
        assert data["remaining"] == 17500

        # Incomes structure
        assert len(data["incomes"]) == 1
        assert data["incomes"][0]["person"] == "Salary"
        assert data["incomes"][0]["amount"] == 30000

        # Category totals with icons
        assert "Bolig" in data["category_totals"]
        assert data["category_totals"]["Bolig"]["total"] == 12000
        assert "icon" in data["category_totals"]["Bolig"]

        # Expenses by category
        assert "Bolig" in data["expenses_by_category"]
        assert len(data["expenses_by_category"]["Bolig"]) == 1
        assert data["expenses_by_category"]["Bolig"][0]["name"] == "Rent"
        assert data["expenses_by_category"]["Bolig"][0]["amount"] == 12000

    def test_export_data_expense_account_field(self, authenticated_client, db_module):
        """Expenses should include account field (nullable)."""
        user_id = authenticated_client.user_id

        db_module.add_expense(user_id, "Rent", "Bolig", 12000, "monthly", account="Fælleskonto")
        db_module.add_expense(user_id, "Netflix", "Underholdning", 149, "monthly")

        response = authenticated_client.get("/budget/api/export-data")
        data = response.json()

        bolig_expenses = data["expenses_by_category"]["Bolig"]
        assert bolig_expenses[0]["account"] == "Fælleskonto"

        underholdning_expenses = data["expenses_by_category"]["Underholdning"]
        assert underholdning_expenses[0]["account"] is None


class TestExportDataDemoMode:
    """Tests for export data in demo mode."""

    def test_demo_mode_returns_data(self, client):
        """Demo users should be able to use export-data."""
        demo_response = client.get("/budget/demo", follow_redirects=False)
        demo_cookie = demo_response.cookies.get("budget_session")
        client.cookies.set("budget_session", demo_cookie)

        response = client.get("/budget/api/export-data")
        assert response.status_code == 200

        data = response.json()
        assert data["total_income"] > 0
        assert data["total_expenses"] > 0
        assert len(data["incomes"]) > 0
        assert len(data["category_totals"]) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_export.py -q 2>&1 | tail -20`
Expected: FAIL — endpoint does not exist yet (404 or similar)

- [ ] **Step 3: Commit test file**

```bash
git add tests/test_export.py
git commit -m "test: add failing tests for export-data endpoint (#79)"
```

---

### Task 2: Export Data Endpoint — Implementation

**Files:**
- Modify: `src/routes/api_endpoints.py`

- [ ] **Step 1: Implement the export-data endpoint**

Add to `src/routes/api_endpoints.py`, after the `chart_data` endpoint:

Also add these imports at the top of the file (after existing imports):

```python
from datetime import datetime
```

Add this constant after the `router` definition:

```python
DANISH_MONTHS = {
    1: "januar", 2: "februar", 3: "marts", 4: "april",
    5: "maj", 6: "juni", 7: "juli", 8: "august",
    9: "september", 10: "oktober", 11: "november", 12: "december",
}
```

Then add the endpoint:

```python
@router.get("/api/export-data")
async def export_data(request: Request, ctx: DataContext = Depends(get_data)):
    """API endpoint for budget export (image/CSV).

    Returns all budget data as JSON. All amounts are monthly equivalents.
    Auth required — returns only the authenticated user's data.
    """
    now = datetime.now()
    date_label = f"{DANISH_MONTHS[now.month]} {now.year}"

    total_income = ctx.total_income()
    total_expenses = ctx.total_expenses()

    # Incomes with person and monthly amount
    incomes = [
        {"person": inc.person, "amount": inc.monthly_amount, "frequency": inc.frequency}
        for inc in ctx.income()
    ]

    # Category totals with icons
    categories = {cat.name: cat.icon for cat in ctx.categories()}
    raw_totals = ctx.category_totals()
    category_totals = {
        name: {"total": total, "icon": categories.get(name, "tag")}
        for name, total in raw_totals.items()
    }

    # Expenses by category with individual items
    expenses_by_cat = ctx.expenses_by_category()
    expenses_by_category = {
        cat_name: [
            {"name": exp.name, "amount": exp.monthly_amount, "account": exp.account}
            for exp in exps
        ]
        for cat_name, exps in expenses_by_cat.items()
    }

    return {
        "date_label": date_label,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "remaining": round(total_income - total_expenses, 2),
        "incomes": incomes,
        "category_totals": category_totals,
        "expenses_by_category": expenses_by_category,
    }
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_export.py -q 2>&1 | tail -20`
Expected: All tests PASS

- [ ] **Step 3: Run full test suite**

Run: `python3 -m pytest tests/ e2e/ -q 2>&1 | tail -40`
Expected: All tests PASS, no regressions

- [ ] **Step 4: Commit**

```bash
git add src/routes/api_endpoints.py
git commit -m "feat: add /budget/api/export-data endpoint (#79)"
```

---

### Task 3: Export UI — Buttons on Konto Page

**Files:**
- Modify: `templates/settings.html`

Note: "Konto" in the bottom nav links to `/budget/settings` which renders `templates/settings.html`.

- [ ] **Step 1: Add "Eksporter" section to settings.html**

Insert just before the logout `<a>` tag (line 98). Use the standard card pattern:

```html
    <!-- Eksporter -->
    <div class="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm border border-gray-100 dark:border-gray-700 mb-4">
        <h2 class="font-medium text-gray-900 dark:text-white mb-3">Eksporter</h2>
        <div class="space-y-2">
            <button
                id="export-summary-btn"
                onclick="exportBudgetImage('summary')"
                class="w-full text-left px-4 py-3 rounded-lg border border-gray-200 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors flex items-center gap-3"
            >
                <i data-lucide="image" class="w-5 h-5 text-gray-400"></i>
                <div>
                    <div class="text-sm font-medium">Oversigt som billede</div>
                    <div class="text-xs text-gray-400">Kategorier og totaler</div>
                </div>
            </button>
            <button
                id="export-detailed-btn"
                onclick="exportBudgetImage('detailed')"
                class="w-full text-left px-4 py-3 rounded-lg border border-gray-200 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors flex items-center gap-3"
            >
                <i data-lucide="file-image" class="w-5 h-5 text-gray-400"></i>
                <div>
                    <div class="text-sm font-medium">Detaljeret som billede</div>
                    <div class="text-xs text-gray-400">Alle udgifter og indkomster</div>
                </div>
            </button>
        </div>
        <div id="export-error" class="hidden mt-3 bg-red-50 dark:bg-red-900/30 text-red-600 dark:text-red-400 px-3 py-2 rounded-lg text-sm">
            <i data-lucide="alert-circle" class="w-4 h-4 inline mr-1"></i>
            <span id="export-error-text"></span>
        </div>
    </div>
```

- [ ] **Step 2: Verify page renders**

Start the app and check `/budget/settings` — the "Eksporter" section should appear with two buttons above the "Log ud" button.

- [ ] **Step 3: Commit**

```bash
git add templates/settings.html
git commit -m "feat: add export buttons to Konto page (#79)"
```

---

### Task 4: Export JS — Image Generation

**Files:**
- Modify: `templates/settings.html`

**Security note:** All user-provided text (category names, expense names, person names) MUST be HTML-escaped before insertion into innerHTML. Use the `esc()` helper defined below.

- [ ] **Step 1: Add html-to-image CDN and export JS to settings.html**

Replace the existing `<script>` block at the bottom of `settings.html` with a `{% block scripts %}` block containing the CDN script and all export logic:

```html
{% block scripts %}
<script src="https://cdn.jsdelivr.net/npm/html-to-image@1.11.13/dist/html-to-image.js"></script>
<script>
// Lucide init
document.addEventListener('DOMContentLoaded', function() {
    if (typeof lucide !== 'undefined') lucide.createIcons();
});

// --- HTML escape helper (XSS prevention) ---
function esc(str) {
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
}

const EXPORT_COLORS = [
    '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
    '#ec4899', '#14b8a6', '#f97316', '#6366f1', '#84cc16',
    '#06b6d4', '#e11d48'
];

function formatCurrency(amount) {
    return new Intl.NumberFormat('da-DK', {
        style: 'decimal', minimumFractionDigits: 0, maximumFractionDigits: 0
    }).format(Math.round(amount)) + ' kr';
}

async function exportBudgetImage(level) {
    const btn = document.getElementById(
        level === 'summary' ? 'export-summary-btn' : 'export-detailed-btn'
    );
    const originalHTML = btn.innerHTML;
    const errorDiv = document.getElementById('export-error');
    errorDiv.classList.add('hidden');

    btn.disabled = true;
    btn.querySelector('.text-sm').textContent = 'Eksporterer...';

    try {
        const resp = await fetch('/budget/api/export-data');
        if (!resp.ok) throw new Error('Kunne ikke hente data');
        const data = await resp.json();

        const exportDiv = buildExportDiv(data, level);
        document.body.appendChild(exportDiv);

        await renderExportChart(exportDiv, data.category_totals);

        if (typeof lucide !== 'undefined') {
            lucide.createIcons({ nodes: [exportDiv] });
        }

        const blob = await htmlToImage.toBlob(exportDiv, {
            backgroundColor: document.documentElement.classList.contains('dark')
                ? '#111827' : '#ffffff',
            pixelRatio: 2,
        });

        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        const now = new Date();
        const monthStr = String(now.getMonth() + 1).padStart(2, '0');
        const prefix = level === 'summary' ? 'budget-oversigt' : 'budget-detaljer';
        a.href = url;
        a.download = `${prefix}-${now.getFullYear()}-${monthStr}.png`;
        a.click();
        URL.revokeObjectURL(url);

        document.body.removeChild(exportDiv);
    } catch (err) {
        console.error('Export failed:', err);
        document.getElementById('export-error-text').textContent =
            'Eksport fejlede. Prøv igen.';
        errorDiv.classList.remove('hidden');
        if (typeof lucide !== 'undefined') lucide.createIcons();
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalHTML;
        if (typeof lucide !== 'undefined') lucide.createIcons();
    }
}

function summaryCard(label, amount, color, cardBg, borderColor) {
    return `<div style="flex:1;background:${cardBg};border:1px solid ${borderColor};
        border-radius:12px;padding:12px;text-align:center;">
        <div style="font-size:12px;color:${color};margin-bottom:4px;">${esc(label)}</div>
        <div style="font-size:16px;font-weight:700;">${formatCurrency(amount)}</div>
    </div>`;
}

function buildExportDiv(data, level) {
    const isDark = document.documentElement.classList.contains('dark');
    const div = document.createElement('div');
    div.style.cssText = 'position:fixed;left:-9999px;top:0;width:400px;padding:24px;'
        + 'font-family:system-ui,-apple-system,sans-serif;';
    div.style.backgroundColor = isDark ? '#111827' : '#ffffff';
    div.style.color = isDark ? '#f9fafb' : '#111827';

    const textMuted = isDark ? '#9ca3af' : '#6b7280';
    const cardBg = isDark ? '#1f2937' : '#f9fafb';
    const borderColor = isDark ? '#374151' : '#e5e7eb';

    let html = '';

    // Header
    html += `<div style="text-align:center;margin-bottom:20px;">
        <div style="font-size:20px;font-weight:700;">Budget oversigt</div>
        <div style="font-size:14px;color:${textMuted};">${esc(data.date_label)}</div>
    </div>`;

    // Summary cards
    html += `<div style="display:flex;gap:8px;margin-bottom:16px;">`;
    html += summaryCard('Indkomst', data.total_income, '#10b981', cardBg, borderColor);
    html += summaryCard('Udgifter', data.total_expenses, '#ef4444', cardBg, borderColor);
    html += `</div>`;

    // Remaining
    const remainColor = data.remaining >= 0 ? '#10b981' : '#ef4444';
    html += `<div style="background:${cardBg};border:1px solid ${borderColor};
        border-radius:12px;padding:16px;text-align:center;margin-bottom:16px;">
        <div style="font-size:12px;color:${textMuted};margin-bottom:4px;">Til fri brug</div>
        <div style="font-size:24px;font-weight:700;color:${remainColor};">
            ${formatCurrency(data.remaining)}</div>`;
    if (data.total_income > 0) {
        const pct = Math.round((data.remaining / data.total_income) * 100);
        html += `<div style="font-size:12px;color:${textMuted};">${pct}% af indkomst</div>`;
    }
    html += `</div>`;

    // Pie chart placeholder
    html += `<div id="export-chart-container" style="background:${cardBg};
        border:1px solid ${borderColor};border-radius:12px;padding:16px;margin-bottom:16px;">
        <div style="font-size:14px;font-weight:600;margin-bottom:12px;">Udgiftsfordeling</div>
        <div id="export-chart-img" style="text-align:center;"></div>
    </div>`;

    // Category totals
    const catEntries = Object.entries(data.category_totals);
    html += `<div style="background:${cardBg};border:1px solid ${borderColor};
        border-radius:12px;padding:16px;margin-bottom:16px;">
        <div style="font-size:14px;font-weight:600;margin-bottom:12px;">Kategorier</div>`;
    catEntries.forEach(([name, info], i) => {
        const color = EXPORT_COLORS[i % EXPORT_COLORS.length];
        const pct = data.total_expenses > 0
            ? Math.round((info.total / data.total_expenses) * 100) : 0;
        const border = i < catEntries.length - 1
            ? `border-bottom:1px solid ${borderColor};` : '';
        html += `<div style="display:flex;justify-content:space-between;
            align-items:center;padding:8px 0;${border}">
            <div style="display:flex;align-items:center;gap:8px;">
                <div style="width:8px;height:8px;border-radius:50%;background:${color};"></div>
                <span style="font-size:13px;">${esc(name)}</span>
            </div>
            <div style="text-align:right;">
                <span style="font-size:13px;font-weight:500;">${formatCurrency(info.total)}</span>
                <span style="font-size:11px;color:${textMuted};margin-left:6px;">${pct}%</span>
            </div>
        </div>`;
    });
    html += `</div>`;

    // Detailed level: individual expenses + income breakdown
    if (level === 'detailed') {
        if (data.incomes.length > 0) {
            html += `<div style="background:${cardBg};border:1px solid ${borderColor};
                border-radius:12px;padding:16px;margin-bottom:16px;">
                <div style="font-size:14px;font-weight:600;margin-bottom:12px;">Indkomst</div>`;
            data.incomes.forEach((inc, i) => {
                const border = i < data.incomes.length - 1
                    ? `border-bottom:1px solid ${borderColor};` : '';
                html += `<div style="display:flex;justify-content:space-between;
                    padding:6px 0;${border}">
                    <span style="font-size:13px;">${esc(inc.person)}</span>
                    <span style="font-size:13px;font-weight:500;">${formatCurrency(inc.amount)}</span>
                </div>`;
            });
            html += `</div>`;
        }

        Object.entries(data.expenses_by_category).forEach(([catName, expenses]) => {
            html += `<div style="background:${cardBg};border:1px solid ${borderColor};
                border-radius:12px;padding:16px;margin-bottom:16px;">
                <div style="font-size:14px;font-weight:600;margin-bottom:8px;">
                    ${esc(catName)}</div>`;
            expenses.forEach((exp, i) => {
                const border = i < expenses.length - 1
                    ? `border-bottom:1px solid ${borderColor};` : '';
                html += `<div style="display:flex;justify-content:space-between;
                    padding:6px 0;${border}">
                    <span style="font-size:13px;">${esc(exp.name)}</span>
                    <span style="font-size:13px;font-weight:500;">
                        ${formatCurrency(exp.amount)}</span>
                </div>`;
            });
            html += `</div>`;
        });
    }

    // Watermark
    html += `<div style="text-align:center;padding-top:8px;font-size:11px;
        color:${textMuted};opacity:0.6;">${esc(window.location.origin)}</div>`;

    div.innerHTML = html;
    return div;
}

async function renderExportChart(exportDiv, categoryTotals) {
    const entries = Object.entries(categoryTotals);
    if (entries.length === 0) return;

    const canvas = document.createElement('canvas');
    canvas.width = 300;
    canvas.height = 300;
    canvas.style.cssText = 'position:fixed;left:-9999px;';
    document.body.appendChild(canvas);

    const chart = new Chart(canvas, {
        type: 'doughnut',
        data: {
            labels: entries.map(([name]) => name),
            datasets: [{
                data: entries.map(([, info]) => info.total),
                backgroundColor: entries.map((_, i) => EXPORT_COLORS[i % EXPORT_COLORS.length]),
                borderWidth: 0,
            }],
        },
        options: {
            animation: false,
            responsive: false,
            cutout: '60%',
            plugins: { legend: { display: false } },
        },
    });

    const imgSrc = canvas.toDataURL('image/png');
    exportDiv.querySelector('#export-chart-img').innerHTML =
        `<img src="${imgSrc}" style="width:200px;height:200px;margin:0 auto;" />`;

    chart.destroy();
    document.body.removeChild(canvas);
}
</script>
{% endblock %}
```

- [ ] **Step 2: Test manually**

Open `/budget/settings` in browser. Click "Oversigt som billede" — should download a PNG. Click "Detaljeret som billede" — should download a more detailed PNG. Verify:
- Correct data appears
- Pie chart renders
- Dark/light mode is respected
- Watermark shows full URL
- File downloads with correct name format

- [ ] **Step 3: Run full test suite to check for regressions**

Run: `python3 -m pytest tests/ e2e/ -q 2>&1 | tail -40`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add templates/settings.html
git commit -m "feat: add budget image export with html-to-image (#79)"
```

---

### Task 5: E2E Test — Export Buttons on Konto Page

**Files:**
- Modify: find appropriate E2E test file in `e2e/` directory

- [ ] **Step 1: Check existing E2E test structure**

Run: `ls e2e/` and look at an existing E2E test to understand the pattern (fixtures, page navigation, selectors).

- [ ] **Step 2: Add E2E test for export section visibility**

Add a test that verifies:
- The "Eksporter" section is visible on `/budget/settings`
- Both buttons ("Oversigt som billede" and "Detaljeret som billede") are present
- Buttons have correct IDs (`export-summary-btn`, `export-detailed-btn`)

Follow the existing E2E test patterns in the project.

- [ ] **Step 3: Run E2E tests**

Run: `python3 -m pytest e2e/ -q 2>&1 | tail -20`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add e2e/
git commit -m "test: add E2E test for export buttons on Konto page (#79)"
```

---

### Task 6: Final Validation and PR

- [ ] **Step 1: Run full test suite**

Run: `python3 -m pytest tests/ e2e/ -q 2>&1 | tail -40`
Expected: All tests PASS

- [ ] **Step 2: Push and create PR**

```bash
git push -u origin feature/export-budget-image
gh pr create --title "feat: export budget overview as image (#79)" --body "..."
```

Link PR to issue #79.
