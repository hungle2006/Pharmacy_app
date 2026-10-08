# PharmaBiz — Pharmaceutical Market Intelligence

**Design and Development of a Business Intelligence Dashboard for Pharmaceutical Pricing and Market Analysis in Vietnam**

Production: https://pharmacyapp-murex.vercel.app/

## Experience

- Animated three-dimensional capsule, orbiting particles and pointer parallax on the introduction screen. Start opens the workspace. Reduced-motion preferences are respected and animation stops when the cover is hidden.
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
npm run check
npm test
```

Tests validate filter parameterization, bounded pagination, explicit unavailable states and execute the analytical SQL in PostgreSQL via PGlite. Fixtures cover multiple observations per product, missing prices, non-VND prices, empty filters, equivalent groups and pagination.

The GitHub main branch is connected to the existing Vercel `pharmacy.app` project. Vercel deploys static frontend assets and Node API functions. Neon credentials stay in Production environment variables.
