# PrintSight — Phased Implementation Plan (PRP v1.2 → Code)

## Context

**Why this plan exists**
PrintSight's spec (`PRPs/printsight-prp.md`) was just revised to v1.2. The revisions capture three things the current code does not:

1. **Printer as root entity** — every configuration, upload, and report must be scoped to a specific printer, with the printer surfaced as the top-level UI anchor (selector + hero image).
2. **Historical cost accuracy** — when toner cartridge prices change, only prints made *after* the new cartridge was installed should reflect the new price. Current schema stores a single `toners.price_per_unit` and would retroactively rewrite history.
3. **Insightful reporting** — Owners need daily/weekly/monthly/yearly cost-per-print views, plus cost-bleed attribution ("why did cost rise?") and maintenance signals ("cost-per-print is 22% above baseline → service recommended").

**Current state (verified 2026-04-17)**
- Backend: basic CRUD for printers, papers, toners, replacements, CSV upload. Services dir is **empty** — no cost calculator at all. No image upload. No archive/purge.
- Frontend: simple pages for printers, costs, toner replacements, dashboard, analytics. No PrinterContext, no chart components folder, no Edit Printer page, no wizard, no dedicated cost-bleed / efficiency pages.
- Migrations: single `001_initial_schema.py`.

**Outcome**
A phased build where Phase 1 delivers a polished, printer-centric configuration UX (with per-cartridge pricing captured), Phase 2 builds the correct cost engine, Phase 3 produces the reports and insights, and Phases 4–5 add notifications, admin, and hardening.

---

## Guiding Principles

- **Printer is the root.** Every screen scopes by the currently-selected printer via a top-level `PrinterContext`.
- **Never rewrite history.** Historical cost stays pegged to the cartridge installed on the print date, not the current `toners.price_per_unit`.
- **Enter data before using it.** UI blocks uploads and calculations when prerequisites (toner price, paper link) are missing — with clear empty-state guidance telling the Owner what to do.
- **One phase, one usable increment.** Each phase ships something end-to-end before the next starts.

---

## PHASE 1 — UI & All Printer Configurations (Look & Feel)

**Goal:** Owner can enter every setting needed for a printer through a polished, printer-centric interface. No cost math in this phase — just get the data IN correctly.

### Deliverables (at end of Phase 1, these work)
- Create / edit / archive / hard-delete / purge a printer
- Upload a printer image and see it as the dashboard hero banner
- Run a 5-step Setup Wizard when adding a new printer
- Configure paper types with width, length, GSM range, tolerance — link to printers via junction
- Configure toners per printer (price + rated yield — these become defaults for future replacements)
- Log toner replacements with per-cartridge price captured (pre-filled, editable)
- Export and import column mappings as JSON
- See a colorful dashboard shell (placeholder data) with printer selector + period tabs

### Tickets

| # | Ticket | Files Touched | Est |
|---|---|---|---|
| 1.0 | Alembic migration `002_r11_paper_gsm_image_junction.py` (image_url, tolerances, junction, paper_gsm, matched_paper_id) | `backend/alembic/versions/`, `backend/app/models/printer.py`, `paper.py`, `upload.py` | 2 h |
| 1.0b | Alembic migration `003_r12_per_cartridge_pricing.py` (cartridge_price_per_unit, cartridge_rated_yield_pages, currency, index) | `backend/alembic/versions/`, `backend/app/models/toner.py` | 1 h |
| 1.1 | `PrinterContext` — global state, hydrated from `/printers`, persisted in localStorage | `frontend/src/context/PrinterContext.tsx`, `frontend/src/App.tsx` | 2 h |
| 1.2 | Design system pass — palette, gradients, shadcn theme, toner color constants | `frontend/tailwind.config.ts`, `frontend/src/lib/colors.ts` | 3 h |
| 1.3 | App shell redesign — sidebar + topbar with `PrinterSelector` (image thumb + name) as main nav anchor | `frontend/src/components/layout/TopBar.tsx`, `Sidebar.tsx`, new `PrinterSelector.tsx` | 3 h |
| 1.4 | Printer image upload endpoint (`POST/DELETE /printers/{id}/image`) + `StaticFiles` mount at `/uploads/printers` | `backend/app/routers/printers.py`, new `services/printer_image_service.py`, `backend/app/main.py` | 2 h |
| 1.5 | Verify `PUT /printers/{id}` accepts `image_url`, name, model, etc. (small patch to existing endpoint) | `backend/app/routers/printers.py` | 0.5 h |
| 1.6 | `EditPrinterPage` + `PrinterImageDropzone` + `PrinterHeroBanner` components | `frontend/src/pages/printers/EditPrinterPage.tsx`, new `components/printers/*.tsx` | 4 h |
| 1.7 | Archive / Restore / Hard-delete (guarded) / Purge (confirm-by-name) endpoints | `backend/app/routers/printers.py`, `services/printer_service.py` (new) | 3 h |
| 1.8 | `DeletePrinterDialog` with 3-tier radio + typed confirmation for purge | `frontend/src/components/printers/DeletePrinterDialog.tsx` | 2 h |
| 1.9 | Column mapping export/import endpoints (GET JSON download, POST JSON upload with diff preview) | `backend/app/routers/printers.py`, `services/column_mapping_service.py` (new) | 2 h |
| 1.10 | `ColumnMappingExportImport` UI — diff modal before apply | `frontend/src/components/printers/ColumnMappingExportImport.tsx`, `frontend/src/pages/printers/ColumnMappingPage.tsx` | 3 h |
| 1.11 | Setup Wizard — 5-step flow at `/printers/new` with progress bar + per-step validation | Rewrite `frontend/src/pages/printers/AddPrinterPage.tsx`, new sub-components per step | 6 h |
| 1.12 | Paper CRUD with tolerances + `/printers/{id}/papers` link/unlink endpoints; `PrinterPaper` model | `backend/app/models/paper.py`, `backend/app/routers/cost_config.py`, `backend/app/routers/printers.py` | 3 h |
| 1.13 | `AddPaperModal` / `EditPaperModal` — width/length/GSM/tolerance/price + PrinterMultiselect | `frontend/src/pages/settings/CostConfigPage.tsx` | 4 h |
| 1.14 | Toner CRUD + `EditTonerModal` (pencil icon per row) | `frontend/src/pages/settings/CostConfigPage.tsx` | 2 h |
| 1.15 | Toner Replacement form — add `cartridge_price_per_unit` + `cartridge_rated_yield_pages` (required, pre-filled from `toners` defaults, editable); "Update default too" checkbox | `backend/app/routers/toner_replacements.py`, `frontend/src/pages/settings/TonerReplacementsPage.tsx` | 4 h |
| 1.16 | Empty-state callout system — missing toners / missing papers / no replacements / no uploads, each with action link | Throughout `frontend/src/pages/` | 3 h |
| 1.17 | Dashboard visual shell — colorful KPI cards with placeholder numbers, grouped bar chart stub, maintenance banner slot, period tabs (Day/Week/Month/Year). All powered by mock data so Phase 1 demos visually. | `frontend/src/pages/dashboard/DashboardPage.tsx`, new `frontend/src/components/charts/*.tsx` | 4 h |
| 1.18 | Smoke test pass: create → wizard → paper → toner → replacement → edit → archive → restore → purge | Manual | 1 h |

**Total Phase 1:** ~50 h (≈ 1 week for one developer).

### Phase 1 Exit Criteria
- [ ] Every configuration can be entered and edited through the UI
- [ ] Per-cartridge price is captured on every replacement log (verified via DB inspection)
- [ ] Printer is the top nav anchor — cannot be missed which printer is in focus
- [ ] Dashboard looks finished (even with placeholder data)
- [ ] `/printers/new` runs the 5-step wizard; cannot skip a step
- [ ] Upload is disabled with warning if no toners are configured

---

## PHASE 2 — CSV Ingestion + Historical Cost Engine

**Goal:** Real numbers appear. Upload a CSV → see accurate paper + toner cost per job, using the correct cartridge price per date.

### Tickets (outline)
- 2.1 Add `paper_gsm` canonical field + `print_jobs.paper_gsm` + `print_jobs.matched_paper_id` parsing in CSV parser
- 2.2 `paper_match_service.py` — printer-scoped tolerant match (width ± tol, length ± tol, gsm in range) with name-match fallback
- 2.3 `cartridge_resolver.py` — returns the replacement log (or `toners` bootstrap) whose `replaced_at ≤ job.printed_at` for a (printer, color) pair
- 2.4 `cost_calculator.py` — rewrites using both services; populates `computed_paper_cost`, `computed_toner_cost`, `computed_total_cost`, `is_waste`, `matched_paper_id`
- 2.5 Re-cost trigger on replacement log create / edit / delete, scoped to the affected `(prev.replaced_at, next.replaced_at)` window for that toner color
- 2.6 Manual CSV upload (`POST /printers/{id}/logs/upload`) + API-key ingest (`POST /api/v1/ingest/{api_key}/logs`) with dedup on `(printer_id, job_id, recorded_at)`
- 2.7 Upload batch UI — drop zone, progress, skipped-row detail modal
- 2.8 Upload gate — disabled with empty-state when no toners configured
- 2.9 Verification: two replacements at different prices → jobs on either side of the date use the right cartridge price

### Phase 2 Exit Criteria
- [ ] Upload one day's CSV → every job has non-zero `computed_total_cost` (assuming paper + toners configured)
- [ ] Change today's cartridge price on a new replacement log → today's new-cartridge jobs reflect it; yesterday's do not
- [ ] Editing a replacement log recomputes only jobs in the affected window

---

## PHASE 3 — Daily / Weekly / Monthly / Yearly Reports + Insights

**Goal:** Owner gets the cost-per-print, efficiency, and cost-bleed insights that drive decisions.

### Tickets (outline)
- 3.1 `period=day` support across every analytics + report endpoint; dashboard default = today
- 3.2 `/analytics/summary` + live KPI cards (cost, pages, waste %, cost/print color, cost/print B&W, avg job duration)
- 3.3 `/analytics/trends` + Cost Trend Area Chart (day-by-day)
- 3.4 `/analytics/cost-breakdown` + Paper vs Toner Grouped Bar Chart (replaces the grey donut)
- 3.5 `efficiency_service.py` + `/analytics/efficiency` — cost-per-print trend, avg job duration, pages/day, maintenance_signal flag
- 3.6 `cost_bleed_service.py` + `/analytics/cost-bleed` — waterfall attribution (toner price Δ + paper price Δ + color mix Δ + waste Δ + yield Δ + volume Δ)
- 3.7 `CostBleedPage` — waterfall chart + per-driver narrative cards with drill-down
- 3.8 `EfficiencyPage` — trend + `MaintenanceRecommendationCard` with plaintext recommendation
- 3.9 `MaintenanceSignalBanner` on dashboard (when 7-day cost/print > 30-day baseline × 1.15)
- 3.10 Toner Yield Report (Module 6) — current cartridge status, history table, efficiency chart
- 3.11 PDF + Excel export for cost / yield / waste / efficiency / cost-bleed

### Phase 3 Exit Criteria
- [ ] Owner picks "Month" on dashboard → sees cost-per-print trend
- [ ] Clicks "Why did cost go up?" → sees attribution waterfall
- [ ] Sees maintenance banner when efficiency breaches baseline
- [ ] Can export any report as PDF or Excel

---

## PHASE 4 — Notifications, Webhooks, Automation

- Notification configs (email + Telegram) + test send
- Threshold alerts: high daily cost, toner low, yield warning
- Monthly + weekly scheduled digests via APScheduler
- Outbound webhooks + HMAC signing + delivery logs
- Print Person invite flow

---

## PHASE 5 — Admin + Hardening

- Admin dashboard (stats, cost summary, toner summary across all printers)
- User management (list, invite, role change, deactivate)
- Test suite to ≥80% backend coverage
- Security review (API key handling, file upload validation, role enforcement)
- Docker compose finalized, deployment docs

---

## Critical Files Map

### New files to create (Phase 1 only)
**Backend**
- `backend/alembic/versions/002_r11_paper_gsm_image_junction.py`
- `backend/alembic/versions/003_r12_per_cartridge_pricing.py`
- `backend/app/services/printer_service.py`
- `backend/app/services/printer_image_service.py`
- `backend/app/services/column_mapping_service.py`

**Frontend**
- `frontend/src/context/PrinterContext.tsx`
- `frontend/src/lib/colors.ts`
- `frontend/src/components/printers/PrinterSelector.tsx`
- `frontend/src/components/printers/PrinterImageDropzone.tsx`
- `frontend/src/components/printers/PrinterHeroBanner.tsx`
- `frontend/src/components/printers/DeletePrinterDialog.tsx`
- `frontend/src/components/printers/ColumnMappingExportImport.tsx`
- `frontend/src/components/charts/` (new folder — KPI cards, grouped bar chart stubs)
- `frontend/src/pages/printers/EditPrinterPage.tsx`

### Files to modify (Phase 1 only)
**Backend**
- `backend/app/models/printer.py` — add `image_url`
- `backend/app/models/paper.py` — add tolerances, `PrinterPaper` junction
- `backend/app/models/toner.py` — add `cartridge_price_per_unit`, `cartridge_rated_yield_pages`, `currency` to `TonerReplacementLog`; add composite index
- `backend/app/models/upload.py` — add `paper_gsm`, `matched_paper_id` to `PrintJob`
- `backend/app/routers/printers.py` — add image / archive / restore / hard-delete / purge / mapping-export / mapping-import endpoints
- `backend/app/routers/cost_config.py` — extend paper endpoints with `printer_ids` linking; link/unlink sub-resource
- `backend/app/routers/toner_replacements.py` — require + default per-cartridge price fields
- `backend/app/main.py` — mount `StaticFiles` at `/uploads/printers`

**Frontend**
- `frontend/src/App.tsx` — wrap app in `PrinterContext.Provider`
- `frontend/src/components/layout/TopBar.tsx` + `Sidebar.tsx` — embed `PrinterSelector`
- `frontend/src/pages/printers/AddPrinterPage.tsx` — rewrite as 5-step wizard
- `frontend/src/pages/printers/PrinterDetailPage.tsx` — hero banner, delete dialog integration, empty-state callouts
- `frontend/src/pages/printers/ColumnMappingPage.tsx` — export/import buttons
- `frontend/src/pages/settings/CostConfigPage.tsx` — paper modal with tolerances + multiselect, toner edit modal
- `frontend/src/pages/settings/TonerReplacementsPage.tsx` — per-cartridge price form fields
- `frontend/src/pages/dashboard/DashboardPage.tsx` — gradient KPI cards, period tabs, grouped bar chart stub

---

## Verification Plan

### Phase 1 (local manual test)
1. `cd backend && alembic upgrade head` — confirms both migrations apply cleanly
2. `docker ps` or check that backend (`:8001`) + frontend (`:5173`) are running
3. Browser: log in as `admin@printsight.com / Admin1234`
4. Click "Add Printer" → walk through all 5 wizard steps → upload an image → confirm printer appears in selector with hero banner
5. On `/printers/{id}/mapping` → Export mapping → re-import the same file → diff should be empty
6. On `/settings/costs` → add a paper with GSM 150–200, tolerances 2 mm, link to printer → edit it → unlink → relink
7. On `/settings/costs` → add a toner (Black @ ₹5000, 10000 pages) → click pencil → edit to ₹5500 → confirm change
8. On `/settings/toner-replacements` → log a replacement for Black → confirm the form pre-fills ₹5500 / 10000, allow edit to ₹5200, save → inspect `toner_replacement_logs` table in DB: `cartridge_price_per_unit = 5200`
9. Try to `DELETE /printers/{id}` with no jobs → succeeds. Create another printer, upload any CSV (even failing) → `DELETE` → should return 409 with counts. Use purge with typed name → cascades.
10. Confirm dashboard shell renders with placeholder data, period tabs visible, grouped bar chart (not pie) visible, hero image bound to selected printer.

### Phase 2–5
Each phase adds its own verification section when we get there — but Phase 2's core check: upload two days of CSV with a price change in between, confirm day 1 and day 2 jobs show different toner costs.

---

## Sequencing & Next Step

Recommended start order for Phase 1: **1.0 → 1.0b → 1.1 → 1.2 → 1.3** (migrations + context + design system + shell first, because every other ticket depends on them). Then 1.4–1.17 can be interleaved by a developer — most are independent once the shell is in place. 1.18 closes the phase.

When Phase 1 is done and smoke-tested, start Phase 2 from ticket 2.1.
