# Eksporter budget overblik som billede — Design Spec

**Date:** 2026-03-25
**Issue:** #79
**Scope:** Tilføj mulighed for at eksportere budget-oversigt som PNG-billede fra Konto-siden

---

## Oversigt

Brugere kan eksportere deres budget-oversigt som et mobilvenligt PNG-billede til deling på Reddit, besked-apps, email m.m. Eksport sker client-side via `html-to-image` library. To detaljeniveauer: oversigt (kategori-totaler) og detaljeret (individuelle poster).

## UI Placering

Eksport-knapper placeres på **Konto-siden** (`/budget/settings`, template: `templates/settings.html`) som en "Eksporter"-sektion. Dette holder dashboardet rent og giver plads til fremtidige eksport-formater (CSV).

```
Eksporter
[Oversigt som billede]
[Detaljeret som billede]
```

Knapperne trigger direkte PNG-download — ingen preview, ingen modal.

## Detaljeniveauer

### Oversigt-niveau
- Titel + dato (fx "Budget oversigt — marts 2026")
- Total indkomst, total udgifter, til fri brug
- Kategori-totaler med ikoner
- Pie chart (doughnut) med udgiftsfordeling
- Watermark: fuld URL i bunden

### Detaljeret niveau
Alt fra oversigt, plus:
- Individuelle udgifter under hver kategori (navn + beløb)
- Indkomstfordeling per person

## Teknisk Tilgang

### Library
`html-to-image` via CDN. Bruger `toBlob()` til at rendere et skjult `<div>` til PNG.

### Data
Nyt API-endpoint: `GET /budget/api/export-data`

- Beskyttet med `require_auth` — returnerer KUN aktiv brugers data via `user_id` fra session
- Ingen parameter til at angive anden bruger
- Returnerer alt data til begge niveauer i ét kald:
  - `incomes`: liste med person, beløb, frekvens
  - `expenses_by_category`: dict med kategori → liste af udgifter (navn, beløb, konto)
  - `category_totals`: dict med kategori → total
  - `total_income`, `total_expenses`, `remaining`
  - `date_label`: formateret dato-label (fx "marts 2026")
- Designet til genbrug for fremtidig CSV-eksport
- Demo-brugere kan eksportere (read-only operation, bruger `Depends(get_data)` som håndterer demo-mode transparent)

**Eksempel-response:**
```json
{
  "date_label": "marts 2026",
  "total_income": 45000.0,
  "total_expenses": 32000.0,
  "remaining": 13000.0,
  "incomes": [
    {"person": "Anders", "amount": 25000.0, "frequency": "monthly"},
    {"person": "Mette", "amount": 20000.0, "frequency": "monthly"}
  ],
  "category_totals": {
    "Bolig": {"total": 12000.0, "icon": "home"},
    "Transport": {"total": 4500.0, "icon": "car"},
    "Mad": {"total": 6000.0, "icon": "utensils"}
  },
  "expenses_by_category": {
    "Bolig": [
      {"name": "Husleje", "amount": 10000.0, "account": "Fælleskonto"},
      {"name": "Forsikring", "amount": 2000.0, "account": null}
    ]
  }
}
```

Alle beløb er månedsnormaliserede (`monthly_amount`). `account` kan være `null` — vises som tom i eksport.

### Eksport-flow
1. Bruger klikker "Oversigt som billede" eller "Detaljeret som billede"
2. JavaScript fetcher `/budget/api/export-data`
3. Bygger skjult `<div>` med dedikeret eksport-layout (ikke screenshot af eksisterende UI)
4. Pie chart: opret midlertidig `<canvas>`, instansier Chart.js med `animation: false`, kald `canvas.toDataURL()` → `<img>` i eksport-div
5. Lucide-ikoner: kald `lucide.createIcons()` på eksport-div'en så SVG-ikoner renderes korrekt
6. `htmlToImage.toBlob(div)` → `URL.createObjectURL()` → trigger download via `<a>` element
7. Rydder op: fjerner skjult div + midlertidig canvas fra DOM

**Fejlhåndtering:**
- Fetch-fejl (401, 500, netværk): vis kort fejlbesked til brugeren, ingen download
- `htmlToImage.toBlob()` fejl: vis fejlbesked, ryd op
- Loading-state: knappen viser "Eksporterer..." mens render kører

### Layout
- Smal bredde (~400px) — optimeret til mobil-feeds (Reddit, besked-apps)
- Portrait-orientering
- Respekterer brugerens dark/light mode — eksport-div arver `dark` klasse fra `<html>` (Tailwind `darkMode: 'class'`)
- Filnavn: `budget-oversigt-2026-03.png` / `budget-detaljer-2026-03.png`

## Filer der ændres

| Fil | Ændring |
|-----|---------|
| `templates/settings.html` | Tilføj "Eksporter"-sektion med knapper, eksport-JS, og `html-to-image` CDN (kun denne side) |
| `src/routes/api_endpoints.py` | Nyt `GET /budget/api/export-data` endpoint |

## Sikkerhed

- Endpoint bruger `require_auth` dependency — session-baseret autentificering
- `user_id` hentes fra session, aldrig fra request-parametre
- Ingen mulighed for at tilgå andre brugeres data

## Test

- Unit test: `/budget/api/export-data` returnerer korrekt JSON-struktur for autentificeret bruger
- Unit test: endpoint afviser uautentificerede requests
- E2E test: "Eksporter"-sektion vises på Konto-siden med begge knapper

## Fremtidig udvidelse

- CSV-eksport kan tilføjes som ekstra knapper i samme sektion, genbruger `/budget/api/export-data`
- Yderligere formater (PDF) kan tilføjes efter samme mønster
