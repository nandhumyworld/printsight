# PRP: PrintSight

> Implementation blueprint for parallel agent execution

---

## METADATA

| Field | Value |
|-------|-------|
| **Product** | PrintSight |
| **Type** | SaaS (Software as a Service) |
| **Version** | 1.2 |
| **Created** | 2026-04-15 |
| **Revised** | 2026-04-17 (twice) |
| **Complexity** | High |
| **Modules** | 11 |
| **DB Tables** | 13 |
| **API Endpoints** | 70 |
| **Frontend Pages** | 18 |

### Revision 1.1 Changes (2026-04-17)
- Paper matching logic switched from exact `paper_type` name match to tolerant `(width, length, gsm)` match
- Added `paper_gsm` canonical CSV field and `print_jobs.paper_gsm` column
- Papers now printer-scoped via new `printer_papers` junction table (many-to-many)
- Added `printers.image_url` + image upload endpoint
- Added column-mapping export / import endpoints
- Delete semantics clarified: 3-tier (Archive / Delete / Purge) with safety guards
- Dashboard: donut replaced with grouped bar chart; color palette + sparklines added

### Revision 1.2 Changes (2026-04-17) — Printer as Root + Historical Accuracy
- **Per-cartridge toner pricing**: `toner_replacement_logs` gains `cartridge_price_per_unit` + `cartridge_rated_yield_pages`. Cost calculator resolves which cartridge was active at each job's `printed_at` and uses THAT cartridge's price. Changing `toners.price_per_unit` never mutates historical job costs.
- **`period=day`** added to all analytics / report endpoints (now `day | week | month | quarter | year`). Dashboard default view = today.
- **Cost-Bleed Attribution** endpoint (`/analytics/cost-bleed`) — explains why period cost rose vs baseline: attributes change to (toner price hikes, more color pages, more waste, volume growth, below-rated yield, paper price change).
- **Efficiency Trend** endpoint (`/analytics/efficiency`) — tracks cost-per-print, pages-per-day, avg job duration (`printed_at - arrived_at`), and flags when 7-day avg breaches 30-day baseline → maintenance alert.
- **Guided Setup Wizard** for new printers (5-step UI flow): Details → Image → Column Mapping → Papers → Toners → API Key.
- **Replacement Workflow** now captures per-cartridge price + rated yield in the form (pre-filled from `toners` defaults, editable). Empty-state banners prompt the Owner to configure toner cost BEFORE the first upload or replacement.
- **Printer-centric UI**: every screen gets a `PrinterContext` — pick a printer once, all KPIs/charts/reports scope to it automatically. The printer selector with hero image is the top-level nav anchor.

---

## PRODUCT OVERVIEW

**Description:** PrintSight turns raw printer CSV logs into actionable cost and toner yield insights. Business owners upload logs (manually or via automated API push from a printer server script), configure paper and toner costs, and get a visual dashboard showing cost per print, resource waste, and toner yield efficiency compared to manufacturer-rated yield.

**Value Proposition:** Business owners stop guessing what printing costs them. They see exactly how much each print job costs, whether their toner cartridges are delivering rated yield, and get alerts before costs spike — all without reading raw log files.

**MVP Scope:**
- [x] Owner + Print Person roles with JWT auth
- [x] Printer management with per-printer CSV column mapping
- [x] Printer API keys for automated log push from printer server
- [x] Manual CSV upload + direct API push ingestion (both methods)
- [x] Paper type cost configuration (matches CSV paper type values)
- [x] Toner configuration with rated yield per color per printer
- [x] Toner replacement logs with printer counter readings
- [x] **Toner yield report** — actual vs. rated yield, cost per page, efficiency %, estimated replacement date
- [x] Analytics dashboard with cost, waste, and specialty toner charts
- [x] Email + Telegram notifications with configurable thresholds
- [x] PDF + Excel report export
- [x] Outbound webhooks for n8n integration (HMAC-signed)
- [x] Admin panel — user management + cost/toner overview

---

## TECH STACK

| Layer | Technology | Skill Reference |
|-------|------------|-----------------|
| Backend | FastAPI + Python 3.11+ | skills/BACKEND.md |
| Frontend | React + TypeScript + Vite | skills/FRONTEND.md |
| Database | PostgreSQL + SQLAlchemy 2.0 | skills/DATABASE.md |
| Auth | JWT (access + refresh) + bcrypt | skills/BACKEND.md |
| UI | Tailwind CSS + shadcn/ui + Recharts | skills/FRONTEND.md |
| Background Jobs | APScheduler (in-process) | skills/BACKEND.md |
| PDF Export | WeasyPrint | skills/BACKEND.md |
| Excel Export | openpyxl | skills/BACKEND.md |
| CSV Parsing | pandas + Python csv | skills/BACKEND.md |
| Notifications | SMTP + Telegram Bot API | skills/BACKEND.md |
| Testing | pytest + httpx + React Testing Library | skills/TESTING.md |
| Deployment | Docker + Docker Compose | skills/DEPLOYMENT.md |

---

## DATABASE MODELS

### 1. `users`
```
id              SERIAL PRIMARY KEY
email           VARCHAR(255) UNIQUE NOT NULL
hashed_password VARCHAR(255) NOT NULL
full_name       VARCHAR(255) NOT NULL
role            ENUM('owner', 'print_person') NOT NULL DEFAULT 'owner'
is_active       BOOLEAN DEFAULT TRUE
created_at      TIMESTAMP DEFAULT NOW()
updated_at      TIMESTAMP DEFAULT NOW()
```

### 2. `refresh_tokens`
```
id          SERIAL PRIMARY KEY
user_id     INT FK → users(id) ON DELETE CASCADE
token       VARCHAR(512) UNIQUE NOT NULL
expires_at  TIMESTAMP NOT NULL
revoked     BOOLEAN DEFAULT FALSE
created_at  TIMESTAMP DEFAULT NOW()
```

### 3. `printers`
```
id             SERIAL PRIMARY KEY
owner_id       INT FK → users(id) ON DELETE CASCADE
name           VARCHAR(255) NOT NULL
model          VARCHAR(255)
type           VARCHAR(100)           -- e.g. "Digital Press", "Laser"
serial_number  VARCHAR(100)
location       VARCHAR(255)
image_url      VARCHAR(500)           -- path or URL to printer photo (nullable)
column_mapping JSONB NOT NULL DEFAULT '{}'  -- canonical → CSV header mapping
is_active      BOOLEAN DEFAULT TRUE   -- archive flag (soft delete)
created_at     TIMESTAMP DEFAULT NOW()
updated_at     TIMESTAMP DEFAULT NOW()
```
**Canonical fields stored in column_mapping:**
`job_id, job_name, status, owner_name, recorded_at, arrived_at, printed_at, color_mode, paper_type, paper_size, paper_width_mm, paper_length_mm, paper_gsm, is_duplex, copies, input_pages, printed_pages, color_pages, bw_pages, specialty_pages, gold_pages, silver_pages, clear_pages, white_pages, texture_pages, pink_pages, blank_pages, printed_sheets, waste_sheets, error_info`

### 4. `printer_api_keys`
```
id           SERIAL PRIMARY KEY
printer_id   INT FK → printers(id) ON DELETE CASCADE
owner_id     INT FK → users(id)
key_prefix   VARCHAR(12) NOT NULL      -- shown in UI e.g. "pk_abc12345"
key_hash     VARCHAR(255) NOT NULL     -- bcrypt hash, never store plain
label        VARCHAR(255)              -- "Server Room Script", "n8n"
last_used_at TIMESTAMP
is_active    BOOLEAN DEFAULT TRUE
created_at   TIMESTAMP DEFAULT NOW()
```

### 5. `papers`
```
id                   SERIAL PRIMARY KEY
owner_id             INT FK → users(id) ON DELETE CASCADE
name                 VARCHAR(500) NOT NULL   -- human label e.g. "Gloss A3 250gsm"
display_name         VARCHAR(255)
length_mm            DECIMAL(8,2) NOT NULL
width_mm             DECIMAL(8,2) NOT NULL
length_tolerance_mm  DECIMAL(6,2) DEFAULT 2  -- ± tolerance for CSV match
width_tolerance_mm   DECIMAL(6,2) DEFAULT 2
gsm_min              INT NOT NULL
gsm_max              INT NOT NULL
counter_multiplier   DECIMAL(4,2) DEFAULT 1.0  -- A3=2.0, A4=1.0
price_per_sheet      DECIMAL(10,4) NOT NULL
currency             VARCHAR(10) DEFAULT 'INR'
created_at           TIMESTAMP DEFAULT NOW()
updated_at           TIMESTAMP DEFAULT NOW()
UNIQUE(owner_id, name)
```
**Matching strategy:** Papers are matched to print jobs by **(width ± tol, length ± tol, gsm in [min,max])** AND linked to the job's printer via `printer_papers`. The legacy exact-name match on `paper_type` is a fallback only.

### 5a. `printer_papers` (junction — many-to-many)
```
printer_id INT FK → printers(id) ON DELETE CASCADE
paper_id   INT FK → papers(id)   ON DELETE CASCADE
created_at TIMESTAMP DEFAULT NOW()
PRIMARY KEY (printer_id, paper_id)
```
**Purpose:** A paper defined once by the owner can be linked to multiple printers. Cost lookup only considers papers linked to the job's printer.

### 6. `toners`
```
id                SERIAL PRIMARY KEY
printer_id        INT FK → printers(id) ON DELETE CASCADE
toner_color       VARCHAR(50) NOT NULL   -- Black, Cyan, Magenta, Yellow, Gold, Silver, Clear, White, Texture, Pink
toner_type        ENUM('standard', 'specialty') DEFAULT 'standard'
price_per_unit    DECIMAL(10,2) NOT NULL  -- DEFAULT for next cartridge (pre-fill on replacement form)
rated_yield_pages INT NOT NULL           -- DEFAULT rated yield (pre-fill on replacement form)
currency          VARCHAR(10) DEFAULT 'INR'
created_at        TIMESTAMP DEFAULT NOW()
updated_at        TIMESTAMP DEFAULT NOW()
UNIQUE(printer_id, toner_color)
```
**Role:** This table holds the configuration / current reference price for each toner color on each printer. It is **NOT** used directly in cost calculation — it only provides defaults when the user logs a replacement. Historical cost always comes from `toner_replacement_logs` (see #7).

### 7. `toner_replacement_logs`
```
id                              SERIAL PRIMARY KEY
printer_id                      INT FK → printers(id)
toner_id                        INT FK → toners(id)
replaced_by_user_id             INT FK → users(id)
counter_reading_at_replacement  INT NOT NULL   -- printer page counter at swap
replaced_at                     TIMESTAMP NOT NULL
cartridge_price_per_unit        DECIMAL(10,2) NOT NULL  -- price paid for THIS cartridge
cartridge_rated_yield_pages     INT NOT NULL            -- rated yield of THIS cartridge
currency                        VARCHAR(10) DEFAULT 'INR'
actual_yield_pages              INT            -- computed: this counter - prev counter
yield_efficiency_pct            DECIMAL(6,2)   -- actual_yield / rated_yield * 100
notes                           TEXT
created_at                      TIMESTAMP DEFAULT NOW()
INDEX (printer_id, toner_id, replaced_at)       -- for cartridge-by-date lookup
```
**Historical accuracy:** `cartridge_price_per_unit` and `cartridge_rated_yield_pages` are captured at the moment of replacement and never back-propagated. `toners.price_per_unit` acts only as the pre-fill default when the user logs the NEXT replacement. A job's toner cost is always computed from the replacement log whose `replaced_at ≤ job.printed_at` (the cartridge that was physically in the machine when the print happened).

### 8. `upload_batches`
```
id                    SERIAL PRIMARY KEY
printer_id            INT FK → printers(id)
uploaded_by_user_id   INT FK → users(id) NULLABLE  -- null for api_push
source                ENUM('manual', 'api_push') NOT NULL
filename              VARCHAR(500)
uploaded_at           TIMESTAMP DEFAULT NOW()
rows_total            INT DEFAULT 0
rows_imported         INT DEFAULT 0
rows_skipped          INT DEFAULT 0
skipped_details       JSONB DEFAULT '[]'  -- [{row_number, reason}]
status                ENUM('processing', 'completed', 'failed') DEFAULT 'processing'
```

### 9. `print_jobs`
```
id                    SERIAL PRIMARY KEY
printer_id            INT FK → printers(id)
upload_batch_id       INT FK → upload_batches(id)
job_id                VARCHAR(100) NOT NULL
job_name              VARCHAR(500)
status                VARCHAR(100)          -- Printing Completed, Error, Held, RIP Completed
owner_name            VARCHAR(255)
recorded_at           TIMESTAMP
arrived_at            TIMESTAMP
printed_at            TIMESTAMP
color_mode            VARCHAR(50)           -- Full Color, Gray Scale
paper_type            VARCHAR(500)          -- raw CSV value (fallback match only)
paper_size            VARCHAR(100)
paper_width_mm        DECIMAL(8,2)
paper_length_mm       DECIMAL(8,2)
paper_gsm             INT                    -- parsed from CSV when available
matched_paper_id      INT FK → papers(id)    -- resolved paper after match; null if no match
is_duplex             BOOLEAN DEFAULT FALSE
copies                INT DEFAULT 1
input_pages           INT DEFAULT 0
printed_pages         INT DEFAULT 0
color_pages           INT DEFAULT 0
bw_pages              INT DEFAULT 0
specialty_pages       INT DEFAULT 0
gold_pages            INT DEFAULT 0
silver_pages          INT DEFAULT 0
clear_pages           INT DEFAULT 0
white_pages           INT DEFAULT 0
texture_pages         INT DEFAULT 0
pink_pages            INT DEFAULT 0
blank_pages           INT DEFAULT 0
printed_sheets        INT DEFAULT 0
waste_sheets          INT DEFAULT 0
error_info            TEXT
computed_paper_cost   DECIMAL(12,4) DEFAULT 0
computed_toner_cost   DECIMAL(12,4) DEFAULT 0
computed_total_cost   DECIMAL(12,4) DEFAULT 0
is_waste              BOOLEAN DEFAULT FALSE
UNIQUE(printer_id, job_id, recorded_at)
```

### 10. `notification_configs`
```
id                        SERIAL PRIMARY KEY
user_id                   INT FK → users(id) ON DELETE CASCADE UNIQUE
email_enabled             BOOLEAN DEFAULT FALSE
email_address             VARCHAR(255)
telegram_enabled          BOOLEAN DEFAULT FALSE
telegram_chat_id          VARCHAR(100)
telegram_bot_token        VARCHAR(255)
high_cost_threshold       DECIMAL(10,2)      -- daily cost alert trigger
toner_low_pages_threshold INT DEFAULT 500    -- remaining pages alert
toner_yield_warning_pct   INT DEFAULT 70     -- yield efficiency % alert
monthly_report_enabled    BOOLEAN DEFAULT TRUE
weekly_summary_enabled    BOOLEAN DEFAULT FALSE
updated_at                TIMESTAMP DEFAULT NOW()
```

### 11. `webhook_configs`
```
id         SERIAL PRIMARY KEY
owner_id   INT FK → users(id) ON DELETE CASCADE
url        VARCHAR(1000) NOT NULL
events     JSONB NOT NULL DEFAULT '[]'   -- ["log_imported","high_cost_alert",...]
secret     VARCHAR(255) NOT NULL         -- HMAC signing secret
is_active  BOOLEAN DEFAULT TRUE
created_at TIMESTAMP DEFAULT NOW()
```

### 12. `webhook_delivery_logs`
```
id                 SERIAL PRIMARY KEY
webhook_config_id  INT FK → webhook_configs(id) ON DELETE CASCADE
event              VARCHAR(100)
payload            JSONB
response_status    INT
response_body      TEXT
delivered_at       TIMESTAMP DEFAULT NOW()
failed             BOOLEAN DEFAULT FALSE
```

---

## MODULES

---

### Module 1: Authentication & Role Management
**Agents:** DATABASE-AGENT + BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Auth | Role | Description |
|--------|----------|------|------|-------------|
| POST | /api/v1/auth/register | None | — | Register owner account |
| POST | /api/v1/auth/login | None | — | Login, return access + refresh tokens |
| POST | /api/v1/auth/refresh | None | — | Refresh access token |
| POST | /api/v1/auth/logout | Bearer | Any | Revoke refresh token |
| GET | /api/v1/auth/me | Bearer | Any | Current user profile |
| PUT | /api/v1/auth/me | Bearer | Any | Update name/email/password |

**Services:**
- `auth_service.py` — register, login, token creation, bcrypt hashing
- `jwt_service.py` — create_access_token, create_refresh_token, verify_token
- `deps.py` — get_current_user, require_owner, require_any_role

**Frontend Pages:**
| Route | Page | Key Components |
|-------|------|----------------|
| /login | LoginPage | LoginForm, PasswordInput |
| /register | RegisterPage | RegisterForm |
| /profile | ProfilePage | ProfileForm, ChangePasswordForm |

---

### Module 2: Printer Management & Column Mapping
**Agents:** DATABASE-AGENT + BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Auth | Role | Description |
|--------|----------|------|------|-------------|
| POST | /api/v1/printers | Bearer | Owner | Create printer |
| GET | /api/v1/printers | Bearer | Owner | List printers with stats (active by default; `?include_archived=true` to show all) |
| GET | /api/v1/printers/{id} | Bearer | Owner | Printer detail |
| PUT | /api/v1/printers/{id} | Bearer | Owner | Update printer info (name, model, location, image) |
| POST | /api/v1/printers/{id}/image | Bearer | Owner | Upload printer image (multipart, max 2MB, jpg/png/webp) |
| DELETE | /api/v1/printers/{id}/image | Bearer | Owner | Remove printer image |
| POST | /api/v1/printers/{id}/archive | Bearer | Owner | Archive (soft delete — sets is_active=false) |
| POST | /api/v1/printers/{id}/restore | Bearer | Owner | Restore archived printer |
| DELETE | /api/v1/printers/{id} | Bearer | Owner | Hard delete — **allowed only when no print_jobs / upload_batches exist**; else 409 with counts |
| DELETE | /api/v1/printers/{id}/purge | Bearer | Owner | Purge — cascade-delete printer and ALL print_jobs/batches/replacement-logs (requires `?confirm=<printer_name>`) |
| GET | /api/v1/printers/{id}/column-mapping | Bearer | Owner | Get column mapping |
| PUT | /api/v1/printers/{id}/column-mapping | Bearer | Owner | Update mapping |
| POST | /api/v1/printers/{id}/column-mapping/validate | Bearer | Owner | Validate mapping against sample CSV |
| GET | /api/v1/printers/{id}/column-mapping/export | Bearer | Owner | Export mapping as downloadable JSON |
| POST | /api/v1/printers/{id}/column-mapping/import | Bearer | Owner | Import mapping from JSON file (validates schema, returns diff preview) |

**Delete semantics (3-tier):**
| Tier | Endpoint | When to use | Data impact |
|------|----------|-------------|-------------|
| **Archive** | `POST /archive` | Temporarily hide printer, keep all history | None — just `is_active=false` |
| **Delete** | `DELETE /{id}` | Remove printer you just added by mistake | Blocked if any print_jobs/batches exist (409 with counts) |
| **Purge** | `DELETE /{id}/purge?confirm=<name>` | Permanently remove printer + all its data | Cascades: wipes print_jobs, upload_batches, toner_replacement_logs, api_keys, toners, printer_papers links |

**Services:**
- `printer_service.py` — CRUD, archive/restore/purge logic, default column mapping seeding, image file handling
- `column_mapping_service.py` — validate_mapping(csv_headers, mapping) → {matched, unmatched, missing_required}, export/import JSON schema validation

**Column mapping export JSON format:**
```json
{
  "schema_version": "1.0",
  "printer_model": "Ricoh Pro C7100",
  "exported_at": "2026-04-17T10:00:00Z",
  "column_mapping": { "job_id": "ID", "job_name": "Job Name", ... }
}
```

**Default column mapping** is pre-seeded on printer creation matching the Ricoh/Canon log format defined in INITIAL.md.

**Image storage:** Files saved to `uploads/printers/{printer_id}.{ext}` (dev) or S3/MinIO (prod via env). Served via FastAPI `StaticFiles` at `/uploads/printers/*`. Old image deleted on replacement.

**Frontend Pages:**
| Route | Page | Key Components |
|-------|------|----------------|
| /printers | PrinterListPage | PrinterCard (with image thumb), StatsChip, ArchivedToggle |
| /printers/new | AddPrinterPage | PrinterForm, ImageDropzone, ColumnMappingEditor |
| /printers/{id} | PrinterDetailPage | PrinterHeroBanner (image + name), UploadSection, JobsTable, ApiKeysSection, ArchiveButton, DeleteDialog |
| /printers/{id}/edit | EditPrinterPage | PrinterForm, ImageDropzone |
| /printers/{id}/mapping | ColumnMappingPage | MappingEditor, CSVPreviewTable, ValidationResult, ExportButton, ImportDropzone |

**ColumnMappingEditor:** Displays two columns — canonical field name (left) + text input for CSV header (right). Upload sample CSV to validate. Top bar shows **Export** and **Import** buttons. Import shows a diff (fields added/changed/removed) before applying.

**DeleteDialog:** Three radio options — "Archive (recommended, keeps history)", "Delete (only if no data exists)", "Purge (permanent, wipes N print jobs, M batches)". Purge requires typing the printer name to confirm.

**Guided Setup Wizard (`/printers/new`)** — 5 sequential steps with a progress bar; "Next" disabled until the step is complete. The Owner cannot skip steps; each step's completion seeds the next.

| Step | Name | Action | Gate to Next |
|------|------|--------|--------------|
| 1 | Printer Details | Name, model, type, serial, location | Name + model required |
| 2 | Image (optional) | Upload printer photo | Always passes |
| 3 | Column Mapping | Confirm default mapping, or import JSON, or edit fields; optionally validate against a sample CSV | Mapping JSON valid (all required canonical fields present) |
| 4 | Papers | Link at least one paper OR "I'll add later" checkbox | Either one link or the skip checkbox |
| 5 | Toners | Configure price + rated yield for at least Black; "Add more colors" button for CMYK / specialty | Black toner configured |
| 6 | Review + API Key | Summary + "Create Printer" → on success, generate first API key and show copy-once modal | — |

**Empty-state guidance** — every printer-scoped page shows contextual callouts when prerequisites are missing:
- `/printers/{id}` with no toners configured → "You haven't set toner prices yet. [Configure toners →]"
- `/printers/{id}` with no papers linked → "Link paper types to this printer so costs can be calculated. [Add papers →]"
- Upload section when toners missing → disables upload, shows "Configure toner costs before uploading logs — otherwise all toner costs will be ₹0."
- Toner replacement page when no toners configured → "Configure your toner colors and prices first. [Go to toner setup →]"
- Dashboard when no jobs imported → "No print jobs yet. [Upload CSV →] or [Generate API key →]"

---

### Module 3: Printer API Keys
**Agents:** BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Auth | Role | Description |
|--------|----------|------|------|-------------|
| POST | /api/v1/printers/{id}/api-keys | Bearer | Owner | Generate key (returned once) |
| GET | /api/v1/printers/{id}/api-keys | Bearer | Owner | List keys (prefix + label only) |
| DELETE | /api/v1/printers/{id}/api-keys/{key_id} | Bearer | Owner | Revoke key |

**Key generation logic:**
1. Generate 32-byte random key: `pk_live_{secrets.token_urlsafe(32)}`
2. Store `key_prefix` (first 12 chars) and `bcrypt(full_key)` as `key_hash`
3. Return full key **once** in response — never stored in plaintext
4. UI shows "Copy this key now — it won't be shown again"

**Frontend:**
- ApiKeysSection component inside `/printers/{id}` — generate, copy-on-create modal, list with revoke

---

### Module 4: CSV Log Upload & Parsing
**Agents:** BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | /api/v1/printers/{id}/logs/upload | Bearer (Any) | Manual CSV upload |
| POST | /api/v1/ingest/{api_key}/logs | API Key | Automated push (no user login) |
| GET | /api/v1/printers/{id}/upload-batches | Bearer (Owner) | List batch history |
| GET | /api/v1/printers/{id}/upload-batches/{batch_id} | Bearer (Owner) | Batch detail + skipped rows |
| GET | /api/v1/printers/{id}/jobs | Bearer (Owner) | List jobs with filters |

**CSV Parser Service (`csv_parser.py`):**
```python
def parse_csv(
    file: bytes,
    column_mapping: dict,
    printer_id: int,
    batch_id: int,
    existing_job_keys: set  # for dedup
) -> ParseResult:
    # 1. Load column_mapping
    # 2. Read CSV headers, map to canonical names
    # 3. For each row:
    #    a. Check dedup: (printer_id, job_id, recorded_at)
    #    b. Parse types: dates, ints, booleans
    #    c. Normalize color_mode: "Full Color" → "full_color"
    #    d. Store parsed job
    # 4. Return: imported_rows, skipped_rows, skipped_details
```

**Paper Match Service (`paper_match_service.py`):**
```python
def resolve_paper(
    printer_id: int,
    width_mm: Decimal | None,
    length_mm: Decimal | None,
    gsm: int | None,
    paper_type_raw: str | None,
    db: Session,
) -> Paper | None:
    # 1. Primary: dimension + GSM match among papers linked to this printer
    if width_mm and length_mm and gsm:
        candidates = (db.query(Paper)
                        .join(PrinterPaper, PrinterPaper.paper_id == Paper.id)
                        .filter(PrinterPaper.printer_id == printer_id)
                        .filter(func.abs(Paper.width_mm - width_mm) <= Paper.width_tolerance_mm)
                        .filter(func.abs(Paper.length_mm - length_mm) <= Paper.length_tolerance_mm)
                        .filter(Paper.gsm_min <= gsm, Paper.gsm_max >= gsm)
                        .all())
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            # tie-break: smallest combined tolerance delta
            return min(candidates, key=lambda p: abs(p.width_mm - width_mm) + abs(p.length_mm - length_mm))
    # 2. Fallback: exact name match (legacy support)
    if paper_type_raw:
        return (db.query(Paper)
                  .join(PrinterPaper, PrinterPaper.paper_id == Paper.id)
                  .filter(PrinterPaper.printer_id == printer_id, Paper.name == paper_type_raw)
                  .first())
    return None
```

**Cartridge-Resolution Service (`cartridge_resolver.py`) — NEW in 1.2:**
```python
def active_cartridge_for(
    printer_id: int, toner_color: str, at: datetime, db: Session
) -> TonerReplacementLog | Toner:
    """Return the replacement log representing the cartridge physically installed at `at`.
    Falls back to the `toners` config row if no replacement logs exist yet (bootstrap)."""
    log = (db.query(TonerReplacementLog)
             .join(Toner, Toner.id == TonerReplacementLog.toner_id)
             .filter(Toner.printer_id == printer_id, Toner.toner_color == toner_color)
             .filter(TonerReplacementLog.replaced_at <= at)
             .order_by(TonerReplacementLog.replaced_at.desc())
             .first())
    if log:
        return log  # has cartridge_price_per_unit + cartridge_rated_yield_pages
    return (db.query(Toner)
              .filter_by(printer_id=printer_id, toner_color=toner_color)
              .first())  # bootstrap: before any replacement, use config defaults

def cost_per_page(cartridge, color: str) -> Decimal:
    if cartridge is None:
        return 0
    # replacement log uses cartridge_* fields, toner config uses price_per_unit + rated_yield_pages
    price = getattr(cartridge, 'cartridge_price_per_unit', None) or cartridge.price_per_unit
    yield_p = getattr(cartridge, 'cartridge_rated_yield_pages', None) or cartridge.rated_yield_pages
    return price / yield_p if yield_p else 0
```

**Cost Calculator Service (`cost_calculator.py`):**
```python
def calculate_job_cost(job: PrintJob, db: Session) -> JobCost:
    # --- Paper ---
    paper = resolve_paper(job.printer_id, job.paper_width_mm, job.paper_length_mm,
                          job.paper_gsm, job.paper_type, db)
    job.matched_paper_id = paper.id if paper else None
    paper_cost = (job.printed_sheets
                  * (paper.price_per_sheet if paper else 0)
                  * (paper.counter_multiplier if paper else 1.0))

    # --- Toner: resolve cartridge ACTIVE at job.printed_at (historical accuracy) ---
    at = job.printed_at or job.recorded_at
    def c(color): return cost_per_page(active_cartridge_for(job.printer_id, color, at, db), color)

    toner_costs = {
        'color':   job.color_pages   * c('Cyan'),   # color pages use CMY amortized; see notes
        'bw':      job.bw_pages      * c('Black'),
        'gold':    job.gold_pages    * c('Gold'),
        'silver':  job.silver_pages  * c('Silver'),
        'clear':   job.clear_pages   * c('Clear'),
        'white':   job.white_pages   * c('White'),
        'texture': job.texture_pages * c('Texture'),
        'pink':    job.pink_pages    * c('Pink'),
    }
    toner_cost = sum(toner_costs.values())
    total_cost = paper_cost + toner_cost
    is_waste = job.status in ('Error',) or job.waste_sheets > 0
    return JobCost(paper=paper_cost, toner=toner_cost, total=total_cost, is_waste=is_waste)
```

**Idempotency rule:** Whenever a replacement log is created/edited/deleted, the cost calculator re-runs for all affected jobs in the impacted date window (between prev-replacement and next-replacement, bounded by the cartridge color). This keeps `computed_*_cost` columns in sync with the historical truth.

**Frontend:**
- UploadSection component: drag-and-drop CSV, progress indicator, batch result summary
- BatchHistoryTable: status badge, rows imported/skipped, link to skipped detail modal

---

### Module 5: Cost Configuration
**Agents:** DATABASE-AGENT + BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Auth | Role | Description |
|--------|----------|------|------|-------------|
| GET | /api/v1/cost-config/papers | Bearer | Owner | List paper types with linked printer IDs |
| POST | /api/v1/cost-config/papers | Bearer | Owner | Create paper type (body includes `printer_ids: int[]` to link) |
| PUT | /api/v1/cost-config/papers/{id} | Bearer | Owner | Update paper (incl. tolerances + `printer_ids` to replace links) |
| DELETE | /api/v1/cost-config/papers/{id} | Bearer | Owner | Delete |
| GET | /api/v1/printers/{id}/papers | Bearer | Owner | List papers linked to this printer |
| POST | /api/v1/printers/{id}/papers/{paper_id} | Bearer | Owner | Link paper to printer |
| DELETE | /api/v1/printers/{id}/papers/{paper_id} | Bearer | Owner | Unlink paper from printer |
| GET | /api/v1/printers/{id}/toners | Bearer | Owner | List toner configs |
| POST | /api/v1/printers/{id}/toners | Bearer | Owner | Add toner config |
| PUT | /api/v1/printers/{id}/toners/{toner_id} | Bearer | Owner | Update toner (price, rated yield, color, type) |
| DELETE | /api/v1/printers/{id}/toners/{toner_id} | Bearer | Owner | Delete |
| GET | /api/v1/printers/{id}/toner-replacements | Bearer | Any | List replacements |
| POST | /api/v1/printers/{id}/toner-replacements | Bearer | Any | Log replacement |
| PUT | /api/v1/printers/{id}/toner-replacements/{log_id} | Bearer | Any* | Edit (*Print Person: 24h window) |
| DELETE | /api/v1/printers/{id}/toner-replacements/{log_id} | Bearer | Owner | Delete |

**Replacement form (required fields on `POST /toner-replacements`):**
```
counter_reading_at_replacement   INT   (required)
replaced_at                      TS    (required, default: now)
cartridge_price_per_unit         DEC   (required; pre-filled from toners.price_per_unit)
cartridge_rated_yield_pages      INT   (required; pre-filled from toners.rated_yield_pages)
notes                            TEXT
```
**UI behaviour:** The replacement modal's first tab shows *"Current default price for {color}: ₹{X} / {Y} pages. If you paid a different price for THIS cartridge, update it now — the new price only applies to prints made after this replacement date."* The user can edit both values. An "Update default too" checkbox copies the entered price back into `toners.price_per_unit` so future replacements default to the new price.

**Yield auto-calculation on replacement log creation:**
```python
# When POST /toner-replacements is called:
prev = get_last_replacement(printer_id, toner_id)
if prev:
    actual_yield = counter_reading - prev.counter_reading_at_replacement
    # Yield efficiency uses THIS (previous) cartridge's rated yield — not the new one
    efficiency = (actual_yield / prev.cartridge_rated_yield_pages) * 100
    log.actual_yield_pages = actual_yield
    log.yield_efficiency_pct = efficiency
# Then re-cost jobs in the window (prev.replaced_at, now)
recost_jobs_in_window(printer_id, toner_color, prev.replaced_at if prev else None, log.replaced_at, db)
```

**Frontend Pages:**
| Route | Page | Key Components |
|-------|------|----------------|
| /settings/costs | CostConfigPage | PaperTypesTable (with tolerance + linked-printer chips), AddPaperModal (with PrinterMultiselect + width/length/GSM/tolerance inputs), EditPaperModal, TonerConfigByPrinter (with inline Edit pencil per toner row), EditTonerModal |
| /settings/toner-replacements | TonerReplacementsPage | ReplacementLogTable, AddReplacementModal (with counter input), EditReplacementModal (Owner always, Print Person ≤24h) |

---

### Module 6: Toner Yield Report (Key Feature)
**Agents:** BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Auth | Role | Description |
|--------|----------|------|------|-------------|
| GET | /api/v1/reports/toner-yield | Bearer | Owner | Full yield report |
| GET | /api/v1/reports/toner-yield/current-status | Bearer | Owner | Live cartridge status per color |
| GET | /api/v1/reports/toner-yield/history | Bearer | Owner | Historical yield table |
| GET | /api/v1/reports/toner-yield/export | Bearer | Owner | PDF or Excel download |

**Yield Report Service (`yield_report_service.py`):**
```python
def get_current_cartridge_status(printer_id: int, db: Session) -> list[CartridgeStatus]:
    for each toner color configured for this printer:
        last_replacement = latest toner_replacement_log
        pages_used = current_counter - last_replacement.counter_reading
        remaining  = toner.rated_yield_pages - pages_used
        daily_rate = avg_pages_per_day(printer_id, last_30_days)
        est_days   = remaining / daily_rate if daily_rate > 0 else None
        est_date   = today + timedelta(days=est_days) if est_days else None
        pct_used   = pages_used / toner.rated_yield_pages * 100
        return CartridgeStatus(
            toner_color, pages_used, remaining, pct_used,
            est_replacement_date=est_date,
            actual_cost_per_page=toner.price / pages_used if pages_used > 0 else None
        )

def get_historical_yield(printer_id: int, toner_color: str) -> list[YieldRecord]:
    for each replacement log:
        return YieldRecord(
            replaced_at, toner_color,
            rated_yield=toner.rated_yield_pages,
            actual_yield=log.actual_yield_pages,
            efficiency_pct=log.yield_efficiency_pct,
            actual_cost_per_page=toner.price / log.actual_yield_pages,
            rated_cost_per_page=toner.price / toner.rated_yield_pages,
            cost_variance_pct=...,
            early_replacement_flag=log.yield_efficiency_pct < 80
        )
```

**Frontend Page `/reports/toner-yield`:**
| Section | Component | Chart Type |
|---------|-----------|------------|
| Current Status | CartridgeStatusCards | Progress bars per color |
| Yield History Table | YieldHistoryTable | Table with efficiency badge (green/yellow/red) |
| Yield Efficiency Chart | YieldEfficiencyChart | Bar chart: actual vs rated per swap |
| Cost Variance | CostVarianceSummary | Total overspend due to below-rated yield |
| Per-Color Comparison | ColorComparisonChart | Grouped bar chart |

---

### Module 7: Analytics Dashboard
**Agents:** BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Auth | Role | Description |
|--------|----------|------|------|-------------|
| GET | /api/v1/analytics/summary | Bearer | Owner | KPI cards (cost, pages, waste %, cost/print, avg job duration) |
| GET | /api/v1/analytics/cost-breakdown | Bearer | Owner | Cost by category (paper vs toner per color) |
| GET | /api/v1/analytics/utilization | Bearer | Owner | Pages + waste metrics |
| GET | /api/v1/analytics/trends | Bearer | Owner | Time-series data (cost, pages, cost/print per day) |
| GET | /api/v1/analytics/efficiency | Bearer | Owner | **NEW 1.2** — cost-per-print trend, avg job duration, toner consumption rate; flags maintenance signal when 7-day avg breaches 30-day baseline |
| GET | /api/v1/analytics/cost-bleed | Bearer | Owner | **NEW 1.2** — attribution: "period cost rose by ₹X, of which +₹A from toner price hikes, +₹B from more color pages, +₹C from waste, +₹D from higher volume, +₹E from below-rated yield, +₹F from paper price change" |
| GET | /api/v1/analytics/printers/compare | Bearer | Owner | Side-by-side printer comparison |
| GET | /api/v1/analytics/specialty-toner | Bearer | Owner | Specialty toner usage |

**Query params on all:** `?period=day|week|month|quarter|year&printer_id=&start_date=&end_date=`
**Default period:** `day` on `/dashboard`, `month` on `/analytics` and `/reports`.

**Cost-Bleed Attribution algorithm (`analytics_service.cost_bleed`):**
```
current_period_cost  = Σ job.computed_total_cost where printed_at in current period
baseline_period_cost = Σ job.computed_total_cost where printed_at in previous period (same length)
delta = current - baseline
Attribute delta by recomputing current jobs against baseline parameters (counterfactuals):
  • toner_price_delta   = current - (current recomputed with baseline cartridge prices)
  • paper_price_delta   = current - (current recomputed with baseline paper prices)
  • color_mix_delta     = extra color_pages × avg color cost/page
  • waste_delta         = extra (waste_sheets × paper cost)
  • yield_delta         = Σ cartridges replaced in current period with yield < rated × (rated - actual) × price/page
  • volume_delta        = delta - (sum of other deltas)  -- residual attributed to pure volume growth
```

**Efficiency metrics (`analytics_service.efficiency`):**
- `cost_per_print` = total_cost / printed_pages
- `cost_per_print_color` = color_cost / color_pages
- `cost_per_print_bw` = bw_cost / bw_pages
- `avg_job_duration_sec` = avg(printed_at - arrived_at) per period bucket
- `pages_per_day` = printed_pages / days_in_period
- `maintenance_signal`: true when rolling 7-day `cost_per_print` > 30-day baseline × 1.15 (configurable)
- Response includes `baseline_cost_per_print`, `current_cost_per_print`, `deviation_pct`, and a plaintext `recommendation` string when signal is true, e.g. *"Cost per print is 22% above your 30-day baseline. Black toner yield dropped from 8,000 to 5,200 pages on the last cartridge — consider a drum unit service."*

**Frontend Pages:**
| Route | Page | Sections |
|-------|------|----------|
| /dashboard | DashboardPage | PrinterSelector with hero image banner, Period Tabs (Day / Week / Month / Year), KPI Cards (gradient + sparkline + trend arrow), Cost Trend Area Chart, **Paper vs Toner Grouped Bar Chart** (X=date, Y=₹, 2 colored bars/day), Top Printers Table, Recent Batches, MaintenanceSignalBanner (when efficiency breaches baseline) |
| /analytics | AnalyticsPage | Filter Bar (printer + period day/week/month/quarter/year), Cost Breakdown Stacked Bar, Utilization Chart, Specialty Toner Stacked Bar, Printer Comparison Table |
| /analytics/cost-bleed | CostBleedPage | Period picker, Waterfall Chart (delta = toner price + color mix + waste + yield + volume + paper), per-driver narrative cards with drill-down to underlying jobs/cartridges |
| /analytics/efficiency | EfficiencyPage | Cost-per-print trend line with baseline, Avg job duration trend, Pages-per-day, Per-color toner consumption rate, MaintenanceRecommendationCard |

**KPI Cards:** Total Cost, Total Pages Printed, Waste %, Cost Per Print (color), Cost Per Print (B&W). Each card: gradient background (`bg-gradient-to-br from-{hue}-500 to-{hue}-600`), icon, big number, trend arrow (▲/▼ vs previous period), inline 30-day sparkline (Recharts minimal LineChart).

**Chart style rules:**
- **No donut / pie charts anywhere** — replaced with stacked or grouped bar charts (clearer over time).
- Toner series use a per-color palette: Black `#1f2937`, Cyan `#06b6d4`, Magenta `#ec4899`, Yellow `#eab308`, Gold `#f59e0b`, Silver `#94a3b8`, Clear `#e5e7eb`, White (with border) `#ffffff`, Texture `#a16207`, Pink `#f472b6`.
- Paper cost series: `#10b981` (emerald). Toner cost series: `#6366f1` (indigo).
- Dashboard hero: when a printer is selected in the top selector, show `printer.image_url` as a 128 px rounded banner image next to the printer name; falls back to icon if no image uploaded.

---

### Module 8: Reports Export
**Agents:** BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Auth | Role | Description |
|--------|----------|------|------|-------------|
| GET | /api/v1/reports/export | Bearer | Owner | Generate + stream download |
| GET | /api/v1/reports/history | Bearer | Owner | List generated reports |

**Query params:** `?type=cost|yield|waste|efficiency|cost-bleed&format=pdf|excel&period=day|week|month|quarter|year&printer_id=`

**Report Generator Service (`report_generator.py`):**
- PDF: WeasyPrint with HTML template → PDF stream
- Excel: openpyxl workbook with formatted sheets

**Report Contents per type:**
- `cost` — summary table, cost trend chart, paper vs toner breakdown, top 10 jobs by cost
- `yield` — current cartridge status, historical yield table, efficiency chart
- `waste` — waste jobs table, waste cost total, waste % trend

**Frontend Page `/reports`:**
- Report builder form: type selector, period picker, printer selector, format toggle (PDF/Excel)
- Download button → streams file
- Recent Reports table with re-download links

---

### Module 9: Notifications
**Agents:** BACKEND-AGENT + FRONTEND-AGENT + DEVOPS-AGENT

**Backend Endpoints:**
| Method | Endpoint | Auth | Role | Description |
|--------|----------|------|------|-------------|
| GET | /api/v1/notifications/config | Bearer | Owner | Get notification settings |
| PUT | /api/v1/notifications/config | Bearer | Owner | Update settings |
| POST | /api/v1/notifications/test | Bearer | Owner | Send test via all enabled channels |

**Notification Service (`notification_service.py`):**
```python
async def send_email(to: str, subject: str, body: str): ...
async def send_telegram(bot_token: str, chat_id: str, message: str): ...

async def trigger_high_cost_alert(owner_id: int, printer: Printer, daily_cost: float): ...
async def trigger_toner_low(owner_id: int, printer: Printer, color: str, remaining: int): ...
async def trigger_yield_warning(owner_id: int, printer: Printer, log: TonerReplacementLog): ...
async def send_monthly_report(owner_id: int): ...
async def send_weekly_summary(owner_id: int): ...
```

**APScheduler Jobs (started in `main.py` lifespan):**
```python
scheduler.add_job(run_daily_cost_alerts,   'cron', hour=20)          # 8pm daily
scheduler.add_job(check_toner_low_levels,  'cron', hour=9)           # 9am daily
scheduler.add_job(send_monthly_reports,    'cron', day=1, hour=8)    # 1st of month 8am
scheduler.add_job(send_weekly_summaries,   'cron', day_of_week='mon', hour=8)
```

**Frontend Page `/settings/notifications`:**
- Email toggle + address input
- Telegram toggle + bot token + chat ID inputs + "How to get your Chat ID" help text
- Threshold inputs: daily cost limit, toner low pages, yield warning %
- Monthly/weekly report toggles
- "Send Test Notification" button

---

### Module 10: Outbound Webhooks
**Agents:** BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Auth | Role | Description |
|--------|----------|------|------|-------------|
| GET | /api/v1/webhooks | Bearer | Owner | List webhook configs |
| POST | /api/v1/webhooks | Bearer | Owner | Create webhook |
| PUT | /api/v1/webhooks/{id} | Bearer | Owner | Update |
| DELETE | /api/v1/webhooks/{id} | Bearer | Owner | Delete |
| POST | /api/v1/webhooks/{id}/test | Bearer | Owner | Send test payload |
| GET | /api/v1/webhooks/{id}/logs | Bearer | Owner | Delivery history |

**Webhook Dispatcher Service (`webhook_dispatcher.py`):**
```python
async def dispatch_event(owner_id: int, event: str, payload: dict):
    configs = get_active_webhooks_for_event(owner_id, event)
    for config in configs:
        signature = hmac.new(config.secret.encode(), json.dumps(payload).encode(), 'sha256').hexdigest()
        headers = {
            'Content-Type': 'application/json',
            'X-PrintSight-Event': event,
            'X-PrintSight-Signature': f'sha256={signature}'
        }
        try:
            r = await httpx.post(config.url, json=payload, headers=headers, timeout=10)
            log_delivery(config.id, event, payload, r.status_code, success=True)
        except Exception as e:
            log_delivery(config.id, event, payload, None, success=False)
```

**Webhook Events fired:**
| Event | When |
|-------|------|
| `log_imported` | After CSV batch completes |
| `high_cost_alert` | Daily cost > threshold |
| `toner_low` | Estimated remaining pages < threshold |
| `toner_yield_warning` | Yield efficiency < warning % |
| `monthly_report_ready` | Monthly report generated |
| `weekly_summary_ready` | Weekly summary generated |

**Frontend Page `/settings/webhooks`:**
- Webhook list with status badge
- Add webhook form: URL, secret, events multiselect (checkboxes)
- Test button per webhook
- Delivery logs expandable panel (last 20 deliveries, status badge, response preview)

---

### Module 11: Admin Panel
**Agents:** BACKEND-AGENT + FRONTEND-AGENT

**Backend Endpoints:**
| Method | Endpoint | Auth | Role | Description |
|--------|----------|------|------|-------------|
| GET | /api/v1/admin/users | Bearer | Owner | List all users |
| POST | /api/v1/admin/users | Bearer | Owner | Create/invite Print Person |
| PUT | /api/v1/admin/users/{id} | Bearer | Owner | Update role / deactivate |
| DELETE | /api/v1/admin/users/{id} | Bearer | Owner | Remove user |
| GET | /api/v1/admin/stats | Bearer | Owner | Platform stats |
| GET | /api/v1/admin/cost-summary | Bearer | Owner | Cost breakdown all printers |
| GET | /api/v1/admin/toner-summary | Bearer | Owner | Toner yield overview all printers |

**Frontend Pages:**
| Route | Page | Sections |
|-------|------|----------|
| /admin | AdminDashboardPage | Stats cards (total users, printers, prints, cost), Cost Summary table, Toner Health Overview |
| /admin/users | UserManagementPage | Users table (name, email, role, status), Invite Print Person modal, Role change + deactivate actions |

---

## PHASE EXECUTION PLAN

---

### Phase 1: Foundation (4 agents in parallel)

**DATABASE-AGENT** — `skills/DATABASE.md`
- Create `backend/app/database.py` (SQLAlchemy engine, session, Base)
- Create all 13 SQLAlchemy models in `backend/app/models/`
  - `user.py` — User, RefreshToken
  - `printer.py` — Printer (incl. `image_url`), PrinterApiKey
  - `paper.py` — Paper (incl. tolerances), PrinterPaper (junction)
  - `toner.py` — Toner, TonerReplacementLog
  - `upload.py` — UploadBatch, PrintJob (incl. `paper_gsm`, `matched_paper_id`)
  - `notification.py` — NotificationConfig
  - `webhook.py` — WebhookConfig, WebhookDeliveryLog
- Create `backend/app/models/__init__.py` (export all)
- Create Alembic initial migration (`001_initial.py`) — covers all 13 tables
- Create follow-up migration (`002_r11_paper_gsm_image_junction.py`) — for repos already at Rev 1.0: adds `printers.image_url`, `papers.width_tolerance_mm`, `papers.length_tolerance_mm`, `print_jobs.paper_gsm`, `print_jobs.matched_paper_id`, creates `printer_papers` table
- Create migration (`003_r12_per_cartridge_pricing.py`) — adds `toner_replacement_logs.cartridge_price_per_unit`, `toner_replacement_logs.cartridge_rated_yield_pages`, `toner_replacement_logs.currency`, and an index on `(printer_id, toner_id, replaced_at)` for fast cartridge lookup. Backfills existing rows with the current `toners.price_per_unit` / `rated_yield_pages` values as a best-effort starting point.
- Create `backend/app/schemas/` — Pydantic schemas for all models (Create, Update, Response variants)

**BACKEND-AGENT** — `skills/BACKEND.md`
- Scaffold `backend/` project structure
- Create `backend/app/main.py` — FastAPI app, CORS, lifespan (APScheduler), router includes
- Create `backend/app/config.py` — Settings via pydantic-settings
- Create `backend/app/auth/deps.py` — JWT dependencies: get_current_user, require_owner, require_any_role
- Create `backend/requirements.txt`

**FRONTEND-AGENT** — `skills/FRONTEND.md`
- Scaffold `frontend/` with Vite + React + TypeScript
- Install: tailwindcss, shadcn/ui, recharts, react-router-dom, react-query, axios, react-hook-form, zod
- Create folder structure: `components/`, `pages/`, `hooks/`, `services/`, `context/`, `types/`
- Create `src/types/index.ts` — all TypeScript interfaces (User, Printer, PrintJob, Paper, Toner, etc.)
- Create `src/services/api.ts` — axios instance with JWT interceptor + refresh logic
- Create `src/context/AuthContext.tsx` — auth state, login/logout
- Create `src/components/layout/` — Sidebar, TopBar, ProtectedRoute, RoleGuard

**DEVOPS-AGENT** — `skills/DEPLOYMENT.md`
- Create `docker-compose.yml` — postgres, backend, frontend services
- Create `backend/Dockerfile`
- Create `frontend/Dockerfile`
- Create `.env.example` with all required variables
- Create `backend/alembic.ini` + `backend/alembic/env.py`
- Create `backend/app/scheduler.py` — APScheduler setup with placeholder jobs

**Validation Gate 1:**
```bash
cd backend && pip install -r requirements.txt
alembic upgrade head
cd frontend && npm install
docker-compose config --quiet
```

---

### Phase 2: Core Modules (agent pairs in parallel)

**Pair A — Auth Module:**
- BACKEND: `routers/auth.py`, `services/auth_service.py`, `services/jwt_service.py`
- FRONTEND: `/login`, `/register`, `/profile` pages + AuthContext wiring

**Pair B — Printer + Column Mapping + API Keys:**
- BACKEND: `routers/printers.py`, `services/printer_service.py`, `services/column_mapping_service.py`, `routers/api_keys.py`
- FRONTEND: `/printers`, `/printers/new`, `/printers/{id}`, `/printers/{id}/mapping` pages

**Pair C — Cost Configuration:**
- BACKEND: `routers/cost_config.py`, `services/cost_config_service.py`
- FRONTEND: `/settings/costs`, `/settings/toner-replacements` pages

**Pair D — CSV Ingestion:**
- BACKEND: `routers/ingest.py`, `services/csv_parser.py`, `services/cost_calculator.py`
- FRONTEND: UploadSection component, BatchHistoryTable, `/printers/{id}` upload section

**Validation Gate 2:**
```bash
cd backend && ruff check app/ && python -m mypy app/ --ignore-missing-imports
cd frontend && npm run lint && npm run type-check
```

---

### Phase 3: Feature Modules (agent pairs in parallel)

**Pair E — Toner Yield Report:**
- BACKEND: `services/yield_report_service.py`, `routers/reports_yield.py`, yield PDF/Excel export
- FRONTEND: `/reports/toner-yield` page — CartridgeStatusCards, YieldHistoryTable, YieldEfficiencyChart, CostVarianceSummary

**Pair F — Analytics Dashboard:**
- BACKEND: `routers/analytics.py`, `services/analytics_service.py` (aggregation queries)
- FRONTEND: `/dashboard`, `/analytics` pages — KPI cards, trend charts, printer comparison

**Pair G — Notifications + Webhooks:**
- BACKEND: `routers/notifications.py`, `services/notification_service.py`, `routers/webhooks.py`, `services/webhook_dispatcher.py`, APScheduler jobs wired up
- FRONTEND: `/settings/notifications`, `/settings/webhooks` pages

**Pair H — Reports Export + Admin:**
- BACKEND: `routers/reports.py`, `services/report_generator.py` (PDF + Excel), `routers/admin.py`
- FRONTEND: `/reports`, `/admin`, `/admin/users` pages

**Validation Gate 3:**
```bash
cd backend && ruff check app/ && python -m mypy app/ --ignore-missing-imports
cd frontend && npm run lint && npm run type-check
curl http://localhost:8000/health
```

---

### Phase 4: Quality (3 agents in parallel)

**TEST-AGENT** — `skills/TESTING.md`

Unit tests (`backend/tests/unit/`):
- `test_cost_calculator.py` — paper cost, toner cost, specialty toner cost, waste detection
- `test_yield_calculator.py` — actual_yield, yield_efficiency_pct, cost_per_page, cost_variance, early replacement flag, estimated replacement date
- `test_csv_parser.py` — valid CSV, missing columns, deduplication, date parsing, boolean parsing
- `test_column_mapping.py` — validate_mapping with matched/unmatched/missing fields

Integration tests (`backend/tests/integration/`):
- `test_auth.py` — register, login, refresh, protected route, role enforcement
- `test_printers.py` — CRUD, column mapping update, validate endpoint
- `test_api_keys.py` — generate (returned once), list (prefix only), revoke, ingest auth
- `test_csv_upload.py` — manual upload, API push, dedup, skipped rows
- `test_cost_config.py` — paper CRUD, toner CRUD, replacement log with yield calc
- `test_toner_yield.py` — current status, history, export
- `test_analytics.py` — summary KPIs, cost breakdown, trend data
- `test_webhooks.py` — create, test dispatch, HMAC signature, delivery log

Frontend tests (`frontend/src/__tests__/`):
- CartridgeStatusCard, YieldHistoryTable, ColumnMappingEditor, UploadSection, KPI cards

**REVIEW-AGENT** — `skills/security-review/SKILL.md`, `skills/coding-standards/SKILL.md`

Security audit priorities:
- API key generation + storage (never plaintext, bcrypt hash)
- Ingest endpoint: API key lookup + rate limiting
- Webhook HMAC signing verification
- File upload: CSV MIME check, size limit, path traversal prevention
- Role enforcement: every Owner-only endpoint has `require_owner` dep
- JWT: expiry enforced, refresh token revocation working
- SQL: no raw queries, all via SQLAlchemy ORM

**Final Validation:**
```bash
cd backend && pytest tests/ -v --cov=app --cov-report=term-missing --cov-fail-under=80
cd frontend && npm test -- --watchAll=false
docker-compose build
docker-compose up -d
curl http://localhost:8000/health
curl http://localhost:8000/docs  # OpenAPI docs accessible
```

---

## VALIDATION GATES

| Gate | Commands | Pass Criteria |
|------|----------|---------------|
| 1 — Foundation | `pip install -r requirements.txt` `alembic upgrade head` `npm install` `docker-compose config` | No errors |
| 2 — Phase 2 | `ruff check app/` `npm run lint` `npm run type-check` | Zero lint errors, zero type errors |
| 3 — Phase 3 | `ruff check app/` `npm run type-check` `curl /health` | All pass |
| Final | `pytest --cov-fail-under=80` `npm test` `docker-compose build` | 80%+ coverage, all tests green, Docker builds |

---

## BACKEND FILE STRUCTURE

```
backend/
├── app/
│   ├── main.py                      # FastAPI app + lifespan + router includes
│   ├── config.py                    # Settings (pydantic-settings)
│   ├── database.py                  # Engine, Session, Base
│   ├── scheduler.py                 # APScheduler setup + job registration
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py                  # User, RefreshToken
│   │   ├── printer.py               # Printer, PrinterApiKey
│   │   ├── paper.py                 # Paper
│   │   ├── toner.py                 # Toner, TonerReplacementLog
│   │   ├── upload.py                # UploadBatch, PrintJob
│   │   ├── notification.py          # NotificationConfig
│   │   └── webhook.py               # WebhookConfig, WebhookDeliveryLog
│   ├── schemas/
│   │   ├── auth.py
│   │   ├── printer.py
│   │   ├── paper.py
│   │   ├── toner.py
│   │   ├── upload.py
│   │   ├── analytics.py
│   │   ├── notification.py
│   │   └── webhook.py
│   ├── routers/
│   │   ├── auth.py
│   │   ├── printers.py
│   │   ├── api_keys.py
│   │   ├── ingest.py                # /ingest/{api_key}/logs
│   │   ├── cost_config.py
│   │   ├── analytics.py
│   │   ├── reports.py               # export endpoint
│   │   ├── reports_yield.py         # toner yield report
│   │   ├── notifications.py
│   │   ├── webhooks.py
│   │   └── admin.py
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── jwt_service.py
│   │   ├── printer_service.py
│   │   ├── printer_image_service.py
│   │   ├── column_mapping_service.py
│   │   ├── paper_match_service.py
│   │   ├── cartridge_resolver.py
│   │   ├── csv_parser.py
│   │   ├── cost_calculator.py
│   │   ├── cost_bleed_service.py
│   │   ├── efficiency_service.py
│   │   ├── cost_config_service.py
│   │   ├── yield_report_service.py
│   │   ├── analytics_service.py
│   │   ├── report_generator.py
│   │   ├── notification_service.py
│   │   └── webhook_dispatcher.py
│   └── auth/
│       └── deps.py                  # get_current_user, require_owner, require_any_role
├── alembic/
│   ├── env.py
│   └── versions/
│       ├── 001_initial.py
│       ├── 002_r11_paper_gsm_image_junction.py
│       └── 003_r12_per_cartridge_pricing.py
├── uploads/
│   └── printers/                   # printer images (mounted via StaticFiles)
├── tests/
│   ├── conftest.py                  # test DB, fixtures, test client
│   ├── unit/
│   │   ├── test_cost_calculator.py
│   │   ├── test_yield_calculator.py
│   │   ├── test_csv_parser.py
│   │   └── test_column_mapping.py
│   └── integration/
│       ├── test_auth.py
│       ├── test_printers.py
│       ├── test_api_keys.py
│       ├── test_csv_upload.py
│       ├── test_cost_config.py
│       ├── test_toner_yield.py
│       ├── test_analytics.py
│       └── test_webhooks.py
├── requirements.txt
├── Dockerfile
└── alembic.ini
```

---

## FRONTEND FILE STRUCTURE

```
frontend/src/
├── types/
│   └── index.ts                    # All TS interfaces
├── services/
│   └── api.ts                      # Axios instance + interceptors
├── context/
│   └── AuthContext.tsx
├── hooks/
│   ├── useAuth.ts
│   ├── usePrinters.ts
│   ├── useTonerYield.ts
│   └── useAnalytics.ts
├── components/
│   ├── layout/
│   │   ├── Sidebar.tsx
│   │   ├── TopBar.tsx
│   │   ├── ProtectedRoute.tsx
│   │   └── RoleGuard.tsx
│   ├── charts/
│   │   ├── CostTrendChart.tsx
│   │   ├── YieldEfficiencyChart.tsx
│   │   ├── CostBreakdownDonut.tsx
│   │   └── SpecialtyTonerChart.tsx
│   ├── printers/
│   │   ├── ColumnMappingEditor.tsx
│   │   ├── ColumnMappingExportImport.tsx
│   │   ├── PrinterImageDropzone.tsx
│   │   ├── PrinterHeroBanner.tsx
│   │   ├── DeletePrinterDialog.tsx
│   │   ├── UploadSection.tsx
│   │   └── ApiKeysSection.tsx
│   └── toner/
│       ├── CartridgeStatusCard.tsx
│       └── YieldHistoryTable.tsx
└── pages/
    ├── auth/
    │   ├── LoginPage.tsx
    │   └── RegisterPage.tsx
    ├── dashboard/
    │   └── DashboardPage.tsx
    ├── printers/
    │   ├── PrinterListPage.tsx
    │   ├── AddPrinterPage.tsx
    │   ├── EditPrinterPage.tsx
    │   ├── PrinterDetailPage.tsx
    │   └── ColumnMappingPage.tsx
    ├── analytics/
    │   ├── AnalyticsPage.tsx
    │   ├── CostBleedPage.tsx
    │   └── EfficiencyPage.tsx
    ├── reports/
    │   ├── ReportsPage.tsx
    │   └── TonerYieldReportPage.tsx
    ├── settings/
    │   ├── CostConfigPage.tsx
    │   ├── TonerReplacementsPage.tsx
    │   ├── NotificationsPage.tsx
    │   └── WebhooksPage.tsx
    ├── admin/
    │   ├── AdminDashboardPage.tsx
    │   └── UserManagementPage.tsx
    └── ProfilePage.tsx
```

---

## ENVIRONMENT VARIABLES

```env
# Database
DATABASE_URL=postgresql://printsight:password@localhost:5432/printsight

# Auth
SECRET_KEY=your-256-bit-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Email (SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASSWORD=your-app-password
EMAILS_FROM_NAME=PrintSight

# Telegram
TELEGRAM_BOT_TOKEN=your-bot-token

# App
ALLOWED_ORIGINS=http://localhost:5173
MAX_CSV_UPLOAD_SIZE_MB=10
APP_ENV=development

# Frontend
VITE_API_URL=http://localhost:8000
```

---

## ACCEPTANCE CRITERIA CHECKLIST

### Auth & Roles
- [ ] Owner registers and logs in with email/password
- [ ] Print Person invited and sets up account
- [ ] Role-based access enforced — Print Person blocked from Owner-only endpoints (403)
- [ ] JWT access + refresh token flow works; expired access token triggers refresh

### Printer + Column Mapping
- [ ] Owner creates printer with default column mapping pre-filled
- [ ] Owner uploads printer image; image appears on dashboard hero banner and printer cards
- [ ] Owner edits printer name / model / location via `/printers/{id}/edit`
- [ ] Column mapping validation returns matched/unmatched fields against uploaded CSV
- [ ] Mapping update propagates to next CSV parse
- [ ] Column mapping **exports** as downloadable JSON and **imports** correctly (diff preview before apply)
- [ ] **Archive** sets `is_active=false` and hides printer from default list
- [ ] **Delete** returns 409 with print_job/batch counts when data exists
- [ ] **Purge** cascades all related data only after typing printer name to confirm

### API Keys + Ingest
- [ ] API key generated, returned once, stored as bcrypt hash
- [ ] `POST /ingest/{api_key}/logs` accepts CSV without user login
- [ ] Invalid API key returns 401
- [ ] Revoked key returns 401

### CSV Parsing + Deduplication
- [ ] CSV parsed correctly using column mapping
- [ ] `paper_gsm` canonical field parsed from CSV when mapped
- [ ] Re-upload of same file does not create duplicate print_jobs
- [ ] Skipped rows (invalid format, dedup) returned in batch response
- [ ] Paper cost + toner cost computed at import time

### Paper Matching (Revision 1.1)
- [ ] Paper resolved by `(width ± tolerance, length ± tolerance, gsm in [min,max])` scoped to printer
- [ ] `print_jobs.matched_paper_id` populated with resolved paper (null when no match)
- [ ] Unmatched rows logged in batch `skipped_details` with reason `"no_paper_match"`
- [ ] Paper editable with width/length/GSM/tolerance/price fields
- [ ] Paper linked to one or more printers via `printer_papers` junction
- [ ] Fallback: exact `paper_type` name match still works for legacy rows

### Cost Configuration (Revision 1.1)
- [ ] Owner edits toner cartridge details (price, rated yield, color, type) via pencil icon on toner row
- [ ] Linking/unlinking papers to a printer via the paper form multiselect or `/printers/{id}/papers` endpoint

### Historical Cost Accuracy (Revision 1.2 — critical)
- [ ] `toner_replacement_logs.cartridge_price_per_unit` + `cartridge_rated_yield_pages` captured on every replacement
- [ ] Replacement form pre-fills from `toners` defaults and lets Owner edit the per-cartridge price before save
- [ ] Changing `toners.price_per_unit` does NOT change any historical job's computed cost
- [ ] A new replacement at a higher price makes jobs after that replacement date more expensive; jobs before that date are unchanged
- [ ] Editing or deleting a replacement log re-runs cost calculation for jobs in the affected window only
- [ ] Bootstrap: before the first replacement log exists, cost calculation falls back to `toners` config

### Guided Workflow & Empty States (Revision 1.2)
- [ ] `/printers/new` runs a 5-step wizard that gates progress on each step
- [ ] Step 5 blocks completion until Black toner is configured
- [ ] Printer detail page shows callouts when toners / papers / logs are missing
- [ ] Upload is disabled with a warning if no toners are configured on the printer
- [ ] Toner replacement modal refuses save if `cartridge_price_per_unit` is empty or 0

### Reporting & Insights (Revision 1.2)
- [ ] All analytics + report endpoints accept `period=day`
- [ ] Dashboard defaults to today's view and scopes to the selected printer
- [ ] `/analytics/efficiency` returns cost-per-print trend, avg job duration, pages/day, maintenance_signal
- [ ] `/analytics/cost-bleed` returns waterfall deltas: toner_price_delta + paper_price_delta + color_mix_delta + waste_delta + yield_delta + volume_delta = total delta
- [ ] Maintenance banner shown on dashboard when 7-day cost/print > 30-day baseline × 1.15
- [ ] Recommendation text surfaces the top contributing driver (e.g. "Black cartridge yield dropped 35% — consider drum service")

### Toner Yield Report
- [ ] actual_yield_pages auto-calculated on replacement log creation
- [ ] yield_efficiency_pct stored correctly
- [ ] Current cartridge status shows pages used, remaining, est replacement date
- [ ] Early replacement flagged when efficiency < 80%
- [ ] Export PDF + Excel produce downloadable files

### Analytics Dashboard
- [ ] KPI cards show correct totals for selected period
- [ ] KPI cards have gradient background + 30-day sparkline + trend arrow
- [ ] Paper vs Toner comparison rendered as **grouped bar chart** (not a pie/donut)
- [ ] Printer selector at top of dashboard shows hero image when printer has one
- [ ] Charts update when period/printer filter changed
- [ ] Waste jobs (Error status + waste_sheets > 0) excluded from productive cost

### Notifications
- [ ] Email sent when daily cost > threshold
- [ ] Telegram message sent with correct bot token + chat ID
- [ ] APScheduler monthly job runs on 1st of month at 08:00

### Webhooks
- [ ] Webhook fires on log_imported, high_cost_alert, toner_low events
- [ ] X-PrintSight-Signature header present and HMAC-correct
- [ ] Delivery log records success/failure

---

## NEXT STEP

```bash
/execute-prp PRPs/printsight-prp.md
```
