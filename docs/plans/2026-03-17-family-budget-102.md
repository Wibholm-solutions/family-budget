# Upgrade Piechart (Issue #102) Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers-extended-cc:subagent-driven-development (if subagents available) or superpowers-extended-cc:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the dashboard expense chart from a basic pie chart to a polished doughnut chart with a centered total, hover animations, an extended color palette, a custom legend showing amounts and percentages, and a proper empty state.

**Architecture:** All changes are purely frontend in `templates/dashboard.html` — the Chart.js config and rendering logic in the `{% block scripts %}` section is replaced with doughnut-type configuration, a custom center-text plugin, and a custom HTML legend rendered below the canvas via safe DOM methods. One E2E test needs updating to reflect the new empty state text.

**Tech Stack:** Chart.js (CDN, already loaded), Tailwind CSS (CDN), Lucide icons (CDN), Jinja2 templates, Playwright (E2E tests)

---

## Chunk 1: Core Doughnut Chart (type, colors, hover, center text)

### Task 1: Write failing E2E test for custom legend

**Files:**
- Modify: `e2e/test_charts.py`

- [ ] **Step 1: Add tests to `TestDemoCharts` class**

In `e2e/test_charts.py`, add two new test methods to the `TestDemoCharts` class:

```python
def test_demo_chart_has_custom_legend(self, page: Page, base_url: str):
    """Doughnut chart should have a custom legend div below the canvas."""
    page.goto(f"{base_url}/budget/demo")
    page.wait_for_url(f"{base_url}/budget/")
    page.wait_for_timeout(1000)

    legend = page.locator("#chart-legend")
    expect(legend).to_be_visible()

def test_demo_chart_legend_has_percentage(self, page: Page, base_url: str):
    """Custom legend should show percentage values."""
    page.goto(f"{base_url}/budget/demo")
    page.wait_for_url(f"{base_url}/budget/")
    page.wait_for_timeout(1500)

    legend_text = page.locator("#chart-legend").text_content()
    assert legend_text is not None
    assert "%" in legend_text
```

- [ ] **Step 2: Run new tests to confirm they FAIL**

```bash
cd /home/saabendtsen/projects/family-budget
venv/bin/pytest e2e/test_charts.py::TestDemoCharts::test_demo_chart_has_custom_legend e2e/test_charts.py::TestDemoCharts::test_demo_chart_legend_has_percentage -v
```

Expected: Both tests FAIL — element `#chart-legend` does not exist yet.

- [ ] **Step 3: Commit failing tests**

```bash
git add e2e/test_charts.py
git commit -m "test: add failing e2e tests for doughnut chart legend (issue #102)"
```

---

### Task 2: Implement doughnut chart with center text, hover animation, and custom legend

**Files:**
- Modify: `templates/dashboard.html`
  - Chart canvas container HTML (~line 232)
  - JavaScript chart section (~lines 546-620)

- [ ] **Step 1: Update canvas container in dashboard.html**

Find this block (around line 232):
```html
<div class="h-64">
    <canvas id="chart-categories"></canvas>
</div>
```

Replace with:
```html
<div class="h-52">
    <canvas id="chart-categories"></canvas>
</div>
<div id="chart-legend" class="mt-3 space-y-0.5 max-h-32 overflow-y-auto"></div>
```

Height reduced from `h-64` to `h-52` to make room for the legend while keeping total card height comfortable.

- [ ] **Step 2: Replace the chart JavaScript section**

In `templates/dashboard.html`, replace from `// Color palette for charts` down to the closing `}` of `renderCategoryChart` (approximately lines 546–619) with:

```javascript
// Extended harmonious color palette (12 colors, Tailwind-aligned)
const chartColors = [
    '#3b82f6', // blue-500
    '#10b981', // emerald-500
    '#f59e0b', // amber-500
    '#8b5cf6', // violet-500
    '#06b6d4', // cyan-500
    '#ec4899', // pink-500
    '#84cc16', // lime-500
    '#f97316', // orange-500
    '#14b8a6', // teal-500
    '#a855f7', // purple-500
    '#ef4444', // red-500
    '#64748b', // slate-500
];

// Custom center text plugin: draws "Total" label + formatted total inside the doughnut hole
const centerTextPlugin = {
    id: 'centerText',
    afterDraw(chart) {
        if (chart.config.type !== 'doughnut') return;
        const { ctx, chartArea } = chart;
        if (!chartArea) return;
        const centerX = (chartArea.left + chartArea.right) / 2;
        const centerY = (chartArea.top + chartArea.bottom) / 2;
        const isDark = document.documentElement.classList.contains('dark');

        ctx.save();

        ctx.font = '11px system-ui, sans-serif';
        ctx.fillStyle = isDark ? '#9ca3af' : '#6b7280';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('Total', centerX, centerY - 12);

        const total = chart.config.data.datasets[0].data.reduce((a, b) => a + b, 0);
        ctx.font = 'bold 14px system-ui, sans-serif';
        ctx.fillStyle = isDark ? '#f9fafb' : '#111827';
        ctx.fillText(formatCurrency(total), centerX, centerY + 8);

        ctx.restore();
    }
};

function renderCategoryChart(categoryTotals) {
    const ctx = document.getElementById('chart-categories');
    if (!ctx) return;

    const labels = Object.keys(categoryTotals);
    const values = Object.values(categoryTotals);
    const total = values.reduce((a, b) => a + b, 0);

    // Empty state: design-guide pattern (icon + text)
    if (total === 0) {
        const container = ctx.parentElement;
        container.replaceChildren(); // clear canvas

        const wrapper = document.createElement('div');
        wrapper.className = 'flex flex-col items-center justify-center h-full py-6 text-center';

        const iconBox = document.createElement('div');
        iconBox.className = 'w-12 h-12 bg-gray-100 dark:bg-gray-700 rounded-full flex items-center justify-center mb-3';
        const icon = document.createElement('i');
        icon.setAttribute('data-lucide', 'pie-chart');
        icon.className = 'w-6 h-6 text-gray-400';
        iconBox.appendChild(icon);

        const title = document.createElement('p');
        title.className = 'text-sm font-medium text-gray-500 dark:text-gray-400';
        title.textContent = 'Ingen udgifter endnu';

        const sub = document.createElement('p');
        sub.className = 'text-xs text-gray-400 dark:text-gray-500 mt-1';
        sub.textContent = 'Tilføj udgifter for at se fordelingen';

        wrapper.appendChild(iconBox);
        wrapper.appendChild(title);
        wrapper.appendChild(sub);
        container.appendChild(wrapper);
        lucide.createIcons();
        return;
    }

    if (categoryChart) categoryChart.destroy();

    const isDark = document.documentElement.classList.contains('dark');

    categoryChart = new Chart(ctx, {
        type: 'doughnut',
        plugins: [centerTextPlugin],
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: chartColors.slice(0, labels.length),
                borderWidth: 2,
                borderColor: isDark ? '#1f2937' : '#ffffff',
                hoverOffset: 12,
                hoverBorderWidth: 2,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '65%',
            animation: { animateRotate: true, animateScale: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const value = context.raw;
                            const percentage = ((value / total) * 100).toFixed(1);
                            return `${context.label}: ${formatCurrency(value)} (${percentage}%)`;
                        }
                    }
                }
            }
        }
    });

    renderChartLegend(labels, values, total);
}

// Builds legend rows using safe DOM methods (avoids XSS from category names)
function renderChartLegend(labels, values, total) {
    const legend = document.getElementById('chart-legend');
    if (!legend) return;

    legend.replaceChildren(); // clear previous

    labels.forEach((label, i) => {
        const value = values[i];
        const pct = ((value / total) * 100).toFixed(1);
        const color = chartColors[i % chartColors.length];

        const row = document.createElement('div');
        row.className = 'flex items-center justify-between gap-2 py-1';

        const left = document.createElement('div');
        left.className = 'flex items-center gap-2 min-w-0';

        const swatch = document.createElement('span');
        swatch.className = 'w-2.5 h-2.5 rounded-full flex-shrink-0';
        swatch.style.backgroundColor = color;

        const name = document.createElement('span');
        name.className = 'text-xs text-gray-600 dark:text-gray-400 truncate';
        name.textContent = label; // textContent — safe, no XSS

        left.appendChild(swatch);
        left.appendChild(name);

        const right = document.createElement('div');
        right.className = 'flex items-center gap-2 flex-shrink-0 text-xs tabular-nums';

        const pctSpan = document.createElement('span');
        pctSpan.className = 'text-gray-500 dark:text-gray-500';
        pctSpan.textContent = pct + '%';

        const amtSpan = document.createElement('span');
        amtSpan.className = 'font-medium text-gray-900 dark:text-white';
        amtSpan.textContent = formatCurrency(value);

        right.appendChild(pctSpan);
        right.appendChild(amtSpan);

        row.appendChild(left);
        row.appendChild(right);
        legend.appendChild(row);
    });
}
```

- [ ] **Step 3: Run failing E2E tests — expect them to now pass**

```bash
cd /home/saabendtsen/projects/family-budget
venv/bin/pytest e2e/test_charts.py::TestDemoCharts -v
```

Expected: All `TestDemoCharts` tests PASS.

- [ ] **Step 4: Run full E2E chart suite**

```bash
venv/bin/pytest e2e/test_charts.py -v 2>&1 | tail -30
```

Expected: All pass except `test_chart_section_renders_for_new_user` (will be fixed in Task 3).

- [ ] **Step 5: Commit**

```bash
git add templates/dashboard.html
git commit -m "feat: upgrade pie chart to doughnut with center total, hover, extended palette, custom legend (#102)"
```

---

## Chunk 2: Empty State + E2E Fix

### Task 3: Update empty state E2E test

**Files:**
- Modify: `e2e/test_charts.py`

- [ ] **Step 1: Update the empty state test in `TestChartRendering`**

Find `test_chart_section_renders_for_new_user`:

```python
def test_chart_section_renders_for_new_user(self, authenticated_page: Page, base_url: str):
    """Chart section should render even for new users without data."""
    authenticated_page.goto(f"{base_url}/budget/")

    # Empty user shows "Ingen data" for category chart
    expect(authenticated_page.locator("text=Ingen data")).to_be_visible()
```

Replace the assertion body with:

```python
def test_chart_section_renders_for_new_user(self, authenticated_page: Page, base_url: str):
    """Chart section should render empty state placeholder for users without data."""
    authenticated_page.goto(f"{base_url}/budget/")

    # Empty state shows icon + descriptive text
    expect(authenticated_page.locator("text=Ingen udgifter endnu")).to_be_visible()
```

- [ ] **Step 2: Run full E2E chart suite**

```bash
cd /home/saabendtsen/projects/family-budget
venv/bin/pytest e2e/test_charts.py -v 2>&1 | tail -30
```

Expected: ALL tests PASS.

- [ ] **Step 3: Run full unit test suite**

```bash
venv/bin/pytest tests/ -v 2>&1 | tail -30
```

Expected: ALL tests PASS. No backend changes were made so `tests/test_charts.py` is unaffected.

- [ ] **Step 4: Commit**

```bash
git add e2e/test_charts.py
git commit -m "test: update empty state assertion for upgraded doughnut chart (#102)"
```

---

## Chunk 3: PR

### Task 4: Create pull request

- [ ] **Step 1: Push branch**

```bash
cd /home/saabendtsen/projects/family-budget
git push origin HEAD
```

- [ ] **Step 2: Create PR**

```bash
gh pr create \
  --repo saabendtsen/family-budget \
  --title "feat: upgrade pie chart to doughnut with legend, hover, and empty state (#102)" \
  --body "## Changes

Upgrades the expense distribution chart on the dashboard:

- **Doughnut variant** with 65% cutout and centered total amount (custom Chart.js plugin)
- **Hover animation**: segments offset outward 12px on hover
- **Extended palette**: 12 harmonious Tailwind-aligned colors (was 8)
- **Custom HTML legend**: color swatch, category name, %, and amount per row
- **Empty state**: pie-chart icon + descriptive text, matches dashboard design system
- **Dark mode**: center text color, border color, and legend text all adapt to dark mode

All changes are frontend-only (templates/dashboard.html). API contract unchanged.

Closes #102"
```

---

## Summary

| Task | File(s) | Type |
|------|---------|------|
| 1: Failing E2E tests | `e2e/test_charts.py` | test |
| 2: Doughnut + legend implementation | `templates/dashboard.html` | feat |
| 3: Empty state E2E fix | `e2e/test_charts.py` | test fix |
| 4: PR | — | infra |

**Run all tests:**
```bash
cd /home/saabendtsen/projects/family-budget
venv/bin/pytest tests/ e2e/test_charts.py -v
```

**Key constraints:**
- No backend changes — API contract (`/budget/api/chart-data`) is unchanged
- Chart.js loaded from CDN — no build step required
- Legend built with `textContent` / DOM methods — no XSS risk from user-supplied category names
- `centerTextPlugin` defined inline before `renderCategoryChart` to keep scope clean
- `formatCurrency` defined earlier in the same `<script>` block and available
