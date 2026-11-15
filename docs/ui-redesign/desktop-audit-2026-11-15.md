# Pharmacy App — desktop workspace review (15/11/2026)

## Scope
Laptop/desktop layout 761–1920px; navigation, title, quick-search, main data filters, lookup results, focus chapters, prediction task spacing. Preserve original 3D Start scene, data APIs, model calculations, and phone-specific layouts.

## Confirmed defects
- **D-01 — duplicated searches in drug lookup:** the global chart filter toolbar rendered underneath the lookup task’s own search. Repair: desktop lookup shows only the context-relevant lookup form; chart filters remain available in chart views.
- **D-02 — narrow laptop shell at 761–980px:** an earlier breakpoint reset the main left margin despite the sidebar remaining visible. Repair: keep sidebar and content in separate columns, hide secondary header actions when space is tight.
- **D-03 — unexpected nested scrolling:** the focus-page had a fixed max-height of 70svh even when page content could fit naturally. Repair: remove the artificial height cap on desktop and retain the single workspace scroller for longer tasks.
- **D-04 — vertical waste:** oversized page title panels, KPI cards, form whitespace and result controls pushed short workspaces below the fold. Repair: compact typography/spacing with consistent field heights.
- **D-05 — search control sizing:** competing search flex constraints and icon buttons risk truncation. Repair: zero-min-width flex input, fixed action hitbox, bounded form widths and ellipsis on filter triggers.

## Chromium measurements (headless, offline local frontend)
| View | 1440×900 content overflow before → after | 1024×768 before → after |
|---|---:|---:|
| Overview | 41px → 0px | 394px → 302px |
| Drug lookup | 252px → 61px | 472px → 200px |
| Feature price | 0px → 0px | 0px → 0px |
| Disease prediction | 201px → 67px | 410px → 220px |
| Pricing | 41px → 0px | 394px → 302px |
| Reports | 0px → 0px | 0px → 0px |
| Modeling | 0px → 0px | 0px → 0px |

Remaining scroll in longer dashboards is intentional. Lookup results and detail panes retain internal scrolling when required rather than clipping their records.

## Validation
- `npm run check`: passed.
- `npm test`: **69 passed, 0 failed**.
- Chromium responsive checks: 760, 800, 860, 980, 1024, 1280, 1366, 1440, 1920px. No document horizontal overflow; no sidebar/main or quick-search/action intersection in measured views; no page JS errors observed.
- Real production/API states, native Safari and physical monitor color rendering were **not** verified by this local test.

## Changes
- Added `assets/desktop-workspace.css` as the scoped, final desktop layer.
- Included one versioned stylesheet link in `index.html`.
- No data API, model, GLB, ETL or mobile task logic modifications.
