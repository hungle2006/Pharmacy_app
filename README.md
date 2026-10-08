# PharmaBiz — Pharmaceutical Market Intelligence

**Design and Development of a Business Intelligence Dashboard for Pharmaceutical Pricing and Market Analysis in Vietnam**

Production: https://pharmacyapp-murex.vercel.app/

## Experience

- Blender-authored GLB capsule with smooth PBR materials, WebGL lighting, orbiting particles and pointer parallax on the introduction screen. Start opens the workspace. Reduced-motion preferences are respected and animation stops when the cover is hidden.
- Persistent light/dark theme on both the cover and workspace; higher-contrast readable typography.
- Database-derived analysis briefs, removable filter chips, 6/12/all-month timeline controls and count/median switching.
- Responsive dashboard with eight sections: Overview, Pricing, Competition, Portfolio, Data Quality, Business Understanding, Data Understanding, Modeling & Evaluation.
- Shared search and filters for ingredient, country, price type and price unit. Chart selections filter the dashboard.
- SVG charts with accessible labels, interactive tooltips, animations and a presentation layout.
- Server pagination, 12 observations per page, and CSV export of the current page.
- Real database analytics only. Missing credentials, failed queries and empty results are displayed explicitly.

## Database and analytics

The production `DATABASE_URL` is stored as a sensitive server-only Vercel variable. Never use a `NEXT_PUBLIC_` prefix or commit credentials. The application does not migrate or modify source data.

`api/analytics.js` computes KPI and charts using parameterized read-only SQL against **all records matching the filters**, rather than a browser sample. Verified schema:

- `dav_product`: `dav_row_id`, `drug_name`, `registration_number`, `active_ingredient_raw`, `strength_raw`, `dosage_form_raw`, `manufacturer`, `country`, `unit`, `package`.
- `price_record`: `price_id`, `dav_row_id`, `price_vnd`, `currency`, `price_type`, `declaration_date`, `unit`, `package`.
- Mapping and terminology sources: `dav_rxnorm_mapping`, `disease`, `medi_relation`, `rxnorm_concept`, `rxnorm_scd`, `rxnorm_scd_component`.

Grain and definitions:

- Products: `COUNT(DISTINCT dav_row_id)` after filters. Multiple price observations do not inflate product counts.
- Observations: product × price record rows after the left join. A product without a price remains visible when no price-specific filter excludes it.
- Price statistics: nonnegative VND prices, including source rows with missing/empty currency that need source review. Missing prices remain `null`, never converted to zero.
- Country, ingredient, manufacturer and dosage-form compositions: one row per distinct product after filters.
- Timeline: count of valid prices or median price grouped by `declaration_date` month. No fabricated months or interpolation. Changes in product mix can affect monthly medians.
- Comparison groups: ingredient, strength, dosage form, unit and price type must all be present; at least two distinct products. Route, packaging and time still require review.
- Completeness: nonempty fields on distinct products in the filter scope.
- Mapping metrics: full `dav_rxnorm_mapping` table, independently of product filters; accepted/review/FK flags are reported as stored.
- Source inventory: PostgreSQL row estimates, explicitly marked with `~`. Dashboard KPI use actual aggregation counts.

Catalog size is not sales volume or revenue market share. The Modeling section is a research plan, not a trained forecasting model. The application is for business analytics and does not provide prescribing advice.

## Verification

```bash
npm ci --ignore-scripts
npm run build
npm run check
npm test
```

Tests validate filter parameterization, bounded pagination, explicit unavailable states and execute the analytical SQL in PostgreSQL via PGlite. Fixtures cover multiple observations per product, missing prices, non-VND prices, empty filters, equivalent groups and pagination.

The GitHub main branch is connected to the existing Vercel `pharmacy.app` project. Vercel deploys static frontend assets and Node API functions. Neon credentials stay in Production environment variables.

## Blender source

The editable scene is `assets/models/pharmabiz-capsule.blend`. Rebuild using official Blender 4.5 LTS:

```bash
blender --background --python scripts/build-capsule.py
npm run build
```

`src/scene3d.js` loads the exported GLB with Three.js, uses a procedural studio environment, pauses rendering when hidden, and respects reduced motion. A lightweight canvas fallback remains available for browsers without WebGL. Three.js is bundled locally during the Vercel build; no third-party runtime CDN is required. Timeline windows end at the latest month in the filtered data; absent months are not filled. The P10/P90 analysis card summarizes the observed distribution and does not imply unit-normalized market prices.
