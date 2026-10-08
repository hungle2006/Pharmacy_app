# PharmaBiz Analytics | Pharmaceutical Business Intelligence

**Design and Development of a Business Intelligence Dashboard for Pharmaceutical Pricing and Market Analysis in Vietnam**

A presentation-ready business intelligence web application with interactive charts, data storytelling, read-only Neon PostgreSQL integration, and a CSV workspace. The deployed website is intentionally *not* a clinical treatment recommendation system.

## Project links

- GitHub: https://github.com/hungle2006/Pharmacy_app
- Vercel: https://pharmacyapp-hope-1091.vercel.app/
- Business Understanding opening: https://pharmacyapp-hope-1091.vercel.app/?view=business

## The analytics story

This prototype follows the **CRISP-DM** narrative:

1. **Business Understanding** – stakeholders, business questions, KPI definitions, success criteria and scope.
2. **Data Understanding** – source inventory from DAV, RxNorm, ICD-10 and MEDI, estimated database counts, grain and join relationships.
3. **Exploratory Data Analysis** – SVG histogram, donut composition chart, ingredient-level median comparison, descriptive statistics.
4. **Data Preparation / ETL** – audit → cleaning → mapping → data mart; unit-price harmonization and source lineage.
5. **Business & Pricing Analytics** – product/category overview, manufacturer competition by catalog count, price median/P10/P90 and comparison groups.
6. **Data Quality** – missing-value completeness and responsible interpretation.
7. **Data Storytelling** – derived insight cards and clear disclaimers on sample size and incomplete data.

This is a business **market intelligence** prototype, not a revenue accounting dashboard. Product listings are not unit sales; manufacturer catalog count is not market share.

## Source database

Existing Neon project (from the shared screenshot):

- Database: `neondb`
- Schema: `public`
- Product registry: `dav_product` (visible columns include `dav_row_id`, `registration_number`, `drug_name`, `active_ingredient_raw`, `strength_raw`)
- Pricing: `price_record`
- Relations: `dav_rxnorm_mapping`, `medi_relation`
- Terminologies: `disease`, `rxnorm_concept`, `rxnorm_scd`, `rxnorm_scd_component`

**The screenshot does not show every column of `price_record` or the join key**. Do not invent column names in migrations. Run `sql/neon_schema_audit.sql` in Neon SQL Editor to inspect actual tables before building a full analytical star schema.

## Connection: Neon → Vercel

1. In Neon select the correct **Pharmacy** project, **production** branch and **neondb** database.
2. In Vercel → `pharmacy.app` → Settings → Environment Variables, configure an **encrypted**, server-only `DATABASE_URL` for Production (and Preview only if desired). Use a dedicated **read-only** database role. **Do not paste passwords into chat or commit secrets to GitHub.**
3. Redeploy the Vercel project. The frontend fetches `/api/data` and `/api/insights`.
4. Verify the UI displays **NEON CONNECTED** rather than **DEMONSTRATION**, and check the backend inventory for real table counts.

The API auto-discovers public schema columns using `information_schema` and provides up to **2,000 sampled** DAV rows. It attempts to join price records only if column names, join keys and numeric price types are recognized. If no validated price join is possible, the UI uses DAV metadata without fabricated prices.

Optional: create the prepared `analytics_drug_prices` view once source mappings and price units are fully validated. `sql/analytics_view_template.sql` is illustrative and should *not* be run verbatim unless schema matches.

### Limitations of the current MVP

- 2,000 rows are a **sample**; browser KPI values must not be reported as global market aggregates. A future SQL data mart needs full-dataset aggregation and server pagination.
- Price observations from different units, dates, strengths or forms must not be compared directly.
- Price types (tender, declaration) must remain separated.
- Clinical indication relations in MEDI are *not* clinical guidance.
- No account/patient/private data should be exposed through public analytics APIs.

## Useful CSV import (local browser; no Neon credentials needed)

Choose **Nhập CSV**. Accepted headings include:

```csv
ten_thuoc,hoat_chat,ham_luong,dang_bao_che,nha_san_xuat,nuoc_san_xuat,gia,loai_gia
Thuoc A,Hoat chat A,500 mg,Vien nen,DN A,Viet Nam,2500,Gia cong bo
Thuoc B,Hoat chat B,20 mg,Vien nang,DN B,Viet Nam,7500,Gia trung thau
```

CSV values shown here are synthetic placeholders. The import parses in the browser and is not transmitted to the server.

## Code layout

```
index.html                 Static app, shared filters and dashboard
assets/visual.css          Responsive business presentation design
assets/presentation.js     Business understanding, data pipeline, SVG EDA charts
api/data.js                Read-only products and price sampling from Neon
api/insights.js            Source table inventory from Neon PostgreSQL
sql/neon_schema_audit.sql  Safe schema discovery queries
sql/analytics_view_template.sql  Optional mapping reference
.github/workflows/validate.yml   Node syntax checks on GitHub
```

## Presentation outline

1. Business challenge: fragmented source data and comparison difficulty.
2. Data sources and unit of analysis: DAV/price_record and mapping sources.
3. Data profiling and ETL: normalize, deduplicate, validate links, source lineage.
4. EDA: distributions, portfolio composition, competitive intensity.
5. Dashboards: KPI definitions, pricing spread and competing products.
6. Analytical insight and caveats: no revenue without sales, no market share without sales volumes.
7. Next stage: star schema, temporal price analysis, anomaly detection and a calibrated regression baseline.

**Research prototype; figures must be checked against the real database before presenting them as market facts.**
