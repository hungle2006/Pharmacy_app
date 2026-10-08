# PharmaBiz Analytics — Vietnam Pharmaceutical Market Intelligence

**Design and Development of a Business Intelligence Dashboard for Pharmaceutical Pricing and Market Analysis in Vietnam**

Live-deployable dashboard built as static HTML/CSS/JavaScript, with an optional read-only Vercel Function for Neon/PostgreSQL. This is a working **MVP** (not a clinical recommendation system).

## Dashboard sections

1. **Market Overview:** total rows, unique ingredients, unique manufacturers, median price, top ingredients and countries.
2. **Drug Pricing Analytics:** P10, median, P90, and within-group price dispersion.
3. **Competitor Intelligence:** manufacturers per ingredient and product counts per manufacturer.
4. **Portfolio Analytics:** dosage forms and therapeutic group coverage.
5. **Data Quality:** completeness by field and data-governance warnings.

All sections have a shared search + ingredient, country, price-type filters, pagination, **CSV import** and **CSV export**.

## Demo vs real data

The app always labels *synthetic* records **DỮ LIỆU MÔ PHỎNG**. Demo products, manufacturers, and prices are deliberately fictitious; they are not claims about Vietnam's drug market.

- Open `index.html` to explore the demo immediately.
- On Vercel, the UI requests `/api/data`.
- If `DATABASE_URL` is available and the normalized SQL view exists, the app switches to the database and labels it **DỮ LIỆU DATABASE**.
- Otherwise the frontend remains in clearly marked demo mode.
- The browser CSV import is local: your CSV file is not sent to the server.

## Import your DAV CSV (no server credentials required)

Click **Nhập CSV**. Supported Vietnamese/English headers include:

```csv
ten_thuoc,hoat_chat,ham_luong,dang_bao_che,nha_san_xuat,nuoc_san_xuat,gia,loai_gia
Thuoc A,Hoat chat A,500 mg,Vien nen,Nha san xuat A,Viet Nam,2500,Gia cong bo
Thuoc B,Hoat chat B,20 mg,Vien nang,Nha san xuat B,Viet Nam,7500,Gia trung thau
```

The CSV parser supports quotes and semicolon-separated files. CSV price values should already use consistent VND units. The browser loads up to 15,000 rows, but it is *not* a production analytics warehouse.

## Connect your existing Neon/PostgreSQL

1. Inspect and validate your existing DAV database schema.
2. Create a **read-only view** named `analytics_drug_prices` with the following columns:

| Column | Required purpose |
|---|---|
| `id` | Stable product/price-row ID |
| `drug_name` | Drug/product name |
| `ingredient` | Standardized active ingredient |
| `strength` | Strength/dose |
| `dosage_form` | Form |
| `manufacturer` | Manufacturer (not reseller) |
| `country` | Manufacturing country |
| `price_vnd` | Comparable price in VND |
| `price_type` | Declared/tender or other source type |
| `therapeutic_group` | Grouping from source data |
| `snapshot_date` | Date of observation |
| `registration_no` | Product registration number |

An **illustrative** SQL view mapping is in `sql/analytics_view_template.sql`. You **must edit** its source table and source column identifiers to match your database; don't run it verbatim unless your raw schema matches.

3. On **Vercel → Project → Settings → Environment Variables**, create encrypted `DATABASE_URL` for Production. Give it a **read-only DB role** and never use `NEXT_PUBLIC_` in the name.
4. Redeploy the Vercel project. The backend function `api/data.js` reads at most 5,000 price rows.

### Limitations

- For more than 5,000 rows, current dashboard metrics are calculated on a subset; use SQL aggregate endpoints for full-dataset KPIs.
- A quantity of product rows is not sales volume or revenue **market share**.
- Price comparisons require the same unit, dosage form, strength, and comparable date/source.
- ICD-10 and MEDI joins are intentionally not used to infer appropriate treatments.
- Never commit real passwords, health records or credentials to this public repository.

## Deployment

This repository is linked to Vercel; pushes to the configured production branch build/deploy automatically. Static UI is served from `index.html`, serverless API from `api/data.js`. No React build is needed in this deployed MVP.

## Next phase

- Add a DAV data mart, normalized unit pricing and source lineage.
- Replace client-side full-array computations with SQL aggregates + pagination.
- Add date range comparison, therapeutic classes, anomaly detection and regression baselines.
- Evaluate ICD–RxNorm–DAV mapping coverage independently from business price KPIs.
