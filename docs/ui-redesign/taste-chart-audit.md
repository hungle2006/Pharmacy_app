# Taste-skill adaptation: Pharmacy task and chart audit

Source design guidance: [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill), specifically `skills/taste-skill/SKILL.md`, README v2.5.1 and system/layout/copy references. Applied to the **existing interactive analytical product** rather than copying its company-website templates. Preserve the approved 3D Start and existing API/data/model behavior.

## Shared product design rules

- One visual system: existing PharmaBiz typography, teal brand accent, state colors, 44px interaction targets; task-specific surface washes distinguish sections while keeping stable categorical chart colors.
- One clear task at a time in the established `focus-deck`. Never remove research tables, sources, provenance, quality gates or clinical limitations.
- Show *actual* data and periods from Neon/Render/DAV/RxNorm/ICD/MEDI; no illustrative values in real charts. Labels and units must be visible; every aggregate keeps inspectable source rows.
- A time-series line is appropriate only for comparable observations that represent a continuous series. Monthly cross-sectional price medians are discrete points, not a longitudinal single-drug price.
- Pie, donut or proportional mosaic only when categories are mutually exclusive with a defensible denominator. Binary/overlapping accepted/review/foreign-key checks are separate indicators, not a 100% split.
- An actual funnel is reserved for cumulative conditions on the **same** population. If the values violate nested-subset assumptions, retain independent bars and explain the limitation.
- Different interval semantics are explicit: P10–P90 historical **distribution**, model **calibration interval**, test **error**, and future **forecast** are not interchangeable.
- Desktop and mobile must maintain the current real interactions. Reduced-motion and no-data/error states cannot become blank pictures.

## Per-task visualization selection

| Task | Main relationship | Visual forms | Do not imply |
| --- | --- | --- | --- |
| Tổng quan | Monthly observations, country makeup, ingredient ranking | Columns by declaration month, country ring, ranked bars; source coverage funnel | Market sales, drug-level longitudinal price |
| Tra cứu thuốc | Search, product details, one-to-many mapping | Search-result list + selected detail panel | A chart where a source record is the real object |
| Dự đoán bệnh | Ranked text labels, user ICD selection | One flashcard at a time, softmax mark, step-by-step sourced evidence | Softmax is probability of diagnosis |
| Dự báo thị trường | 3/6/12-month conditional changes, quality gates | Historical P10–P90 range, horizon comparisons, validation diagnostics | An unapproved market forecast as approved |
| Dự đoán giá | Point estimate and calibrated interval | Estimate-in-interval graphic; test coverage/readouts | Guaranteed price or individual-error bound |
| Phân tích giá | Irregular price bins; relative variation among comparable groups | Six categorical frequency dots, P10–P90 interval strips, discrete monthly median marks | Equal-width histogram bins, fixed-basket price series |
| Phân tích cạnh tranh | Product count vs ingredient breadth | Scatter with numbered source lookup, independent rankings | Market share or causation |
| Danh mục | Form composition and category comparison | Proportional mosaic, ranked categories, country-by-form heatmap | Share of sales or standardized countries |
| Chất lượng | Independent missingness and mapping flags | Filled/missing bars, status ranks, separate technical indicators | Add overlapping missing fields to get defective product count |
| Đề tài & mục tiêu | Readiness indicators with distinct denominator | Independent benchmark bars and supporting descriptions | A funnel across different populations |
| Nguồn dữ liệu & tích hợp | Source lineage and cumulative MEDI eligibility | Process narrative and conditional count funnel | Rejected/filtered row is necessarily wrong |
| Thống kê dữ liệu | Distribution, cardinality and numeric spread | Ranked categories, monthly columns, box plot where quartiles exist | Normality from a box plot alone |
| EDA dữ liệu | Two-way categoricals and null patterns | Row-normalized/count heatmap and missing-combination ranks | Meaningful effect from color alone |
| Làm sạch dữ liệu | Field completeness and normalized relationships | Missing-combination frequencies and documented data rules | Invented before/after counts |
| Mô hình hóa & đánh giá | Training/test metrics and errors | Test scatter, signed residual distributions where available, grouped model metrics | Better generalization without independent holdout |

## Changes in this iteration

1. `assets/taste-workspace.css`: shared editorial hierarchy, responsive grid, focus navigation, task variations, accessible chart presentation.
2. `assets/task-depth.js`: exact six-bin frequency-dot chart; discrete median-by-month marks; proportionally sized form mosaic; inspectable data sources.
3. `assets/data-exploration.js`: single-population cumulative funnel with bar fallback for inconsistent counts.
4. `assets/feature-price.js`: model estimate marker placed on its own returned calibration interval.
5. `tests/taste-workspace.test.js`: count reconciliation, zero-bin preservation, integration and graphic-family checks.

## Validation boundaries

The upstream Taste Skill runner targets authored company pages, and its one-section-per-screen static gate would incorrectly reject long tables and interactive dashboards. Therefore its design rules are **adapted** here; run this repository's Node tests, syntax/build, and browser interactions across task routes and responsive widths rather than claiming a Taste Skill `GATE: PASS` for a different output type. Keep known gaps explicit in the completion report.
