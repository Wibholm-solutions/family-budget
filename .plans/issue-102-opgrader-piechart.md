# Issue #102: Opgrader piechart

> **For Claude:** Brug `superpowers:executing-plans` til at implementere denne plan task-by-task.

**Goal:** Moderniser category-chartet fra pie til doughnut med center-tekst, bedre legend og dark mode.

---

## 1. Kontekst

Nuvaerende chart: Chart.js `type: 'pie'`, 8 farver, basal legend (kun navne), beloeb kun i tooltip.

## 2. Design: Behold Chart.js, opgrader konfiguration

**Behold Chart.js** - allerede loaded, har doughnut built-in, center-label plugin. Intet nyt library.

## 3. Implementation steps

### Step 1: Pie -> Doughnut (`templates/dashboard.html`, linje 543-621)

- AEndr `type: 'pie'` til `type: 'doughnut'`
- Tilfoej `cutout: '60%'`
- Tilfoej hover: `hoverOffset: 8, hoverBorderWidth: 3`
- Border: `borderWidth: 2, borderColor: isDark ? '#1f2937' : '#ffffff'`

### Step 2: Udvid farvepalette til 12

```javascript
const chartColors = [
    '#3b82f6', '#10b981', '#f59e0b', '#ef4444',
    '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16',
    '#f97316', '#14b8a6', '#6366f1', '#a855f7',
];
```

### Step 3: Center-tekst plugin

Inline Chart.js plugin der viser "Total" + formateret beloeb i doughnut-centrum.

```javascript
const centerTextPlugin = {
    id: 'centerText',
    afterDraw(chart) {
        if (chart.config.type !== 'doughnut') return;
        const { ctx, chartArea } = chart;
        const centerX = (chartArea.left + chartArea.right) / 2;
        const centerY = (chartArea.top + chartArea.bottom) / 2;
        const total = chart.data.datasets[0].data.reduce((a, b) => a + b, 0);
        const isDark = document.documentElement.classList.contains('dark');
        ctx.save();
        ctx.textAlign = 'center';
        ctx.font = '12px system-ui';
        ctx.fillStyle = isDark ? '#9ca3af' : '#6b7280';
        ctx.fillText('Total', centerX, centerY - 10);
        ctx.font = 'bold 16px system-ui';
        ctx.fillStyle = isDark ? '#f3f4f6' : '#111827';
        ctx.fillText(formatCurrency(total), centerX, centerY + 12);
        ctx.restore();
    }
};
Chart.register(centerTextPlugin);
```

### Step 4: Legend med beloeb og procent

`generateLabels` callback der viser `"Kategori: 5.000 kr (25%)"` i stedet for bare "Kategori".

### Step 5: Tom-tilstand

Erstat `<p>Ingen data</p>` med visuelt placeholder (ikon + tekst), matchende dashboard-stil.

### Step 6: Forhoej chart-hoejde

`h-64` -> `h-80` for plads til udvidet legend.

## 4. Acceptkriterier

1. Doughnut med centreret total i midten
2. Hover-animation paa segmenter
3. 12 farver fra Tailwind-palette
4. Legend viser beloeb + procent direkte
5. Korrekt i baade light og dark mode
6. Poleret tom-tilstand

## 5. Test plan

- Opdater E2E: empty state tekst aendres
- Nye E2E: legend viser beloeb, dark mode renders
- Manuel: check paa mobil viewport, hover animation
