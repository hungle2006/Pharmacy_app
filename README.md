# PharmaBiz — Pharmaceutical Market Intelligence

**Design and Development of a Business Intelligence Dashboard for Pharmaceutical Pricing and Market Analysis in Vietnam**

Production: https://pharmacyapp-data.vercel.app/

## Experience

- Blender-authored GLB capsule with smooth PBR materials, WebGL lighting, orbiting particles and pointer parallax on the introduction screen. The cover has one Start action; Logout returns from the workspace to the 3D introduction. Reduced-motion preferences are respected and animation stops when the cover is hidden.
- Persistent light/dark theme on both the cover and workspace; higher-contrast readable typography.
- Database-derived analysis briefs, removable filter chips, 6/12/all-month timeline controls and count/median switching.
- Responsive dashboard with thirteen retained tasks for overview, lookup, forecasts, pricing, supply, portfolio, data quality, research goals, integration, statistical profiles, EDA, cleaning and model evaluation.
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

Catalog size is not sales volume or revenue market share. The Modeling section reads the live walk-forward and independent-test report; estimates that do not pass remain explicitly experimental. The application is for business analytics and does not provide prescribing advice.

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

`src/scene3d.js` loads the exported GLB with Three.js, uses a procedural studio environment, pauses rendering when hidden, and respects reduced motion. Browsers without WebGL show a CPU-rendered Blender poster with CSS float/parallax animation; a lightweight canvas remains as the final image-load fallback. Three.js is bundled locally during the Vercel build; no third-party runtime CDN is required. Timeline windows end at the latest month in the filtered data; absent months are not filled. The P10/P90 analysis card summarizes the observed distribution and does not imply unit-normalized market prices.


## Paginated complete Gold data and RxNorm endpoints

The browser's main `/api/analytics` dashboard calculates aggregate metrics on **all matching Neon Gold records** and displays 12 paginated observations at a time. The independent legacy `/api/data` endpoint formerly sampled `LIMIT 2000` rows and did not drive the dashboard. It now reads **all Gold rows by paginating in SQL**; no total-record cap or in-memory download of the database.

- `GET /api/data?page=1&pageSize=100` — default 100 rows, maximum 200 per request. Returns `records`, `page`, `pageSize`, `totalRows`, `totalPages`, `hasNextPage`, `hasPreviousPage`, `sampled:false`.
- `GET /api/data?page=21&pageSize=100` — retrieves beyond the previous 2,000-row cutoff.
- `GET /api/data?q=paracetamol&ingredient=...&country=...&kind=...&unit=...` — fully parameterized filters across the Gold source, including unpriced products.
- `GET /api/data?currentOnly=true` — current Silver DAV product records only. Without this option **both** historic and current DAV rows are included (no silent loss). Legacy probable-duplicate flags `catalog_duplicate_status` and `catalog_equivalent_to` accompany results, but do not delete or hide original price history.
- `GET /api/rxnorm?q=acetaminophen&page=1&pageSize=25` — read-only canonical RxNorm terminology + SCD text metadata, with 100-row page cap and a full result count.
- `GET /api/rxnorm?dav_row_id=100024` — DAV product's recorded, accepted or suggested SCD and component evidence; unverified RxCUI candidates are never presented as clinically validated mappings.

Both APIs use server-side `DATABASE_URL`, explicit SQL `ORDER BY`, bounded page sizes, safe query parameters and no new database tables or R2 copies. Counts reflect **product × price observations**, not necessarily unique products. The frontend CSV button on the main dashboard continues to export **the current dashboard page** rather than claiming to export all matching records. Full exports would require a separate controlled batch/streaming endpoint.

Tests in `tests/gold-data-pagination.test.js` exercise 2,105 PostgreSQL rows, including page 21 and 22, parameter safety, and the RxNorm query using PGlite.

## Tra cứu thuốc trên PharmaBiz

Mở [PharmaBiz](https://pharmacyapp-data.vercel.app/) nhấn **Start**, rồi chọn **Tra cứu thuốc** trong menu bên trái. Tab **Thuốc Việt Nam** tìm theo tên thuốc, hoạt chất, số đăng ký hoặc nhà sản xuất. Mặc định chỉ dùng dữ liệu DAV hiện tại từ Silver; có thể bỏ chọn để tra cả Gold lịch sử. Mỗi kết quả biểu diễn **một DAV ID** và giá quan sát mới nhất nếu có. Chọn một thuốc để xem hàm lượng, dạng bào chế, thông tin đăng ký, ứng viên RxNorm và bằng chứng thành phần. Tab **RxNorm** tra cứu bằng tên thuật ngữ hoặc RxCUI.

Giao diện hoạt động trực tiếp qua `/api/data?mode=products` và `/api/rxnorm`, có tìm kiếm và phân trang trên toàn bộ Neon Gold; không tạo bản sao, không giới hạn 2.000 dòng. Mọi RxCUI ứng viên chưa xét duyệt được phân biệt rõ với mapping chấp nhận trong Gold. **Không dùng mapping chưa được xác minh để tư vấn điều trị.** Giao diện đáp ứng điện thoại và chế độ sáng/tối; các dashboard phân tích cũ vẫn hoạt động.

Truy cập trực tiếp mục tra cứu mà không qua trang giới thiệu: https://pharmacyapp-data.vercel.app/?view=lookup


## RxNorm → DAV reverse lookup

In **Tra cứu thuốc → RxNorm**, search by RxCUI or term, select a concept,
then review the **Thuốc DAV liên quan** section. The results are paginated
independently of the RxNorm terminology search; each product can be opened
to inspect source DAV details and price observations.

The read-only API is:
- `GET /api/rxnorm?dav_for_rxcui=979492&page=1&pageSize=10` for direct
  *SCD-to-DAV* links, separated as `ACCEPTED_SCD` and `CANDIDATE_SCD`.
  Optional `review=accepted` or `review=review` filters these classifications.
- `GET /api/rxnorm?dav_for_rxcui=161&page=1&pageSize=10` for *ingredient-to-DAV*
  matches from `dav_rxnorm_evidence.ingredient_candidate_rxcui`. Each
  has `INGREDIENT_EVIDENCE` review status, even when the same DAV product
  happens to have another accepted SCD mapping.
- Unsupported RxNorm term types return no DAV associations rather than
  making a medically misleading name-based link.

A result is counted once per DAV ID. A latest price observation (if any)
is displayed for convenience. No Gold rows or schema are modified. Source
mapping and ingredient evidence have not necessarily been clinically
validated; they do not imply interchangeable medicines or indications.

## Research reading workflow

Each task explains its research question, role in the integrated pharmacy-data system, method, units, source-backed interpretation and next analytical step. The statistical workspace covers all nine Gold tables. Silver terminology inference remains explicitly scoped to its snapshot: Welch comparisons with Holm-adjusted p-values, approximate difference intervals, and a row-normalized TTY-by-length matrix with its independence limitation. The frontend does not rewrite datasets or retrain models.
