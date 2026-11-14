# Pharmacy App — Visual element audit & repair plan
Ngày rà soát: 15/11/2026. Scope: Start, workspace header, chapter selector, sidebar/mobile navigation, lookup, evidence sheets, charts, interactions. Sources: screenshot in conversation, live component code and Chromium DOM measurements.

## Findings and actions

| ID | Element / context | Observed or code-grounded defect | Severity | Repair | Verify |
|---|---|---|---|---|---|
| UI-01 | "Chọn góc nhìn" desktop | Native OS select expands as full-width unbounded list and obscures page | High | Replace with search + short list popover, internal scroll, selected state, focus-safe keyboard controls | Select any chapter, close, Escape, Enter, page stays in place |
| UI-02 | Chapter picker on 320/375px | Old select and arrow buttons competed for width; initial upward menu clipped top by about 7px in Chromium | High | Narrow-screen toolbar stacks in two rows; popover anchors to picker and opens above or below based on available room | Menu rectangle entirely within viewport, zero horizontal overflow |
| UI-03 | Header CTA | "Chọn tác vụ" duplicates desktop sidebar and mobile taskbar, making header crowded | High | Remove CTA from header, retain sidebar and mobile taskbar; keep Ctrl/Cmd+K for keyboard users | No header task CTA, both navigation routes still work |
| UI-04 | Start CTA | Button used broad hover transforms and a second JS pointer animation, giving competing feedback | Medium | Use one CSS hover/active animation and short press feedback; disable during transition | Hover, click and rapid click; no stuck disabled state |
| UI-05 | Start-to-workspace | Old cover animation .65s but JS switched page at 520ms and animated page differently | High | Synchronize 440ms exit with 210ms workspace reveal, remove 3D canvas scale on intro | Click Start, landing dashboard visible, no half-faded frame |
| UI-06 | Start at 320x568 | Hard-coded minimum height and large headline can push CTA/footer below fold | High | Compact low-height breakpoint with 100dvh, flexible capsule stage, smaller proportional typography and CTA ≥48px | CTA fully visible; important elements accessible, no horizontal clipping |
| UI-07 | Mobile header actions | CSS rules accumulated from multiple iterations with 2-column/3-column grid layouts and unused slots after task CTA removal | High | Replace narrow-screen action layout with flexible group and 44px export icon; no ghost column | No blank action column or wrapped button labels at 320/375px |
| UI-08 | Navigation icon consistency | Mobile menu used a font glyph differing from existing SVG icon set | Low | Use a standard stroked SVG, preserve accessible name and toggle logic | Icon stays aligned in light/dark modes |
| UI-09 | Focus menu and source sheet | Menu and source details could overlap other content or force unnecessary long-scroll | Medium | Controlled popover height, popup placement, separate returnable sheet, no cloning source content | Open/close in viewport, body scroll lock and focus restoration |
| UI-10 | Small action targets | Mixed older widths and min-heights for desktop/mobile toolbar controls | Medium | 44px minimum interactive areas, button alignment and consistent focus-visible ring | Inspect clickable controls for small targets |
| UI-11 | Chart viewport | Wide plots can overflow phone if wrapper not scrollable | Medium | Keep scroll inside graph container and maintain axis metadata; no chart-value changes | Document width ≤ viewport, chart area may scroll internally |
| UI-12 | Mobile bottom navigation | Tight spacing at 320px, safe-area and active-state alignment | Medium | Equal 4-column grid, stable SVG/text spacing and safe area padding | Labels not clipped at 320px, tab touch boxes >=44px |
| UI-13 | Menu reduced-motion | Excess animation is inappropriate when reduced motion requested | Medium | Disable UI animations under prefers-reduced-motion | Test motion pref = reduce |
| UI-14 | Data safety | UI redesign must not alter 3D model, API, page measurements, ICD/MEDI mapping or dashboard calculations | Critical constraint | All modifications confined to presentation CSS + navigation/motion code | Node syntax, unit/integration tests, no API or GLB edits |

## Implementation phases
1. **P0:** Chapter dropdown replacement (previous screenshot), fix upward popover edge, remove duplicate header task CTA and prove all chapter selection routes work
2. **P1:** Start button & entrance motion synchronisation, compact mobile Start responsive layout and keyboard-visible focus states
3. **P1:** Consolidate mobile spacing and header actions, standardize nav SVG, ensure touch targets and panels can be closed/reopened
4. **P2:** Regression tests, responsive Chromium checks at 320x568, 375x812, 390x844, 768x900, 1024x900 and 1440x900; merge only after CI and Vercel READY
5. **P2:** Deeper future follow-up: screenshot-diff of every dynamic API state on physical iOS/Android devices, which headless Chromium does not completely simulate

## Acceptance criteria
- No document horizontal overflow greater than 2px at tested widths; long chart/table content can scroll **within its own container**.
- The Start button is reachable and visible; model scene unchanged and poster fallback intact.
- One focus page visible at a time; native option UI hidden; menu can be searched and dismissed by Escape/outside click.
- All primary buttons have at least 44px interactive height except intentional inline text links.
- No unexpected vertical jump when flipping chapters; detail drawers close to restore content and focus.
- No missing source records, fabricated values, API modifications, or altered 3D model assets.

## Evidence status
- Previously confirmed in Chromium: custom chapter menu at 1440/1024/768/375/320px, 65/65 existing tests, zero horizontal page overflow; detected and fixed 7px popup clipping on 320/375px.
- New Start and responsive changes require fresh browser runs; treat as **pending verification** until results are recorded.


## Additional measured findings (Chromium)

| ID | Evidence | Remediation / status |
| --- | --- | --- |
| UI-15 | Desktop quick-search submit button measured 20×30px; target should be ≥44px | Set an actual 44×44px hit area, not just a larger icon; pending final recheck |
| UI-16 | Mobile lookup filter toggle measured 78px tall at 375px and 115px tall at 320px despite collapsed state | Shorten the accompanying description and standardize a 46px-wide full-row toggle; full source criteria remain expandable |
| UI-17 | Mobile lookup "Cách đọc kết quả" explanation measured 71px collapsed due to overly verbose summary | Shorten collapsed caption to "Cách đọc kết quả", preserve full explanation inside the details |
| UI-18 | Lookup retry button measured 77×40px | Increase minimum hit height to 44px |
| UI-19 | After filter height fix, filter toggle initially occupied only half of a 300px row due to upstream two-column grid precedence | Explicit one-column collapsed layout with full-width action |

### Latest browser measurements before final review
- Start 320×568: CTA rectangle y=467–516, 49px high; footer 525–568; width=320px with no horizontal overflow.
- Start 375×812: CTA y=618–675, 57px high; preserved 3D stage; no horizontal overflow.
- Across 320,375,390,768,1024,1440px: Start click succeeded, dashboard shown, button state restored, no JS errors during the tested flow.
- Primary workspace views (research, pricing, lookup, disease and market forecast) at 1440/768/375/320px: no overall horizontal page overflow.
- Lookup mobile collapsed filters before fix: results panel began at ~649px (375px screen) / ~687px (320px screen). After compact label + toggle sizing, result panel began ~584px in both; no removed data fields.
- Focus popup previously measured inside viewport at 320/375, after fixing initial 7px upward clipping.

These checks verify Chromium layout, not native Safari/iPhone or every individual API state.


## Final regression pass (Chromium, branch before merge)

- Node syntax + `npm test`: **69 passed, 0 failed**.
- Start 320×568: CTA bottom at 516px, footer below; document width exactly 320px, 3D canvas present.
- Start 375×812: CTA bottom at 675px; 3D canvas present, no horizontal overflow.
- 768×900 and 1440×900: Start clicked and dashboard entered successfully; no stuck disabled/busy button.
- Reduced-motion 375×812: Start immediately enters dashboard, cover is hidden.
- Lookup 320px: filter container width=300px, toggle width=300px, height=46px, result card starts at y=584px.
- Lookup 375px: filter container width=349px, toggle width=349px, height=46px, result card starts at y=584px.
- Desktop 1440px: quick search submit hitbox=44×44px.
- No horizontal document overflow or browser page errors in the tested Start/lookup paths.
- Existing chapter popover was tested at 1440/1024/768/375/320px: search, option selection, Escape and prev/next navigation behaved as expected; no menu clipping after mobile anchor fix.

**Residual checks:** Native iOS Safari, Android Chrome hardware, and all data-driven popup states have not been visually compared on real devices. The shipped revision preserves the underlying data and 3D asset.
