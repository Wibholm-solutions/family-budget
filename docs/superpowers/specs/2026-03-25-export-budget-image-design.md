# Eksporter budget overblik som billede — Design Spec

**Date:** 2026-03-25
**Issue:** #79
**Scope:** Tilføj mulighed for at eksportere budget-oversigt som PNG-billede fra Konto-siden

---

## Oversigt

Brugere kan eksportere deres budget-oversigt som et mobilvenligt PNG-billede til deling på Reddit, besked-apps, email m.m. Eksport sker client-side via `html-to-image` library. To detaljeniveauer: oversigt (kategori-totaler) og detaljeret (individuelle poster).

## UI Placering

Eksport-knapper placeres på **Konto-siden** (`/budget/account`) som en "Eksporter"-sektion. Dette holder dashboardet rent og giver plads til fremtidige eksport-formater (CSV).

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
  - `period`: aktiv periode (month/year)
  - `date_label`: formateret dato-label
- Designet til genbrug for fremtidig CSV-eksport

### Eksport-flow
1. Bruger klikker "Oversigt som billede" eller "Detaljeret som billede"
2. JavaScript fetcher `/budget/api/export-data`
3. Bygger skjult `<div>` med dedikeret eksport-layout (ikke screenshot af eksisterende UI)
4. Pie chart: renderer Chart.js doughnut canvas → `toDataURL()` → `<img>` i eksport-div
5. `htmlToImage.toBlob(div)` → `URL.createObjectURL()` → trigger download via `<a>` element
6. Rydder op: fjerner skjult div fra DOM

### Layout
- Smal bredde (~400px) — optimeret til mobil-feeds (Reddit, besked-apps)
- Portrait-orientering
- Respekterer brugerens dark/light mode
- Filnavn: `budget-oversigt-2026-03.png` / `budget-detaljer-2026-03.png`

## Filer der ændres

| Fil | Ændring |
|-----|---------|
| `templates/account.html` | Tilføj "Eksporter"-sektion med to knapper + eksport-JS |
| `src/routes/api_endpoints.py` | Nyt `GET /budget/api/export-data` endpoint |
| `templates/base.html` | Tilføj `html-to-image` CDN script-tag |

## Sikkerhed

- Endpoint bruger `require_auth` dependency — session-baseret autentificering
- `user_id` hentes fra session, aldrig fra request-parametre
- Ingen mulighed for at tilgå andre brugeres data

## Fremtidig udvidelse

- CSV-eksport kan tilføjes som ekstra knapper i samme sektion, genbruger `/budget/api/export-data`
- Yderligere formater (PDF) kan tilføjes efter samme mønster
