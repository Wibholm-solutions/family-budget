# Design Guide for Simple Web Apps

Dette er et genbrugeligt design system til simple web apps, baseret på family-budget's visuelle identitet.

**Reference implementation:** family-budget appen (`<project-root>`)

## Hvornår bruges denne guide?

- Når du bygger nye simple web apps med TailwindCSS
- Når du vil have et konsistent visuelt udtryk på tværs af apps
- Når du har brug for copy-paste komponenter til hurtig prototyping

**Hvad denne guide IKKE er:**
- Ikke til komplekse web applications med custom design systems
- Ikke til apps der kræver unique branding

---

## Foundation

### Farvepalette

```javascript
// TailwindCSS config (inject via CDN)
tailwind.config = {
    darkMode: 'class',
    theme: {
        extend: {
            colors: {
                primary: '#3b82f6',    // blue-500
                success: '#10b981',    // emerald-500
                danger: '#ef4444',     // red-500
            }
        }
    }
}
```

**Anvendelse:**
- **Primary (blue):** Primære actions, active states, links
- **Success (green):** Positive metrics, success messages, income
- **Danger (red):** Errors, warnings, destructive actions, expenses
- **Grays:** Text, backgrounds, borders

**Gray scale:**
- Text: `text-gray-900 dark:text-white` (headings), `text-gray-600 dark:text-gray-400` (body)
- Backgrounds: `bg-gray-50 dark:bg-gray-900` (page), `bg-white dark:bg-gray-800` (cards)
- Borders: `border-gray-200 dark:border-gray-700`

### Typografi

**Font stack:** TailwindCSS default system fonts

**Sizes:**
- `text-xs` (12px) - Small labels, metadata
- `text-sm` (14px) - Secondary text, buttons
- `text-base` (16px) - Body text
- `text-lg` (18px) - Card values
- `text-2xl` (24px) - Page headings
- `text-3xl` (30px) - Featured metrics

**Weights:**
- `font-medium` (500) - Emphasized text
- `font-bold` (700) - Headings
- `font-semibold` (600) - Subheadings

### Spacing & Layout

**Standard spacing patterns:**
- Card padding: `p-4` (standard), `p-6` (spacious)
- Element gaps: `gap-2`, `gap-3` (small), `gap-4`, `gap-6` (large)
- Section margins: `mb-3`, `mb-6`
- Page padding: `px-4 py-6`

**Border radius:**
- Standard: `rounded-xl` (12px)
- Featured/cards: `rounded-2xl` (16px)
- Buttons: `rounded-lg` (8px)

**Shadows:**
- Cards: `shadow-sm`
- Featured elements: `shadow-lg`

**Container:**
- Max width: `max-w-md` (mobile-first, 448px)
- Centered: `mx-auto`

---

## Components

### Cards

#### Standard Card
```html
<div class="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm border border-gray-100 dark:border-gray-700">
    <h3 class="font-medium text-gray-900 dark:text-white mb-2">Card Title</h3>
    <p class="text-gray-600 dark:text-gray-400 text-sm">Card content goes here</p>
</div>
```

#### Clickable Card (Hover Effect)
```html
<a href="/destination" class="block bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm border border-gray-100 dark:border-gray-700 hover:border-primary dark:hover:border-primary transition-colors group">
    <div class="flex justify-between items-center">
        <div>
            <h3 class="font-medium text-gray-900 dark:text-white">Card Title</h3>
            <p class="text-gray-600 dark:text-gray-400 text-sm">Subtitle</p>
        </div>
        <i data-lucide="chevron-right" class="w-4 h-4 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity"></i>
    </div>
</a>
```

#### Featured Card (Gradient)
```html
<div class="bg-gradient-to-r from-emerald-500 to-green-600 rounded-2xl p-6 text-white shadow-lg">
    <div class="text-sm opacity-90 mb-1">Label</div>
    <div class="text-3xl font-bold">Main Value</div>
    <div class="text-sm opacity-75 mt-2">Secondary info</div>
</div>
```

**Gradient variations:**
- Success: `from-emerald-500 to-green-600`
- Error: `from-red-500 to-rose-600`
- Primary: `from-blue-500 to-indigo-600`

#### Grid Cards (Summary/Metrics)
```html
<div class="grid grid-cols-2 gap-3">
    <div class="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm border border-gray-100 dark:border-gray-700">
        <div class="flex items-center gap-2 text-gray-500 dark:text-gray-400 text-sm mb-1">
            <i data-lucide="trending-up" class="w-4 h-4 text-success"></i>
            Label
        </div>
        <div class="text-lg font-bold text-gray-900 dark:text-white">25.000 kr</div>
    </div>
    <!-- Repeat for second card -->
</div>
```

### Buttons

#### Primary Button
```html
<button class="w-full bg-primary text-white py-3 rounded-xl font-medium hover:bg-blue-600 active:bg-blue-700 transition-colors">
    Primary Action
</button>
```

#### Secondary Button
```html
<button class="w-full bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 py-3 rounded-xl font-medium hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors">
    Secondary Action
</button>
```

#### Icon Button
```html
<button class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors">
    <i data-lucide="settings" class="w-5 h-5"></i>
</button>
```

#### Small Button (in cards)
```html
<button class="text-sm text-primary hover:text-blue-600 flex items-center gap-1 transition-colors">
    Action
    <i data-lucide="chevron-right" class="w-3 h-3"></i>
</button>
```

### Form Inputs

#### Text Input
```html
<input
    type="text"
    placeholder="Placeholder"
    class="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-xl focus:ring-2 focus:ring-primary focus:border-transparent outline-none bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
>
```

#### Select Dropdown
```html
<select class="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-xl focus:ring-2 focus:ring-primary focus:border-transparent outline-none bg-white dark:bg-gray-800 text-gray-900 dark:text-white cursor-pointer">
    <option>Option 1</option>
    <option>Option 2</option>
</select>
```

#### Small Select (filter/sort)
```html
<select class="text-sm bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 px-3 py-1.5 rounded-lg border-0 focus:ring-2 focus:ring-primary outline-none cursor-pointer">
    <option>Sort option</option>
</select>
```

### Bottom Navigation

```html
<nav class="fixed bottom-0 left-0 right-0 bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 px-4 py-2">
    <div class="max-w-md mx-auto">
        <div class="flex justify-around items-center">
            <!-- Active nav item -->
            <a href="/dashboard" class="nav-item flex flex-col items-center py-2 px-4 rounded-lg text-primary bg-blue-50 dark:bg-blue-900/30">
                <i data-lucide="layout-dashboard" class="w-6 h-6"></i>
                <span class="text-xs mt-1">Oversigt</span>
            </a>
            <!-- Inactive nav item -->
            <a href="/settings" class="nav-item flex flex-col items-center py-2 px-4 rounded-lg text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200">
                <i data-lucide="settings" class="w-6 h-6"></i>
                <span class="text-xs mt-1">Indstillinger</span>
            </a>
        </div>
    </div>
</nav>

<!-- Add bottom padding to page to prevent content hiding under nav -->
<body class="pb-20">
```

**CSS for smooth transitions:**
```css
.nav-item { transition: all 0.2s ease; }
```

### Empty States

```html
<div class="bg-white dark:bg-gray-800 rounded-xl p-8 text-center shadow-sm border border-gray-100 dark:border-gray-700">
    <div class="w-12 h-12 bg-gray-100 dark:bg-gray-700 rounded-full flex items-center justify-center mx-auto mb-4">
        <i data-lucide="inbox" class="w-6 h-6 text-gray-400"></i>
    </div>
    <h3 class="font-medium text-gray-900 dark:text-white mb-1">No Items Yet</h3>
    <p class="text-gray-500 dark:text-gray-400 text-sm mb-4">Add your first item to get started</p>
    <a href="/add" class="inline-block bg-primary text-white px-4 py-2 rounded-lg text-sm font-medium">
        Add Item
    </a>
</div>
```

### Banners & Alerts

#### Info Banner
```html
<div class="bg-amber-500 text-amber-900 px-4 py-2 text-center text-sm font-medium">
    <i data-lucide="info" class="w-4 h-4 inline mr-1"></i>
    Information message here
</div>
```

#### Error Message
```html
<div class="bg-red-50 dark:bg-red-900/30 text-red-600 dark:text-red-400 px-4 py-3 rounded-xl text-center text-sm">
    Error message here
</div>
```

---

## Patterns & Principles

### Dark Mode Strategy

**ALWAYS include dark mode variants:**
- Backgrounds: `bg-white dark:bg-gray-800`
- Text: `text-gray-900 dark:text-white`
- Borders: `border-gray-200 dark:border-gray-700`

**Set dark mode by default:**
```html
<html lang="da" class="dark">
```

### Mobile-First Approach

**Container pattern:**
```html
<div class="max-w-md mx-auto px-4 py-6">
    <!-- Content -->
</div>
```

**Bottom navigation** instead of top navigation for mobile ergonomics.

**Touch-friendly targets:** Minimum `py-3` for buttons, `py-2` for clickable elements.

### Hover States & Transitions

**Standard transition:**
```css
transition-colors  /* For color changes */
transition-all     /* For multiple properties */
```

**Hover patterns:**
- Links: `hover:text-primary`
- Buttons: `hover:bg-blue-600`
- Cards: `hover:border-primary`
- Icons: `hover:text-gray-600 dark:hover:text-gray-300`

**Active state for tactile feedback:**
```css
active:bg-blue-700
active:scale-98  /* Custom via card class */
```

### Icon Usage

**Lucide icons:**
```html
<script src="https://unpkg.com/lucide@latest"></script>
```

**Standard sizes:**
- Small: `w-4 h-4`
- Medium: `w-5 h-5`
- Large: `w-6 h-6`
- Hero/featured: `w-8 h-8`

**Initialize at page bottom:**
```html
<script>
    lucide.createIcons();
</script>
```

**Common icon colors:**
- Success: `text-success`
- Danger: `text-danger`
- Muted: `text-gray-400`
- Primary: `text-primary`

### Layout & Spacing Conventions

**Page structure:**
```html
<body class="bg-gray-50 dark:bg-gray-900 min-h-screen pb-20">
    <div class="max-w-md mx-auto px-4 py-6">
        <!-- Header -->
        <div class="flex justify-between items-center mb-6">
            <h1 class="text-2xl font-bold text-gray-900 dark:text-white">Page Title</h1>
        </div>

        <!-- Content sections with mb-6 -->
        <section class="mb-6">...</section>
        <section class="mb-6">...</section>
    </div>
</body>
```

**Consistent spacing:**
- Between major sections: `mb-6`
- Between cards in grid: `gap-3`
- Within cards: `mb-2` or `mb-3`
- List items: `space-y-2` or `space-y-3`

---

## Base Template Setup

### HTML Skeleton

```html
<!DOCTYPE html>
<html lang="da" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>App Name</title>

    <!-- TailwindCSS CDN -->
    <script src="https://cdn.tailwindcss.com"></script>

    <!-- Lucide Icons -->
    <script src="https://unpkg.com/lucide@latest"></script>

    <!-- TailwindCSS Config -->
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    colors: {
                        primary: '#3b82f6',
                        success: '#10b981',
                        danger: '#ef4444',
                    }
                }
            }
        }
    </script>

    <!-- Custom Transitions -->
    <style>
        .nav-item { transition: all 0.2s ease; }
        .card { transition: transform 0.2s ease, box-shadow 0.2s ease; }
        .card:active { transform: scale(0.98); }
    </style>
</head>
<body class="bg-gray-50 dark:bg-gray-900 min-h-screen pb-20">
    <!-- Your content -->

    <!-- Bottom Navigation (if needed) -->
    <nav class="fixed bottom-0 left-0 right-0 bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 px-4 py-2">
        <!-- Nav items -->
    </nav>

    <!-- Initialize Lucide -->
    <script>
        lucide.createIcons();
    </script>
</body>
</html>
```

---

## Best Practices

### Semantic HTML
- Use `<nav>`, `<section>`, `<article>` where appropriate
- Use `<button>` for actions, `<a>` for navigation
- Include `aria-label` for icon-only buttons

### Consistent Border Radius
- Small elements (badges, pills): `rounded-lg`
- Standard elements (cards, inputs): `rounded-xl`
- Featured elements: `rounded-2xl`
- Icons/avatars: `rounded-full`

### Focus States
Always include focus states for accessibility:
```html
focus:ring-2 focus:ring-primary focus:border-transparent outline-none
```

### Testing Checklist
- [ ] Test på mobile viewport (max-w-md)
- [ ] Test dark mode (`class="dark"` on `<html>`)
- [ ] Test hover states på alle interactive elements
- [ ] Test focus states med keyboard navigation
- [ ] Verificer at Lucide icons renderer korrekt

---

## Reference Files

For konkrete eksempler, se:
- `<project-root>/templates/base.html` - Base template setup
- `<project-root>/templates/dashboard.html` - Card layouts, navigation
- `<project-root>/templates/login.html` - Forms, buttons

---

**Version:** 1.0
**Last updated:** 2026-02-14
**Maintained by:** Søren Bendtsen
