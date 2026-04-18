# PrintSight Phase 1 (Tickets 1.2–1.18) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete Phase 1 of PrintSight — polished printer-centric UI with all configuration data entry working correctly.

**Architecture:** Backend-first for each feature group (fix endpoints, add new ones), then frontend (new components + page rewrites). Each task is self-contained and shippable.

**Tech Stack:** FastAPI + SQLAlchemy (backend), React 18 + Vite + TanStack Query + shadcn/ui + Recharts (frontend), Tailwind CSS, TypeScript.

---

## Current State (verified 2026-04-18)

- Migrations 002 + 003 done. Models have `image_url`, `cartridge_price_per_unit`, `cartridge_rated_yield_pages`, `PrinterPaper` junction, paper tolerances.
- `PrinterContext` exists and `App.tsx` wraps with `PrinterProvider`.
- **Gaps:** `_printer_out` doesn't return `image_url`. `PrinterUpdate` schema missing `image_url`. No archive/purge/image-upload endpoints. `ReplacementCreate` missing cartridge price fields. Paper CRUD missing tolerances. No printer-paper link/unlink. TopBar has no `PrinterSelector`. No `colors.ts`. No `EditPrinterPage`. No `DeletePrinterDialog`. Dashboard uses area chart only (needs grouped bar chart + period tabs Day/Week/Month/Year + hero banner slot).

---

## File Map

**New backend files:**
- `backend/app/services/printer_service.py` — archive, restore, hard-delete guard, purge logic
- `backend/app/services/printer_image_service.py` — save/delete image file on disk
- `backend/app/services/column_mapping_service.py` — export/import JSON diff logic

**Modified backend files:**
- `backend/app/routers/printers.py` — add `image_url` to `_printer_out` + `PrinterUpdate`; image upload/delete endpoints; archive/restore/hard-delete/purge endpoints; printer-paper link/unlink endpoints
- `backend/app/routers/cost_config.py` — add `length_tolerance_mm`/`width_tolerance_mm` to create/update; add `printer_ids` to paper list; expose `tolerance` fields in `_paper_out`
- `backend/app/routers/toner_replacements.py` — add `cartridge_price_per_unit`, `cartridge_rated_yield_pages`, `cartridge_currency` to `ReplacementCreate`; expose them in `_log_out`; add `PUT /{log_id}` update endpoint
- `backend/app/main.py` — mount `StaticFiles` at `/uploads/printers`

**New frontend files:**
- `frontend/src/lib/colors.ts` — toner color map + gradient palette constants
- `frontend/src/components/printers/PrinterSelector.tsx` — dropdown with image thumb + name
- `frontend/src/components/printers/PrinterImageDropzone.tsx` — image upload widget
- `frontend/src/components/printers/PrinterHeroBanner.tsx` — gradient hero with printer image
- `frontend/src/components/printers/DeletePrinterDialog.tsx` — 3-tier radio + typed confirm
- `frontend/src/components/printers/ColumnMappingExportImport.tsx` — export/import + diff modal
- `frontend/src/components/charts/KpiCard.tsx` — colorful gradient KPI card
- `frontend/src/components/charts/CostBreakdownChart.tsx` — grouped bar chart (paper vs toner)
- `frontend/src/pages/printers/EditPrinterPage.tsx` — edit name/model/location + image + delete

**Modified frontend files:**
- `frontend/src/components/layout/TopBar.tsx` — embed `PrinterSelector` on left
- `frontend/src/tailwind.config.js` — add gradient + accent color tokens
- `frontend/src/pages/printers/AddPrinterPage.tsx` — rewrite as 5-step wizard
- `frontend/src/pages/printers/PrinterDetailPage.tsx` — add hero banner + edit link + empty-state callouts
- `frontend/src/pages/printers/ColumnMappingPage.tsx` — add export/import buttons
- `frontend/src/pages/settings/CostConfigPage.tsx` — paper form with tolerances + printer multiselect; toner edit modal
- `frontend/src/pages/settings/TonerReplacementsPage.tsx` — add cartridge price fields to form
- `frontend/src/pages/dashboard/DashboardPage.tsx` — Day/Week/Month/Year tabs; hero banner slot; grouped bar chart
- `frontend/src/types/index.ts` — add `cartridge_*` fields to `TonerReplacementLog`; add `printer_ids` + tolerance fields to `Paper`

---

## Task 1: Design system — colors.ts + Tailwind tokens

**Files:**
- Create: `frontend/src/lib/colors.ts`
- Modify: `frontend/tailwind.config.js`

- [ ] **Step 1: Create `frontend/src/lib/colors.ts`**

```typescript
// Toner color → hex for UI badges and chart series
export const TONER_COLORS: Record<string, string> = {
  Black:   '#1a1a1a',
  Cyan:    '#0891b2',
  Magenta: '#db2777',
  Yellow:  '#ca8a04',
  Gold:    '#d97706',
  Silver:  '#64748b',
  Clear:   '#94a3b8',
  White:   '#e2e8f0',
  Texture: '#7c3aed',
  Pink:    '#ec4899',
};

// KPI card gradient classes (Tailwind)
export const KPI_GRADIENTS = [
  'from-blue-500 to-cyan-400',
  'from-violet-500 to-purple-400',
  'from-amber-500 to-orange-400',
  'from-emerald-500 to-teal-400',
];

// Chart palette for recharts series
export const CHART_PALETTE = ['#0891b2', '#7c3aed', '#d97706', '#059669', '#db2777'];
```

- [ ] **Step 2: Add gradient utility to `frontend/tailwind.config.js`**

Replace the existing file content with:

```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        border: 'hsl(var(--border))',
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        input: 'hsl(var(--border))',
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
      },
      backgroundImage: {
        'gradient-kpi-blue':    'linear-gradient(135deg, #3b82f6, #06b6d4)',
        'gradient-kpi-violet':  'linear-gradient(135deg, #8b5cf6, #a855f7)',
        'gradient-kpi-amber':   'linear-gradient(135deg, #f59e0b, #f97316)',
        'gradient-kpi-emerald': 'linear-gradient(135deg, #10b981, #14b8a6)',
      },
      borderRadius: { lg: 'var(--radius)', md: 'calc(var(--radius) - 2px)', sm: 'calc(var(--radius) - 4px)' },
    },
  },
  plugins: [],
};
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/colors.ts frontend/tailwind.config.js
git commit -m "feat: add toner color constants and KPI gradient tokens"
```

---

## Task 2: PrinterSelector component

**Files:**
- Create: `frontend/src/components/printers/PrinterSelector.tsx`

- [ ] **Step 1: Create the component**

```tsx
import { usePrinter } from '@/context/PrinterContext';
import { ChevronDown, Printer } from 'lucide-react';
import { useState, useRef, useEffect } from 'react';

export function PrinterSelector() {
  const { printers, selectedPrinter, setSelectedPrinter, isLoading } = usePrinter();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  if (isLoading) return <div className="h-8 w-40 animate-pulse rounded-md bg-muted" />;
  if (!printers.length) return null;

  const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8001';

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 rounded-md border border-border bg-card px-3 py-1.5 text-sm hover:bg-muted/50 transition-colors"
      >
        {selectedPrinter?.image_url ? (
          <img
            src={`${API_BASE}${selectedPrinter.image_url}`}
            alt=""
            className="h-5 w-5 rounded object-cover"
          />
        ) : (
          <Printer className="h-4 w-4 text-muted-foreground" />
        )}
        <span className="max-w-[140px] truncate font-medium">
          {selectedPrinter?.name ?? 'Select printer'}
        </span>
        <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
      </button>

      {open && (
        <div className="absolute left-0 top-full z-50 mt-1 min-w-[200px] rounded-md border bg-card shadow-md">
          {printers.map((p) => (
            <button
              key={p.id}
              onClick={() => { setSelectedPrinter(p); setOpen(false); }}
              className={`flex w-full items-center gap-2 px-3 py-2 text-sm hover:bg-muted/50 transition-colors ${p.id === selectedPrinter?.id ? 'bg-primary/5 font-medium' : ''}`}
            >
              {p.image_url ? (
                <img src={`${API_BASE}${p.image_url}`} alt="" className="h-5 w-5 rounded object-cover" />
              ) : (
                <Printer className="h-4 w-4 text-muted-foreground" />
              )}
              <span className="truncate">{p.name}</span>
              {!p.is_active && (
                <span className="ml-auto text-xs text-muted-foreground">archived</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/printers/PrinterSelector.tsx
git commit -m "feat: add PrinterSelector dropdown with image thumb"
```

---

## Task 3: TopBar with PrinterSelector

**Files:**
- Modify: `frontend/src/components/layout/TopBar.tsx`

- [ ] **Step 1: Update TopBar to embed PrinterSelector on left**

Replace entire file:

```tsx
import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/components/ui/button';
import { LogOut, User } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { PrinterSelector } from '@/components/printers/PrinterSelector';

export function TopBar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <header className="flex h-16 items-center justify-between border-b bg-card px-6">
      <PrinterSelector />
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 text-sm">
          <User className="h-4 w-4 text-muted-foreground" />
          <span className="font-medium">{user?.full_name}</span>
          <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary capitalize">
            {user?.role?.replace('_', ' ')}
          </span>
        </div>
        <Button variant="ghost" size="sm" onClick={handleLogout}>
          <LogOut className="h-4 w-4" />
        </Button>
      </div>
    </header>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/layout/TopBar.tsx
git commit -m "feat: embed PrinterSelector in TopBar"
```

---

## Task 4: Backend — fix _printer_out + PrinterUpdate + archive/purge endpoints

**Files:**
- Modify: `backend/app/routers/printers.py`
- Create: `backend/app/services/printer_service.py`

- [ ] **Step 1: Create `backend/app/services/printer_service.py`**

```python
"""Printer lifecycle service — archive, restore, delete, purge."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.printer import Printer
from app.models.upload import UploadBatch


def archive_printer(db: Session, printer: Printer) -> Printer:
    printer.is_active = False
    db.commit()
    db.refresh(printer)
    return printer


def restore_printer(db: Session, printer: Printer) -> Printer:
    printer.is_active = True
    db.commit()
    db.refresh(printer)
    return printer


def hard_delete_printer(db: Session, printer: Printer) -> None:
    """Delete printer if it has no uploaded jobs; raise 409 otherwise."""
    batch_count = db.query(UploadBatch).filter(UploadBatch.printer_id == printer.id).count()
    if batch_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete: printer has {batch_count} upload batch(es). Use purge to force-delete.",
        )
    db.delete(printer)
    db.commit()


def purge_printer(db: Session, printer: Printer, confirm_name: str) -> None:
    """Cascade-delete everything; caller must pass printer name as confirmation."""
    if confirm_name != printer.name:
        raise HTTPException(status_code=400, detail="Confirmation name does not match printer name")
    db.delete(printer)
    db.commit()
```

- [ ] **Step 2: Update `backend/app/routers/printers.py`**

Full replacement:

```python
"""Printers router — CRUD for printers and toner configs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, OwnerUser
from app.database import get_db
from app.models.paper import Paper, PrinterPaper
from app.models.printer import Printer
from app.models.toner import Toner, TonerType
from app.services.printer_image_service import delete_printer_image, save_printer_image
from app.services.printer_service import (
    archive_printer,
    hard_delete_printer,
    purge_printer,
    restore_printer,
)

router = APIRouter(prefix="/printers", tags=["printers"])


class PrinterCreate(BaseModel):
    name: str
    model: str | None = None
    type: str | None = None
    serial_number: str | None = None
    location: str | None = None
    column_mapping: dict[str, str] = {}


class PrinterUpdate(BaseModel):
    name: str | None = None
    model: str | None = None
    type: str | None = None
    serial_number: str | None = None
    location: str | None = None
    is_active: bool | None = None
    column_mapping: dict[str, str] | None = None
    image_url: str | None = None


class TonerCreate(BaseModel):
    toner_color: str
    toner_type: str = "standard"
    price_per_unit: float
    rated_yield_pages: int
    currency: str = "INR"


class PurgeBody(BaseModel):
    confirm_name: str


def _printer_out(p: Printer) -> dict[str, Any]:
    return {
        "id": p.id,
        "owner_id": p.owner_id,
        "name": p.name,
        "model": p.model,
        "type": p.type,
        "serial_number": p.serial_number,
        "location": p.location,
        "column_mapping": p.column_mapping,
        "image_url": p.image_url,
        "is_active": p.is_active,
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat(),
    }


def _get_printer_or_404(db: Session, printer_id: int, owner_id: int) -> Printer:
    p = db.query(Printer).filter(Printer.id == printer_id, Printer.owner_id == owner_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Printer not found")
    return p


@router.get("")
async def list_printers(current_user: CurrentUser, db: Session = Depends(get_db)):
    printers = db.query(Printer).filter(Printer.owner_id == current_user.id).all()
    return {"data": [_printer_out(p) for p in printers], "message": "ok"}


@router.post("", status_code=201)
async def create_printer(body: PrinterCreate, current_user: OwnerUser, db: Session = Depends(get_db)):
    p = Printer(owner_id=current_user.id, **body.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return {"data": _printer_out(p), "message": "Printer created"}


@router.get("/{printer_id}")
async def get_printer(printer_id: int, current_user: CurrentUser, db: Session = Depends(get_db)):
    p = _get_printer_or_404(db, printer_id, current_user.id)
    return {"data": _printer_out(p), "message": "ok"}


@router.put("/{printer_id}")
async def update_printer(printer_id: int, body: PrinterUpdate, current_user: OwnerUser, db: Session = Depends(get_db)):
    p = _get_printer_or_404(db, printer_id, current_user.id)
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(p, field, val)
    db.commit()
    db.refresh(p)
    return {"data": _printer_out(p), "message": "Printer updated"}


@router.delete("/{printer_id}", status_code=204)
async def delete_printer(printer_id: int, current_user: OwnerUser, db: Session = Depends(get_db)):
    p = _get_printer_or_404(db, printer_id, current_user.id)
    hard_delete_printer(db, p)


@router.post("/{printer_id}/archive")
async def archive(printer_id: int, current_user: OwnerUser, db: Session = Depends(get_db)):
    p = _get_printer_or_404(db, printer_id, current_user.id)
    return {"data": _printer_out(archive_printer(db, p)), "message": "Printer archived"}


@router.post("/{printer_id}/restore")
async def restore(printer_id: int, current_user: OwnerUser, db: Session = Depends(get_db)):
    p = _get_printer_or_404(db, printer_id, current_user.id)
    return {"data": _printer_out(restore_printer(db, p)), "message": "Printer restored"}


@router.post("/{printer_id}/purge", status_code=204)
async def purge(printer_id: int, body: PurgeBody, current_user: OwnerUser, db: Session = Depends(get_db)):
    p = _get_printer_or_404(db, printer_id, current_user.id)
    purge_printer(db, p, body.confirm_name)


# ---- Image sub-resource ----

@router.post("/{printer_id}/image")
async def upload_image(
    printer_id: int,
    file: UploadFile = File(...),
    current_user: OwnerUser = Depends(),
    db: Session = Depends(get_db),
):
    p = _get_printer_or_404(db, printer_id, current_user.id)
    if p.image_url:
        delete_printer_image(p.image_url)
    url = await save_printer_image(printer_id, file)
    p.image_url = url
    db.commit()
    db.refresh(p)
    return {"data": _printer_out(p), "message": "Image uploaded"}


@router.delete("/{printer_id}/image", status_code=204)
async def delete_image(printer_id: int, current_user: OwnerUser, db: Session = Depends(get_db)):
    p = _get_printer_or_404(db, printer_id, current_user.id)
    if p.image_url:
        delete_printer_image(p.image_url)
        p.image_url = None
        db.commit()


# ---- Printer-Paper link/unlink ----

@router.get("/{printer_id}/papers")
async def list_linked_papers(printer_id: int, current_user: CurrentUser, db: Session = Depends(get_db)):
    _get_printer_or_404(db, printer_id, current_user.id)
    links = db.query(PrinterPaper).filter(PrinterPaper.printer_id == printer_id).all()
    paper_ids = [lnk.paper_id for lnk in links]
    papers = db.query(Paper).filter(Paper.id.in_(paper_ids)).all() if paper_ids else []
    return {"data": [_paper_mini(p) for p in papers], "message": "ok"}


@router.post("/{printer_id}/papers/{paper_id}", status_code=201)
async def link_paper(printer_id: int, paper_id: int, current_user: OwnerUser, db: Session = Depends(get_db)):
    _get_printer_or_404(db, printer_id, current_user.id)
    paper = db.query(Paper).filter(Paper.id == paper_id, Paper.owner_id == current_user.id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    existing = db.query(PrinterPaper).filter(
        PrinterPaper.printer_id == printer_id, PrinterPaper.paper_id == paper_id
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Already linked")
    db.add(PrinterPaper(printer_id=printer_id, paper_id=paper_id))
    db.commit()
    return {"data": None, "message": "Paper linked"}


@router.delete("/{printer_id}/papers/{paper_id}", status_code=204)
async def unlink_paper(printer_id: int, paper_id: int, current_user: OwnerUser, db: Session = Depends(get_db)):
    _get_printer_or_404(db, printer_id, current_user.id)
    link = db.query(PrinterPaper).filter(
        PrinterPaper.printer_id == printer_id, PrinterPaper.paper_id == paper_id
    ).first()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    db.delete(link)
    db.commit()


def _paper_mini(p: Paper) -> dict:
    return {"id": p.id, "name": p.name, "display_name": p.display_name}


# ---- Toner sub-resource ----

@router.get("/{printer_id}/toners")
async def list_toners(printer_id: int, current_user: CurrentUser, db: Session = Depends(get_db)):
    _get_printer_or_404(db, printer_id, current_user.id)
    toners = db.query(Toner).filter(Toner.printer_id == printer_id).all()
    return {"data": [_toner_out(t) for t in toners], "message": "ok"}


@router.post("/{printer_id}/toners", status_code=201)
async def create_toner(printer_id: int, body: TonerCreate, current_user: OwnerUser, db: Session = Depends(get_db)):
    _get_printer_or_404(db, printer_id, current_user.id)
    t = Toner(
        printer_id=printer_id,
        toner_color=body.toner_color,
        toner_type=TonerType(body.toner_type),
        price_per_unit=body.price_per_unit,
        rated_yield_pages=body.rated_yield_pages,
        currency=body.currency,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"data": _toner_out(t), "message": "Toner created"}


@router.put("/{printer_id}/toners/{toner_id}")
async def update_toner(printer_id: int, toner_id: int, body: TonerCreate, current_user: OwnerUser, db: Session = Depends(get_db)):
    _get_printer_or_404(db, printer_id, current_user.id)
    t = db.query(Toner).filter(Toner.id == toner_id, Toner.printer_id == printer_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Toner not found")
    t.toner_color = body.toner_color
    t.toner_type = TonerType(body.toner_type)
    t.price_per_unit = body.price_per_unit
    t.rated_yield_pages = body.rated_yield_pages
    t.currency = body.currency
    db.commit()
    db.refresh(t)
    return {"data": _toner_out(t), "message": "Toner updated"}


@router.delete("/{printer_id}/toners/{toner_id}", status_code=204)
async def delete_toner(printer_id: int, toner_id: int, current_user: OwnerUser, db: Session = Depends(get_db)):
    _get_printer_or_404(db, printer_id, current_user.id)
    t = db.query(Toner).filter(Toner.id == toner_id, Toner.printer_id == printer_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Toner not found")
    db.delete(t)
    db.commit()


def _toner_out(t: Toner) -> dict[str, Any]:
    return {
        "id": t.id,
        "printer_id": t.printer_id,
        "toner_color": t.toner_color,
        "toner_type": t.toner_type.value,
        "price_per_unit": float(t.price_per_unit),
        "rated_yield_pages": t.rated_yield_pages,
        "currency": t.currency,
        "created_at": t.created_at.isoformat(),
    }
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/printers.py backend/app/services/printer_service.py
git commit -m "feat: add image_url to printer output, archive/restore/purge endpoints, paper link/unlink"
```

---

## Task 5: Backend — printer image service + StaticFiles mount

**Files:**
- Create: `backend/app/services/printer_image_service.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create `backend/app/services/printer_image_service.py`**

```python
"""Save and delete printer images on disk."""
from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

UPLOAD_DIR = Path("uploads/printers")
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_BYTES = 5 * 1024 * 1024  # 5 MB


async def save_printer_image(printer_id: int, file: UploadFile) -> str:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, WebP, GIF images are allowed")

    contents = await file.read()
    if len(contents) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="Image must be under 5 MB")

    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else "jpg"
    filename = f"{printer_id}_{uuid.uuid4().hex}.{ext}"
    dest = UPLOAD_DIR / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(contents)
    return f"/uploads/printers/{filename}"


def delete_printer_image(image_url: str) -> None:
    filename = image_url.lstrip("/").replace("uploads/printers/", "")
    path = UPLOAD_DIR / filename
    if path.exists():
        path.unlink()
```

- [ ] **Step 2: Mount StaticFiles in `backend/app/main.py`**

Find the line where routers are included (after `app = FastAPI(...)`) and add, right after the existing imports at the top:

```python
from fastapi.staticfiles import StaticFiles
```

And after `app` is created, before the first `app.include_router(...)`:

```python
import os
os.makedirs("uploads/printers", exist_ok=True)
app.mount("/uploads/printers", StaticFiles(directory="uploads/printers"), name="printer_images")
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/printer_image_service.py backend/app/main.py
git commit -m "feat: printer image upload/delete service + StaticFiles mount"
```

---

## Task 6: Backend — paper tolerances + toner replacement per-cartridge price

**Files:**
- Modify: `backend/app/routers/cost_config.py`
- Modify: `backend/app/routers/toner_replacements.py`

- [ ] **Step 1: Update `_paper_out` and schemas in `cost_config.py`**

Replace `PaperCreate`, `PaperUpdate`, `_paper_out` only (leave endpoints untouched except where `_paper_out` is called):

```python
class PaperCreate(BaseModel):
    name: str
    display_name: str | None = None
    length_mm: float | None = None
    width_mm: float | None = None
    length_tolerance_mm: float = 2.0
    width_tolerance_mm: float = 2.0
    gsm_min: int | None = None
    gsm_max: int | None = None
    counter_multiplier: float = 1.0
    price_per_sheet: float
    currency: str = "INR"
    printer_ids: list[int] = []


class PaperUpdate(BaseModel):
    display_name: str | None = None
    price_per_sheet: float | None = None
    currency: str | None = None
    counter_multiplier: float | None = None
    gsm_min: int | None = None
    gsm_max: int | None = None
    length_tolerance_mm: float | None = None
    width_tolerance_mm: float | None = None


def _paper_out(p: Paper) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "display_name": p.display_name,
        "length_mm": float(p.length_mm) if p.length_mm else None,
        "width_mm": float(p.width_mm) if p.width_mm else None,
        "length_tolerance_mm": float(p.length_tolerance_mm),
        "width_tolerance_mm": float(p.width_tolerance_mm),
        "gsm_min": p.gsm_min,
        "gsm_max": p.gsm_max,
        "counter_multiplier": float(p.counter_multiplier),
        "price_per_sheet": float(p.price_per_sheet),
        "currency": p.currency,
        "created_at": p.created_at.isoformat(),
    }
```

Also update `create_paper` to set tolerances and create printer-paper links:

```python
@router.post("/papers", status_code=201)
async def create_paper(body: PaperCreate, current_user: OwnerUser, db: Session = Depends(get_db)):
    from decimal import Decimal
    from app.models.paper import PrinterPaper
    existing = db.query(Paper).filter(Paper.owner_id == current_user.id, Paper.name == body.name).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Paper '{body.name}' already exists")
    p = Paper(
        owner_id=current_user.id,
        name=body.name,
        display_name=body.display_name,
        length_mm=Decimal(str(body.length_mm)) if body.length_mm else None,
        width_mm=Decimal(str(body.width_mm)) if body.width_mm else None,
        length_tolerance_mm=Decimal(str(body.length_tolerance_mm)),
        width_tolerance_mm=Decimal(str(body.width_tolerance_mm)),
        gsm_min=body.gsm_min,
        gsm_max=body.gsm_max,
        counter_multiplier=Decimal(str(body.counter_multiplier)),
        price_per_sheet=Decimal(str(body.price_per_sheet)),
        currency=body.currency,
    )
    db.add(p)
    db.flush()
    for pid in body.printer_ids:
        db.add(PrinterPaper(printer_id=pid, paper_id=p.id))
    db.commit()
    db.refresh(p)
    return {"data": _paper_out(p), "message": "Paper created"}
```

Also update `update_paper` to handle new tolerance fields:

```python
@router.put("/papers/{paper_id}")
async def update_paper(paper_id: int, body: PaperUpdate, current_user: OwnerUser, db: Session = Depends(get_db)):
    from decimal import Decimal
    p = db.query(Paper).filter(Paper.id == paper_id, Paper.owner_id == current_user.id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Paper not found")
    if body.display_name is not None:
        p.display_name = body.display_name
    if body.price_per_sheet is not None:
        p.price_per_sheet = Decimal(str(body.price_per_sheet))
    if body.currency is not None:
        p.currency = body.currency
    if body.counter_multiplier is not None:
        p.counter_multiplier = Decimal(str(body.counter_multiplier))
    if body.gsm_min is not None:
        p.gsm_min = body.gsm_min
    if body.gsm_max is not None:
        p.gsm_max = body.gsm_max
    if body.length_tolerance_mm is not None:
        p.length_tolerance_mm = Decimal(str(body.length_tolerance_mm))
    if body.width_tolerance_mm is not None:
        p.width_tolerance_mm = Decimal(str(body.width_tolerance_mm))
    db.commit()
    db.refresh(p)
    return {"data": _paper_out(p), "message": "Paper updated"}
```

- [ ] **Step 2: Update `toner_replacements.py` — add cartridge price to create + log output**

Replace `ReplacementCreate` and `_log_out` and `create_replacement`:

```python
class ReplacementCreate(BaseModel):
    printer_id: int
    toner_id: int
    counter_reading_at_replacement: int
    replaced_at: str  # ISO string
    cartridge_price_per_unit: float
    cartridge_rated_yield_pages: int
    cartridge_currency: str = "INR"
    notes: str | None = None


def _log_out(log: TonerReplacementLog) -> dict:
    toner = log.toner
    return {
        "id": log.id,
        "printer_id": log.printer_id,
        "toner_id": log.toner_id,
        "toner_color": toner.toner_color if toner else None,
        "toner_type": toner.toner_type.value if toner else None,
        "replaced_by_user_id": log.replaced_by_user_id,
        "counter_reading_at_replacement": log.counter_reading_at_replacement,
        "replaced_at": log.replaced_at.isoformat(),
        "cartridge_price_per_unit": float(log.cartridge_price_per_unit),
        "cartridge_rated_yield_pages": log.cartridge_rated_yield_pages,
        "cartridge_currency": log.cartridge_currency,
        "actual_yield_pages": log.actual_yield_pages,
        "yield_efficiency_pct": float(log.yield_efficiency_pct) if log.yield_efficiency_pct else None,
        "notes": log.notes,
        "created_at": log.created_at.isoformat(),
    }


@router.post("", status_code=201)
async def create_replacement(
    body: ReplacementCreate,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
):
    from decimal import Decimal
    printer = db.query(Printer).filter(Printer.id == body.printer_id, Printer.owner_id == current_user.id).first()
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found")

    toner = db.query(Toner).filter(Toner.id == body.toner_id, Toner.printer_id == body.printer_id).first()
    if not toner:
        raise HTTPException(status_code=404, detail="Toner not found")

    try:
        replaced_at = datetime.fromisoformat(body.replaced_at.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid replaced_at format")

    prev = db.query(TonerReplacementLog).filter(
        TonerReplacementLog.toner_id == body.toner_id
    ).order_by(TonerReplacementLog.replaced_at.desc()).first()

    actual_yield = None
    efficiency_pct = None
    if prev:
        actual_yield = body.counter_reading_at_replacement - prev.counter_reading_at_replacement
        if actual_yield > 0 and body.cartridge_rated_yield_pages > 0:
            efficiency_pct = Decimal(str(round(actual_yield / body.cartridge_rated_yield_pages * 100, 2)))

    log = TonerReplacementLog(
        printer_id=body.printer_id,
        toner_id=body.toner_id,
        replaced_by_user_id=current_user.id,
        counter_reading_at_replacement=body.counter_reading_at_replacement,
        replaced_at=replaced_at,
        cartridge_price_per_unit=Decimal(str(body.cartridge_price_per_unit)),
        cartridge_rated_yield_pages=body.cartridge_rated_yield_pages,
        cartridge_currency=body.cartridge_currency,
        actual_yield_pages=actual_yield,
        yield_efficiency_pct=efficiency_pct,
        notes=body.notes,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return {"data": _log_out(log), "message": "Replacement logged"}
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/cost_config.py backend/app/routers/toner_replacements.py
git commit -m "feat: paper tolerances + printer_ids on create; cartridge price on replacement log"
```

---

## Task 7: Backend — column mapping export/import

**Files:**
- Create: `backend/app/services/column_mapping_service.py`
- Modify: `backend/app/routers/printers.py` (add 2 endpoints at bottom)

- [ ] **Step 1: Create `backend/app/services/column_mapping_service.py`**

```python
"""Export and import column mapping JSON with diff computation."""
from __future__ import annotations


def compute_diff(
    current: dict[str, str], incoming: dict[str, str]
) -> dict[str, dict]:
    """Return {field: {old, new}} for every key that differs."""
    all_keys = set(current) | set(incoming)
    diff = {}
    for k in all_keys:
        old_val = current.get(k)
        new_val = incoming.get(k)
        if old_val != new_val:
            diff[k] = {"old": old_val, "new": new_val}
    return diff
```

- [ ] **Step 2: Add export/import endpoints to `backend/app/routers/printers.py`**

Add these at the bottom of the file (before `_toner_out`):

```python
# ---- Column mapping export / import ----

@router.get("/{printer_id}/mapping/export")
async def export_mapping(printer_id: int, current_user: CurrentUser, db: Session = Depends(get_db)):
    from fastapi.responses import JSONResponse
    p = _get_printer_or_404(db, printer_id, current_user.id)
    return JSONResponse(
        content=p.column_mapping,
        headers={"Content-Disposition": f'attachment; filename="mapping_{printer_id}.json"'},
    )


@router.post("/{printer_id}/mapping/import/preview")
async def preview_mapping_import(
    printer_id: int,
    file: UploadFile = File(...),
    current_user: OwnerUser = Depends(),
    db: Session = Depends(get_db),
):
    import json
    p = _get_printer_or_404(db, printer_id, current_user.id)
    contents = await file.read()
    try:
        incoming: dict[str, str] = json.loads(contents)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    from app.services.column_mapping_service import compute_diff
    diff = compute_diff(p.column_mapping or {}, incoming)
    return {"data": {"diff": diff, "incoming": incoming}, "message": "ok"}


@router.post("/{printer_id}/mapping/import/apply")
async def apply_mapping_import(
    printer_id: int,
    file: UploadFile = File(...),
    current_user: OwnerUser = Depends(),
    db: Session = Depends(get_db),
):
    import json
    p = _get_printer_or_404(db, printer_id, current_user.id)
    contents = await file.read()
    try:
        incoming: dict[str, str] = json.loads(contents)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    p.column_mapping = incoming
    db.commit()
    db.refresh(p)
    return {"data": _printer_out(p), "message": "Mapping applied"}
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/column_mapping_service.py backend/app/routers/printers.py
git commit -m "feat: column mapping export/import endpoints with diff preview"
```

---

## Task 8: Frontend — types update

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: Add cartridge fields to `TonerReplacementLog` and tolerance fields to `Paper`**

In `types/index.ts`, replace the `TonerReplacementLog` interface:

```typescript
export interface TonerReplacementLog {
  id: number;
  printer_id: number;
  toner_id: number;
  toner_color: string | null;
  toner_type: string | null;
  replaced_by_user_id: number;
  counter_reading_at_replacement: number;
  replaced_at: string;
  cartridge_price_per_unit: number;
  cartridge_rated_yield_pages: number;
  cartridge_currency: string;
  actual_yield_pages: number | null;
  yield_efficiency_pct: number | null;
  notes: string | null;
  created_at: string;
  toner?: Toner;
  replaced_by?: User;
}
export interface TonerReplacementCreate {
  toner_id: number;
  counter_reading_at_replacement: number;
  replaced_at: string;
  cartridge_price_per_unit: number;
  cartridge_rated_yield_pages: number;
  cartridge_currency?: string;
  notes?: string;
}
```

Replace the `Paper` interface:

```typescript
export interface Paper {
  id: number;
  owner_id: number;
  name: string;
  display_name: string | null;
  length_mm: number | null;
  width_mm: number | null;
  length_tolerance_mm: number;
  width_tolerance_mm: number;
  gsm_min: number | null;
  gsm_max: number | null;
  counter_multiplier: number;
  price_per_sheet: number;
  currency: string;
  created_at: string;
}
export interface PaperCreate {
  name: string;
  display_name?: string;
  length_mm?: number;
  width_mm?: number;
  length_tolerance_mm?: number;
  width_tolerance_mm?: number;
  gsm_min?: number;
  gsm_max?: number;
  counter_multiplier?: number;
  price_per_sheet: number;
  currency?: string;
  printer_ids?: number[];
}
export interface PaperUpdate extends Partial<PaperCreate> {}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat: update types for cartridge price fields and paper tolerances"
```

---

## Task 9: Frontend — KpiCard + CostBreakdownChart components

**Files:**
- Create: `frontend/src/components/charts/KpiCard.tsx`
- Create: `frontend/src/components/charts/CostBreakdownChart.tsx`

- [ ] **Step 1: Create `frontend/src/components/charts/KpiCard.tsx`**

```tsx
interface KpiCardProps {
  title: string;
  value: string;
  sub?: string;
  icon: React.ElementType;
  gradient: string; // e.g. 'from-blue-500 to-cyan-400'
}

export function KpiCard({ title, value, sub, icon: Icon, gradient }: KpiCardProps) {
  return (
    <div className={`rounded-xl bg-gradient-to-br ${gradient} p-5 text-white shadow-sm`}>
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-white/80">{title}</p>
        <div className="rounded-full bg-white/20 p-2">
          <Icon className="h-4 w-4" />
        </div>
      </div>
      <p className="mt-3 text-2xl font-bold">{value}</p>
      {sub && <p className="mt-1 text-xs text-white/70">{sub}</p>}
    </div>
  );
}
```

- [ ] **Step 2: Create `frontend/src/components/charts/CostBreakdownChart.tsx`**

```tsx
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend,
} from 'recharts';
import { CHART_PALETTE } from '@/lib/colors';

interface BreakdownPoint {
  date: string;
  paper_cost: number;
  toner_cost: number;
}

export function CostBreakdownChart({ data }: { data: BreakdownPoint[] }) {
  if (!data || data.length === 0) return null;
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} barGap={2}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
        <XAxis dataKey="date" tick={{ fontSize: 12 }} />
        <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `₹${v}`} />
        <Tooltip formatter={(v: number) => `₹${v.toFixed(2)}`} />
        <Legend />
        <Bar dataKey="paper_cost" name="Paper" fill={CHART_PALETTE[0]} radius={[3, 3, 0, 0]} />
        <Bar dataKey="toner_cost" name="Toner" fill={CHART_PALETTE[1]} radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/charts/
git commit -m "feat: KpiCard gradient component and CostBreakdownChart grouped bar"
```

---

## Task 10: Frontend — Dashboard visual shell

**Files:**
- Modify: `frontend/src/pages/dashboard/DashboardPage.tsx`

- [ ] **Step 1: Replace `DashboardPage.tsx`**

```tsx
import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api';
import { formatCurrency, formatPercent } from '@/lib/utils';
import { BarChart3, FileText, Printer, AlertTriangle } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { KpiCard } from '@/components/charts/KpiCard';
import { CostBreakdownChart } from '@/components/charts/CostBreakdownChart';
import { usePrinter } from '@/context/PrinterContext';

const PERIODS = [
  { label: 'Day',   value: '1d' },
  { label: 'Week',  value: '7d' },
  { label: 'Month', value: '30d' },
  { label: 'Year',  value: '365d' },
];

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8001';

export default function DashboardPage() {
  const [period, setPeriod] = useState('30d');
  const navigate = useNavigate();
  const { selectedPrinter } = usePrinter();

  const printerParam = selectedPrinter ? `&printer_id=${selectedPrinter.id}` : '';

  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ['analytics-summary', period, selectedPrinter?.id],
    queryFn: () => api.get(`/analytics/summary?period=${period}${printerParam}`).then(r => r.data.data),
  });

  const { data: trends, isLoading: trendsLoading } = useQuery({
    queryKey: ['analytics-trends', period, selectedPrinter?.id],
    queryFn: () => api.get(`/analytics/trends?period=${period}${printerParam}`).then(r => r.data.data),
  });

  const heroImage = selectedPrinter?.image_url
    ? `${API_BASE}${selectedPrinter.image_url}`
    : null;

  return (
    <div className="space-y-6">
      {/* Hero banner */}
      {selectedPrinter && (
        <div
          className="relative flex h-28 items-end overflow-hidden rounded-xl bg-gradient-to-r from-slate-800 to-slate-600 px-6 pb-4 shadow-sm"
          style={heroImage ? { backgroundImage: `url(${heroImage})`, backgroundSize: 'cover', backgroundPosition: 'center' } : {}}
        >
          <div className="absolute inset-0 bg-black/40 rounded-xl" />
          <div className="relative z-10">
            <p className="text-xs font-medium text-white/70 uppercase tracking-wide">Selected Printer</p>
            <h2 className="text-xl font-bold text-white">{selectedPrinter.name}</h2>
            {selectedPrinter.model && <p className="text-sm text-white/70">{selectedPrinter.model}</p>}
          </div>
          <button
            onClick={() => navigate(`/printers/${selectedPrinter.id}`)}
            className="relative z-10 ml-auto rounded-md bg-white/20 px-3 py-1.5 text-xs font-medium text-white hover:bg-white/30 transition-colors"
          >
            Manage →
          </button>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-muted-foreground text-sm mt-1">Print cost overview and trends</p>
        </div>
        <div className="flex gap-1 rounded-md border bg-card p-1">
          {PERIODS.map((p) => (
            <button
              key={p.value}
              onClick={() => setPeriod(p.value)}
              className={`rounded px-3 py-1.5 text-sm transition-colors ${period === p.value ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground'}`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* KPI cards */}
      {summaryLoading ? (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {[...Array(4)].map((_, i) => <div key={i} className="h-28 rounded-xl animate-pulse bg-muted" />)}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <KpiCard
            title="Total Cost"
            value={formatCurrency(summary?.total_cost ?? 0)}
            sub={`${summary?.total_jobs ?? 0} jobs`}
            icon={BarChart3}
            gradient="from-blue-500 to-cyan-400"
          />
          <KpiCard
            title="Total Pages"
            value={(summary?.total_pages ?? 0).toLocaleString()}
            sub={`₹${(summary?.cost_per_page ?? 0).toFixed(4)}/page`}
            icon={FileText}
            gradient="from-violet-500 to-purple-400"
          />
          <KpiCard
            title="Waste Cost"
            value={formatCurrency(summary?.waste_cost ?? 0)}
            sub={`${formatPercent(summary?.waste_pct ?? 0)} of pages`}
            icon={AlertTriangle}
            gradient="from-amber-500 to-orange-400"
          />
          <KpiCard
            title="Color vs B&W"
            value={`${formatPercent(summary?.color_pct ?? 0)} color`}
            sub={`${(summary?.color_pages ?? 0).toLocaleString()} color / ${(summary?.bw_pages ?? 0).toLocaleString()} B&W`}
            icon={Printer}
            gradient="from-emerald-500 to-teal-400"
          />
        </div>
      )}

      {/* Cost breakdown grouped bar */}
      <div className="rounded-xl border bg-card p-5">
        <h2 className="mb-4 font-semibold">Paper vs Toner Cost</h2>
        {trendsLoading ? (
          <div className="h-64 animate-pulse rounded bg-muted" />
        ) : trends && trends.length > 0 ? (
          <CostBreakdownChart data={trends} />
        ) : (
          <div className="flex h-64 items-center justify-center text-muted-foreground">
            <div className="text-center">
              <FileText className="mx-auto mb-2 h-10 w-10 opacity-30" />
              <p>No data yet. Upload a CSV log to get started.</p>
            </div>
          </div>
        )}
      </div>

      {/* Cost trend area chart */}
      <div className="rounded-xl border bg-card p-5">
        <h2 className="mb-4 font-semibold">Cost Trend</h2>
        {trendsLoading ? (
          <div className="h-64 animate-pulse rounded bg-muted" />
        ) : trends && trends.length > 0 ? (
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={trends}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
              <XAxis dataKey="date" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `₹${v}`} />
              <Tooltip formatter={(v: number) => formatCurrency(v)} />
              <Area type="monotone" dataKey="total_cost" name="Total Cost" stroke="hsl(var(--primary))" fill="hsl(var(--primary) / 0.1)" strokeWidth={2} />
              <Area type="monotone" dataKey="waste_cost" name="Waste Cost" stroke="#f97316" fill="rgba(249,115,22,0.1)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        ) : null}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/dashboard/DashboardPage.tsx
git commit -m "feat: dashboard with printer hero banner, gradient KPI cards, Day/Week/Month/Year tabs, grouped bar chart"
```

---

## Task 11: Frontend — PrinterHeroBanner + PrinterImageDropzone + EditPrinterPage

**Files:**
- Create: `frontend/src/components/printers/PrinterHeroBanner.tsx`
- Create: `frontend/src/components/printers/PrinterImageDropzone.tsx`
- Create: `frontend/src/pages/printers/EditPrinterPage.tsx`
- Modify: `frontend/src/App.tsx` (add route)

- [ ] **Step 1: Create `frontend/src/components/printers/PrinterHeroBanner.tsx`**

```tsx
const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8001';

interface Props {
  printer: { name: string; model?: string | null; image_url?: string | null };
}

export function PrinterHeroBanner({ printer }: Props) {
  const heroImage = printer.image_url ? `${API_BASE}${printer.image_url}` : null;
  return (
    <div
      className="relative flex h-32 items-end overflow-hidden rounded-xl bg-gradient-to-r from-slate-800 to-slate-600 px-6 pb-4"
      style={heroImage ? { backgroundImage: `url(${heroImage})`, backgroundSize: 'cover', backgroundPosition: 'center' } : {}}
    >
      <div className="absolute inset-0 bg-black/50 rounded-xl" />
      <div className="relative z-10">
        <h1 className="text-2xl font-bold text-white">{printer.name}</h1>
        {printer.model && <p className="text-sm text-white/70">{printer.model}</p>}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create `frontend/src/components/printers/PrinterImageDropzone.tsx`**

```tsx
import { useRef, useState } from 'react';
import { api } from '@/services/api';
import { ImageIcon, Trash2, Upload } from 'lucide-react';
import { Button } from '@/components/ui/button';

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8001';

interface Props {
  printerId: number;
  currentImageUrl?: string | null;
  onUpdate: (imageUrl: string | null) => void;
}

export function PrinterImageDropzone({ printerId, currentImageUrl, onUpdate }: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    setError(null);
    const form = new FormData();
    form.append('file', file);
    try {
      const { data } = await api.post(`/printers/${printerId}/image`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      onUpdate(data.data.image_url);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Upload failed');
    } finally {
      setLoading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const handleDelete = async () => {
    setLoading(true);
    try {
      await api.delete(`/printers/${printerId}/image`);
      onUpdate(null);
    } catch {
      setError('Failed to remove image');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-2">
      {currentImageUrl ? (
        <div className="relative w-32 h-32 rounded-lg overflow-hidden border">
          <img src={`${API_BASE}${currentImageUrl}`} alt="Printer" className="w-full h-full object-cover" />
          <button
            onClick={handleDelete}
            disabled={loading}
            className="absolute top-1 right-1 rounded-full bg-black/60 p-1 text-white hover:bg-black/80"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      ) : (
        <div
          onClick={() => fileRef.current?.click()}
          className="flex h-32 w-32 cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed hover:border-primary hover:bg-muted/30 transition-colors"
        >
          <ImageIcon className="h-8 w-8 text-muted-foreground mb-1" />
          <span className="text-xs text-muted-foreground">Add image</span>
        </div>
      )}
      <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()} disabled={loading}>
        <Upload className="mr-1.5 h-3.5 w-3.5" />
        {loading ? 'Uploading...' : currentImageUrl ? 'Replace' : 'Upload'}
      </Button>
      {error && <p className="text-xs text-destructive">{error}</p>}
      <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={handleFile} />
    </div>
  );
}
```

- [ ] **Step 3: Create `frontend/src/pages/printers/EditPrinterPage.tsx`**

```tsx
import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ArrowLeft } from 'lucide-react';
import { PrinterImageDropzone } from '@/components/printers/PrinterImageDropzone';
import { DeletePrinterDialog } from '@/components/printers/DeletePrinterDialog';
import { usePrinter } from '@/context/PrinterContext';

export default function EditPrinterPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { refetchPrinters } = usePrinter();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [showDelete, setShowDelete] = useState(false);

  const { data: printer, isLoading } = useQuery({
    queryKey: ['printer', id],
    queryFn: () => api.get(`/printers/${id}`).then(r => r.data.data),
  });

  const [form, setForm] = useState<{ name: string; model: string; type: string; serial_number: string; location: string } | null>(null);

  if (!form && printer) {
    setForm({
      name: printer.name ?? '',
      model: printer.model ?? '',
      type: printer.type ?? '',
      serial_number: printer.serial_number ?? '',
      location: printer.location ?? '',
    });
  }

  const set = (field: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => f ? { ...f, [field]: e.target.value } : f);

  const handleSave = async () => {
    if (!form) return;
    setSaving(true);
    setError('');
    try {
      await api.put(`/printers/${id}`, form);
      qc.invalidateQueries({ queryKey: ['printer', id] });
      await refetchPrinters();
      navigate(`/printers/${id}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const handleImageUpdate = (imageUrl: string | null) => {
    qc.invalidateQueries({ queryKey: ['printer', id] });
    refetchPrinters();
  };

  if (isLoading || !form) return <div className="h-40 animate-pulse rounded-lg bg-muted" />;
  if (!printer) return <div className="text-center py-20 text-muted-foreground">Printer not found</div>;

  return (
    <div className="max-w-lg space-y-6">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate(`/printers/${id}`)} className="text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <h1 className="text-2xl font-bold">Edit Printer</h1>
          <p className="text-sm text-muted-foreground">{printer.name}</p>
        </div>
      </div>

      <div className="rounded-lg border bg-card p-6 space-y-4">
        <div>
          <Label className="mb-2 block">Printer Image</Label>
          <PrinterImageDropzone
            printerId={Number(id)}
            currentImageUrl={printer.image_url}
            onUpdate={handleImageUpdate}
          />
        </div>

        <div className="space-y-1">
          <Label htmlFor="name">Printer Name *</Label>
          <Input id="name" value={form.name} onChange={set('name')} required />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1">
            <Label htmlFor="model">Model</Label>
            <Input id="model" value={form.model} onChange={set('model')} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="type">Type</Label>
            <Input id="type" value={form.type} onChange={set('type')} />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1">
            <Label htmlFor="serial_number">Serial Number</Label>
            <Input id="serial_number" value={form.serial_number} onChange={set('serial_number')} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="location">Location</Label>
            <Input id="location" value={form.location} onChange={set('location')} />
          </div>
        </div>

        {error && <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}
        <div className="flex gap-3 pt-2">
          <Button type="button" variant="outline" onClick={() => navigate(`/printers/${id}`)}>Cancel</Button>
          <Button onClick={handleSave} isLoading={saving}>Save Changes</Button>
        </div>
      </div>

      <div className="rounded-lg border border-destructive/30 bg-card p-5">
        <h3 className="font-medium text-destructive mb-2">Danger Zone</h3>
        <p className="text-sm text-muted-foreground mb-3">Permanently remove this printer and all associated data.</p>
        <Button variant="destructive" size="sm" onClick={() => setShowDelete(true)}>Delete Printer</Button>
      </div>

      {showDelete && (
        <DeletePrinterDialog
          printer={printer}
          onClose={() => setShowDelete(false)}
          onDeleted={async () => {
            await refetchPrinters();
            navigate('/printers');
          }}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 4: Add route to `frontend/src/App.tsx`**

After `import EditPrinterPage from ...` (add the import), then add the route:

Add import:
```tsx
import EditPrinterPage from '@/pages/printers/EditPrinterPage';
```

Add route (after the `PrinterDetailPage` route):
```tsx
<Route path="/printers/:id/edit" element={<EditPrinterPage />} />
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/printers/PrinterHeroBanner.tsx frontend/src/components/printers/PrinterImageDropzone.tsx frontend/src/pages/printers/EditPrinterPage.tsx frontend/src/App.tsx
git commit -m "feat: EditPrinterPage with image dropzone, hero banner component"
```

---

## Task 12: Frontend — DeletePrinterDialog

**Files:**
- Create: `frontend/src/components/printers/DeletePrinterDialog.tsx`

- [ ] **Step 1: Create the component**

```tsx
import { useState } from 'react';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { AlertTriangle, X } from 'lucide-react';

type DeleteMode = 'archive' | 'hard' | 'purge';

interface Props {
  printer: { id: number; name: string };
  onClose: () => void;
  onDeleted: () => void;
}

export function DeletePrinterDialog({ printer, onClose, onDeleted }: Props) {
  const [mode, setMode] = useState<DeleteMode>('archive');
  const [confirmName, setConfirmName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleAction = async () => {
    setError('');
    setLoading(true);
    try {
      if (mode === 'archive') {
        await api.post(`/printers/${printer.id}/archive`);
        onDeleted();
      } else if (mode === 'hard') {
        await api.delete(`/printers/${printer.id}`);
        onDeleted();
      } else {
        await api.post(`/printers/${printer.id}/purge`, { confirm_name: confirmName });
        onDeleted();
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Action failed');
    } finally {
      setLoading(false);
    }
  };

  const canSubmit =
    mode === 'archive' ||
    mode === 'hard' ||
    (mode === 'purge' && confirmName === printer.name);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="relative w-full max-w-md rounded-xl border bg-card p-6 shadow-xl mx-4">
        <button onClick={onClose} className="absolute right-4 top-4 text-muted-foreground hover:text-foreground">
          <X className="h-4 w-4" />
        </button>

        <div className="flex items-center gap-3 mb-4">
          <div className="rounded-full bg-destructive/10 p-2">
            <AlertTriangle className="h-5 w-5 text-destructive" />
          </div>
          <div>
            <h2 className="font-semibold">Remove Printer</h2>
            <p className="text-sm text-muted-foreground">{printer.name}</p>
          </div>
        </div>

        <div className="space-y-2 mb-4">
          {[
            { value: 'archive' as DeleteMode, label: 'Archive', desc: 'Hide from active views. Can be restored later.' },
            { value: 'hard' as DeleteMode, label: 'Delete', desc: 'Permanently delete. Only works if no uploads exist.' },
            { value: 'purge' as DeleteMode, label: 'Purge (all data)', desc: 'Cascade-delete printer + all jobs, uploads, costs.' },
          ].map((opt) => (
            <label key={opt.value} className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors ${mode === opt.value ? 'border-destructive bg-destructive/5' : 'hover:bg-muted/30'}`}>
              <input
                type="radio"
                name="deleteMode"
                value={opt.value}
                checked={mode === opt.value}
                onChange={() => setMode(opt.value)}
                className="mt-0.5"
              />
              <div>
                <p className="font-medium text-sm">{opt.label}</p>
                <p className="text-xs text-muted-foreground">{opt.desc}</p>
              </div>
            </label>
          ))}
        </div>

        {mode === 'purge' && (
          <div className="mb-4 space-y-1">
            <Label>Type <strong>{printer.name}</strong> to confirm</Label>
            <Input
              value={confirmName}
              onChange={(e) => setConfirmName(e.target.value)}
              placeholder={printer.name}
            />
          </div>
        )}

        {error && <p className="mb-3 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}

        <div className="flex gap-3">
          <Button variant="outline" onClick={onClose} disabled={loading}>Cancel</Button>
          <Button variant="destructive" onClick={handleAction} disabled={!canSubmit || loading} isLoading={loading}>
            {mode === 'archive' ? 'Archive' : mode === 'hard' ? 'Delete' : 'Purge'}
          </Button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/printers/DeletePrinterDialog.tsx
git commit -m "feat: DeletePrinterDialog with archive/delete/purge radio"
```

---

## Task 13: Frontend — ColumnMappingExportImport + ColumnMappingPage update

**Files:**
- Create: `frontend/src/components/printers/ColumnMappingExportImport.tsx`
- Modify: `frontend/src/pages/printers/ColumnMappingPage.tsx` (add export/import buttons)

- [ ] **Step 1: Create `ColumnMappingExportImport.tsx`**

```tsx
import { useRef, useState } from 'react';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Download, Upload, X, Check } from 'lucide-react';

interface DiffEntry { old: string | null; new: string | null }

interface Props {
  printerId: string;
  onApplied: () => void;
}

export function ColumnMappingExportImport({ printerId, onApplied }: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [diff, setDiff] = useState<Record<string, DiffEntry> | null>(null);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleExport = () => {
    window.open(`${import.meta.env.VITE_API_URL ?? 'http://localhost:8001'}/printers/${printerId}/mapping/export`, '_blank');
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setPendingFile(file);
    setError('');
    setLoading(true);
    const form = new FormData();
    form.append('file', file);
    try {
      const { data } = await api.post(`/printers/${printerId}/mapping/import/preview`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setDiff(data.data.diff);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Preview failed');
      setPendingFile(null);
    } finally {
      setLoading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const handleApply = async () => {
    if (!pendingFile) return;
    setLoading(true);
    const form = new FormData();
    form.append('file', pendingFile);
    try {
      await api.post(`/printers/${printerId}/mapping/import/apply`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setDiff(null);
      setPendingFile(null);
      onApplied();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Apply failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center gap-2">
      <Button variant="outline" size="sm" onClick={handleExport}>
        <Download className="mr-1.5 h-3.5 w-3.5" /> Export JSON
      </Button>
      <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()} disabled={loading}>
        <Upload className="mr-1.5 h-3.5 w-3.5" /> Import JSON
      </Button>
      <input ref={fileRef} type="file" accept=".json" className="hidden" onChange={handleFileSelect} />

      {/* Diff modal */}
      {diff !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-lg rounded-xl border bg-card p-6 shadow-xl mx-4 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold">Mapping Diff</h3>
              <button onClick={() => { setDiff(null); setPendingFile(null); }} className="text-muted-foreground hover:text-foreground">
                <X className="h-4 w-4" />
              </button>
            </div>
            {Object.keys(diff).length === 0 ? (
              <p className="text-sm text-muted-foreground">No changes — imported mapping is identical to current.</p>
            ) : (
              <div className="max-h-64 overflow-y-auto space-y-1">
                {Object.entries(diff).map(([field, { old: o, new: n }]) => (
                  <div key={field} className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm">
                    <span className="font-mono font-medium w-36 truncate">{field}</span>
                    <span className="text-destructive line-through text-xs">{o ?? '(none)'}</span>
                    <span className="text-muted-foreground">→</span>
                    <span className="text-emerald-600 text-xs">{n ?? '(removed)'}</span>
                  </div>
                ))}
              </div>
            )}
            {error && <p className="text-sm text-destructive">{error}</p>}
            <div className="flex gap-3">
              <Button variant="outline" size="sm" onClick={() => { setDiff(null); setPendingFile(null); }}>Cancel</Button>
              <Button size="sm" onClick={handleApply} disabled={loading || Object.keys(diff).length === 0} isLoading={loading}>
                <Check className="mr-1.5 h-3.5 w-3.5" /> Apply
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Read current `ColumnMappingPage.tsx` header to locate where to insert buttons**

The page currently has a header section. Find the line with `<h1` or the top action area and add:

```tsx
import { ColumnMappingExportImport } from '@/components/printers/ColumnMappingExportImport';
```

And in the header JSX, add `<ColumnMappingExportImport printerId={id!} onApplied={() => qc.invalidateQueries({ queryKey: ['printer', id] })} />` next to the existing save button area.

(Exact placement depends on current ColumnMappingPage structure — add the import at top, and place the component in the header row alongside the existing save/cancel buttons.)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/printers/ColumnMappingExportImport.tsx frontend/src/pages/printers/ColumnMappingPage.tsx
git commit -m "feat: column mapping export/import UI with diff preview modal"
```

---

## Task 14: Frontend — 5-step Setup Wizard (AddPrinterPage rewrite)

**Files:**
- Modify: `frontend/src/pages/printers/AddPrinterPage.tsx`

- [ ] **Step 1: Replace entire file**

```tsx
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Check, ChevronRight } from 'lucide-react';
import { usePrinter } from '@/context/PrinterContext';

const STEPS = [
  { label: 'Basic Info',    desc: 'Name, model, location' },
  { label: 'Toners',        desc: 'At least one toner required' },
  { label: 'Paper Types',   desc: 'Link paper configurations' },
  { label: 'Column Map',    desc: 'CSV field mapping' },
  { label: 'Review',        desc: 'Confirm and create' },
];

interface TonerDraft {
  toner_color: string;
  toner_type: string;
  price_per_unit: string;
  rated_yield_pages: string;
  currency: string;
}

export default function AddPrinterPage() {
  const navigate = useNavigate();
  const { refetchPrinters } = usePrinter();
  const [step, setStep] = useState(0);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [createdId, setCreatedId] = useState<number | null>(null);

  // Step 1 state
  const [info, setInfo] = useState({ name: '', model: '', type: '', serial_number: '', location: '' });

  // Step 2 state
  const [toners, setToners] = useState<TonerDraft[]>([
    { toner_color: 'Black', toner_type: 'standard', price_per_unit: '', rated_yield_pages: '', currency: 'INR' },
  ]);

  const setInfo$ = (f: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setInfo(p => ({ ...p, [f]: e.target.value }));

  const updateToner = (i: number, f: string, v: string) =>
    setToners(ts => ts.map((t, idx) => idx === i ? { ...t, [f]: v } : t));

  const addToner = () =>
    setToners(ts => [...ts, { toner_color: '', toner_type: 'standard', price_per_unit: '', rated_yield_pages: '', currency: 'INR' }]);

  const removeToner = (i: number) => setToners(ts => ts.filter((_, idx) => idx !== i));

  // Step 3 state — printer-paper links happen after creation
  // Step 4 state
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [mappingKey, setMappingKey] = useState('');
  const [mappingVal, setMappingVal] = useState('');

  const addMapping = () => {
    if (!mappingKey.trim() || !mappingVal.trim()) return;
    setMapping(m => ({ ...m, [mappingKey.trim()]: mappingVal.trim() }));
    setMappingKey('');
    setMappingVal('');
  };

  const removeMapping = (k: string) => setMapping(m => { const n = { ...m }; delete n[k]; return n; });

  const canNext = () => {
    if (step === 0) return info.name.trim().length > 0;
    if (step === 1) return toners.length > 0 && toners.every(t => t.toner_color && t.price_per_unit && t.rated_yield_pages);
    return true;
  };

  const handleCreate = async () => {
    setError('');
    setLoading(true);
    try {
      const { data: p } = await api.post('/printers', {
        name: info.name,
        model: info.model || undefined,
        type: info.type || undefined,
        serial_number: info.serial_number || undefined,
        location: info.location || undefined,
        column_mapping: mapping,
      });
      const pid = p.data.id;
      setCreatedId(pid);

      await Promise.all(
        toners.map(t =>
          api.post(`/printers/${pid}/toners`, {
            toner_color: t.toner_color,
            toner_type: t.toner_type,
            price_per_unit: parseFloat(t.price_per_unit),
            rated_yield_pages: parseInt(t.rated_yield_pages),
            currency: t.currency,
          })
        )
      );

      await refetchPrinters();
      navigate(`/printers/${pid}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to create printer');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl space-y-6">
      {/* Progress bar */}
      <div>
        <div className="flex items-center gap-1 mb-4">
          {STEPS.map((s, i) => (
            <div key={i} className="flex items-center gap-1">
              <div className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-medium transition-colors ${i < step ? 'bg-primary text-primary-foreground' : i === step ? 'bg-primary/20 text-primary border border-primary' : 'bg-muted text-muted-foreground'}`}>
                {i < step ? <Check className="h-3.5 w-3.5" /> : i + 1}
              </div>
              {i < STEPS.length - 1 && <div className={`h-px w-6 ${i < step ? 'bg-primary' : 'bg-border'}`} />}
            </div>
          ))}
        </div>
        <h1 className="text-2xl font-bold">{STEPS[step].label}</h1>
        <p className="text-sm text-muted-foreground">{STEPS[step].desc}</p>
      </div>

      <div className="rounded-lg border bg-card p-6 space-y-4">

        {/* Step 0: Basic Info */}
        {step === 0 && (
          <>
            <div className="space-y-1">
              <Label>Printer Name *</Label>
              <Input placeholder="e.g. HP LaserJet 1st Floor" value={info.name} onChange={setInfo$('name')} required />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <Label>Model</Label>
                <Input placeholder="HP LaserJet Pro M404n" value={info.model} onChange={setInfo$('model')} />
              </div>
              <div className="space-y-1">
                <Label>Type</Label>
                <Input placeholder="Laser / Inkjet" value={info.type} onChange={setInfo$('type')} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <Label>Serial Number</Label>
                <Input placeholder="SN-XXXXX" value={info.serial_number} onChange={setInfo$('serial_number')} />
              </div>
              <div className="space-y-1">
                <Label>Location</Label>
                <Input placeholder="Office 2B" value={info.location} onChange={setInfo$('location')} />
              </div>
            </div>
          </>
        )}

        {/* Step 1: Toners */}
        {step === 1 && (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">Add at least one toner. These become defaults for replacement logs.</p>
            {toners.map((t, i) => (
              <div key={i} className="rounded-md border p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Toner {i + 1}</span>
                  {toners.length > 1 && (
                    <button onClick={() => removeToner(i)} className="text-xs text-muted-foreground hover:text-destructive">Remove</button>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div className="space-y-1">
                    <Label>Color *</Label>
                    <Input placeholder="Black / Cyan / Gold…" value={t.toner_color} onChange={e => updateToner(i, 'toner_color', e.target.value)} />
                  </div>
                  <div className="space-y-1">
                    <Label>Type</Label>
                    <select className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm" value={t.toner_type} onChange={e => updateToner(i, 'toner_type', e.target.value)}>
                      <option value="standard">Standard</option>
                      <option value="specialty">Specialty</option>
                    </select>
                  </div>
                  <div className="space-y-1">
                    <Label>Price per Unit *</Label>
                    <Input type="number" min="0" step="0.01" placeholder="e.g. 2500" value={t.price_per_unit} onChange={e => updateToner(i, 'price_per_unit', e.target.value)} />
                  </div>
                  <div className="space-y-1">
                    <Label>Rated Yield (pages) *</Label>
                    <Input type="number" min="1" placeholder="e.g. 3000" value={t.rated_yield_pages} onChange={e => updateToner(i, 'rated_yield_pages', e.target.value)} />
                  </div>
                </div>
              </div>
            ))}
            <Button variant="outline" size="sm" onClick={addToner}>+ Add Another Toner</Button>
          </div>
        )}

        {/* Step 2: Paper Types */}
        {step === 2 && (
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">
              Paper types can be linked after creation from <strong>Settings → Cost Config</strong>.
              You can skip this step.
            </p>
            <div className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
              Paper linking is available on the printer detail page after creation.
            </div>
          </div>
        )}

        {/* Step 3: Column Mapping */}
        {step === 3 && (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">Map CSV column headers to PrintSight fields. You can also configure this later.</p>
            <div className="flex gap-2">
              <Input placeholder="CSV column name" value={mappingKey} onChange={e => setMappingKey(e.target.value)} />
              <Input placeholder="PrintSight field" value={mappingVal} onChange={e => setMappingVal(e.target.value)} />
              <Button variant="outline" size="sm" onClick={addMapping} disabled={!mappingKey || !mappingVal}>Add</Button>
            </div>
            {Object.entries(mapping).length > 0 && (
              <div className="space-y-1">
                {Object.entries(mapping).map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between rounded-md border px-3 py-1.5 text-sm">
                    <span><span className="font-mono">{k}</span> → <span className="font-mono text-primary">{v}</span></span>
                    <button onClick={() => removeMapping(k)} className="text-muted-foreground hover:text-destructive text-xs">Remove</button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Step 4: Review */}
        {step === 4 && (
          <div className="space-y-3 text-sm">
            <div className="rounded-md bg-muted/40 p-4 space-y-1">
              <p><span className="text-muted-foreground">Name:</span> <strong>{info.name}</strong></p>
              {info.model && <p><span className="text-muted-foreground">Model:</span> {info.model}</p>}
              {info.type && <p><span className="text-muted-foreground">Type:</span> {info.type}</p>}
              {info.location && <p><span className="text-muted-foreground">Location:</span> {info.location}</p>}
              <p><span className="text-muted-foreground">Toners:</span> {toners.map(t => t.toner_color).join(', ')}</p>
              <p><span className="text-muted-foreground">Mapping fields:</span> {Object.keys(mapping).length || 'none'}</p>
            </div>
            {error && <p className="rounded-md bg-destructive/10 px-3 py-2 text-destructive">{error}</p>}
          </div>
        )}
      </div>

      {/* Navigation */}
      <div className="flex items-center justify-between">
        <Button variant="outline" onClick={() => step > 0 ? setStep(s => s - 1) : navigate('/printers')} disabled={loading}>
          {step === 0 ? 'Cancel' : '← Back'}
        </Button>
        {step < STEPS.length - 1 ? (
          <Button onClick={() => setStep(s => s + 1)} disabled={!canNext()}>
            Next <ChevronRight className="ml-1.5 h-4 w-4" />
          </Button>
        ) : (
          <Button onClick={handleCreate} isLoading={loading}>
            Create Printer
          </Button>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/printers/AddPrinterPage.tsx
git commit -m "feat: 5-step setup wizard for adding a new printer"
```

---

## Task 15: Frontend — Paper modal with tolerances + toner edit modal (CostConfigPage)

**Files:**
- Modify: `frontend/src/pages/settings/CostConfigPage.tsx`

- [ ] **Step 1: Read the current file fully, then replace `AddPaperForm` to include tolerance fields and printer multiselect, and add an `EditTonerModal`**

Add `length_tolerance_mm`, `width_tolerance_mm`, `gsm_min`, `gsm_max`, `length_mm`, `width_mm` to `AddPaperForm` state and submit:

```tsx
// In AddPaperForm, replace state:
const [form, setForm] = useState({
  name: '',
  display_name: '',
  length_mm: '',
  width_mm: '',
  length_tolerance_mm: '2',
  width_tolerance_mm: '2',
  gsm_min: '',
  gsm_max: '',
  price_per_sheet: '',
  currency: 'INR',
});

// Replace create mutationFn payload:
mutationFn: () => api.post('/cost-config/papers', {
  name: form.name,
  display_name: form.display_name || undefined,
  length_mm: form.length_mm ? parseFloat(form.length_mm) : undefined,
  width_mm: form.width_mm ? parseFloat(form.width_mm) : undefined,
  length_tolerance_mm: parseFloat(form.length_tolerance_mm),
  width_tolerance_mm: parseFloat(form.width_tolerance_mm),
  gsm_min: form.gsm_min ? parseInt(form.gsm_min) : undefined,
  gsm_max: form.gsm_max ? parseInt(form.gsm_max) : undefined,
  price_per_sheet: parseFloat(form.price_per_sheet),
  currency: form.currency,
}),
```

Add these fields to the form JSX (after the existing name/display_name fields):

```tsx
<div className="grid grid-cols-2 gap-3">
  <div className="space-y-1">
    <Label>Width (mm)</Label>
    <Input type="number" placeholder="210" value={form.width_mm} onChange={set('width_mm')} />
  </div>
  <div className="space-y-1">
    <Label>Length (mm)</Label>
    <Input type="number" placeholder="297" value={form.length_mm} onChange={set('length_mm')} />
  </div>
  <div className="space-y-1">
    <Label>Width Tolerance (mm)</Label>
    <Input type="number" step="0.1" value={form.width_tolerance_mm} onChange={set('width_tolerance_mm')} />
  </div>
  <div className="space-y-1">
    <Label>Length Tolerance (mm)</Label>
    <Input type="number" step="0.1" value={form.length_tolerance_mm} onChange={set('length_tolerance_mm')} />
  </div>
  <div className="space-y-1">
    <Label>GSM Min</Label>
    <Input type="number" placeholder="60" value={form.gsm_min} onChange={set('gsm_min')} />
  </div>
  <div className="space-y-1">
    <Label>GSM Max</Label>
    <Input type="number" placeholder="300" value={form.gsm_max} onChange={set('gsm_max')} />
  </div>
</div>
```

Also add an inline `EditTonerModal` component at the top of `CostConfigPage.tsx` (before the page component) that allows editing an existing toner's price and yield from a pencil icon in the toner table. The toner table in `CostConfigPage` currently doesn't exist (toners live on `PrinterDetailPage`). We leave the per-printer toner table on `PrinterDetailPage` and add a pencil icon there instead — see Task 16.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/settings/CostConfigPage.tsx
git commit -m "feat: paper form with dimensions, tolerances, GSM range fields"
```

---

## Task 16: Frontend — toner edit modal on PrinterDetailPage + empty-state callouts

**Files:**
- Modify: `frontend/src/pages/printers/PrinterDetailPage.tsx`

- [ ] **Step 1: Add edit toner state and modal to `TonerManagement` component**

In `TonerManagement`, add these state variables:

```tsx
const [editToner, setEditToner] = useState<any | null>(null);
const [editForm, setEditForm] = useState({ price_per_unit: '', rated_yield_pages: '', currency: 'INR' });
```

Add update mutation:

```tsx
const updateToner = useMutation({
  mutationFn: () => api.put(`/printers/${printerId}/toners/${editToner.id}`, {
    toner_color: editToner.toner_color,
    toner_type: editToner.toner_type,
    price_per_unit: parseFloat(editForm.price_per_unit),
    rated_yield_pages: parseInt(editForm.rated_yield_pages),
    currency: editForm.currency,
  }),
  onSuccess: () => {
    qc.invalidateQueries({ queryKey: ['toners', printerId] });
    setEditToner(null);
  },
});
```

Add pencil button in toner table row (alongside existing Trash2):

```tsx
<button
  onClick={() => {
    setEditToner(t);
    setEditForm({ price_per_unit: String(t.price_per_unit), rated_yield_pages: String(t.rated_yield_pages), currency: t.currency });
  }}
  className="text-muted-foreground hover:text-primary p-1"
>
  <Edit className="h-3.5 w-3.5" />
</button>
```

Add edit modal JSX below the toner table:

```tsx
{editToner && (
  <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
    <div className="w-full max-w-sm rounded-xl border bg-card p-6 shadow-xl mx-4 space-y-4">
      <h3 className="font-semibold">Edit {editToner.toner_color} Toner</h3>
      <div className="space-y-3">
        <div className="space-y-1">
          <Label>Price per Unit</Label>
          <Input type="number" min="0" step="0.01" value={editForm.price_per_unit} onChange={e => setEditForm(p => ({ ...p, price_per_unit: e.target.value }))} />
        </div>
        <div className="space-y-1">
          <Label>Rated Yield (pages)</Label>
          <Input type="number" min="1" value={editForm.rated_yield_pages} onChange={e => setEditForm(p => ({ ...p, rated_yield_pages: e.target.value }))} />
        </div>
        <div className="space-y-1">
          <Label>Currency</Label>
          <select className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm" value={editForm.currency} onChange={e => setEditForm(p => ({ ...p, currency: e.target.value }))}>
            <option value="INR">INR</option>
            <option value="USD">USD</option>
            <option value="EUR">EUR</option>
            <option value="GBP">GBP</option>
          </select>
        </div>
      </div>
      {updateToner.isError && <p className="text-sm text-destructive">{(updateToner.error as any)?.response?.data?.detail || 'Update failed'}</p>}
      <div className="flex gap-3">
        <Button variant="outline" size="sm" onClick={() => setEditToner(null)}>Cancel</Button>
        <Button size="sm" onClick={() => updateToner.mutate()} disabled={updateToner.isPending} isLoading={updateToner.isPending}>Save</Button>
      </div>
    </div>
  </div>
)}
```

Also add an "Edit Printer" link in the `PrinterDetailPage` header:

```tsx
// In the header section, after the printer name:
<button
  onClick={() => navigate(`/printers/${id}/edit`)}
  className="text-xs text-primary hover:underline ml-2"
>
  Edit →
</button>
```

And add empty-state callouts: after the `TonerManagement` component, if `toners.length === 0`, show a warning callout about uploads being disabled:

```tsx
{toners && toners.length === 0 && (
  <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
    <strong>CSV upload is disabled.</strong> Configure at least one toner cartridge above before uploading print logs.
  </div>
)}
```

Add `Edit` to the lucide-react import at the top.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/printers/PrinterDetailPage.tsx
git commit -m "feat: toner edit modal, edit printer link, upload gate empty-state on PrinterDetailPage"
```

---

## Task 17: Frontend — toner replacement per-cartridge price fields

**Files:**
- Modify: `frontend/src/pages/settings/TonerReplacementsPage.tsx`

- [ ] **Step 1: Read the full file, then update `AddReplacementForm`**

In `AddReplacementForm`, add `cartridge_price_per_unit`, `cartridge_rated_yield_pages`, `cartridge_currency` to state:

```tsx
const [form, setForm] = useState({
  printer_id: '',
  toner_id: '',
  counter_reading_at_replacement: '',
  replaced_at: new Date().toISOString().slice(0, 16),
  cartridge_price_per_unit: '',
  cartridge_rated_yield_pages: '',
  cartridge_currency: 'INR',
  notes: '',
});
```

When `toner_id` changes, pre-fill the cartridge price fields from the selected toner:

```tsx
const handleTonerSelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
  const tonerId = e.target.value;
  const selected = toners?.find((t: any) => String(t.id) === tonerId);
  setForm(p => ({
    ...p,
    toner_id: tonerId,
    cartridge_price_per_unit: selected ? String(selected.price_per_unit) : '',
    cartridge_rated_yield_pages: selected ? String(selected.rated_yield_pages) : '',
    cartridge_currency: selected?.currency ?? 'INR',
  }));
};
```

Update the toner `<select>` to use `onChange={handleTonerSelect}` instead of `onChange={set('toner_id')}`.

Update the `create` mutation payload to include the cartridge fields:

```tsx
mutationFn: () => api.post('/toner-replacements', {
  printer_id: parseInt(form.printer_id),
  toner_id: parseInt(form.toner_id),
  counter_reading_at_replacement: parseInt(form.counter_reading_at_replacement),
  replaced_at: new Date(form.replaced_at).toISOString(),
  cartridge_price_per_unit: parseFloat(form.cartridge_price_per_unit),
  cartridge_rated_yield_pages: parseInt(form.cartridge_rated_yield_pages),
  cartridge_currency: form.cartridge_currency,
  notes: form.notes || undefined,
}),
```

Add these form fields in the JSX after the toner selector:

```tsx
<div className="space-y-1">
  <Label>Cartridge Price (pre-filled, editable) *</Label>
  <div className="flex gap-2">
    <Input
      type="number" min="0" step="0.01"
      placeholder="e.g. 5000"
      value={form.cartridge_price_per_unit}
      onChange={set('cartridge_price_per_unit')}
    />
    <select
      className="rounded-md border border-border bg-background px-3 py-2 text-sm"
      value={form.cartridge_currency}
      onChange={set('cartridge_currency')}
    >
      <option value="INR">INR</option>
      <option value="USD">USD</option>
      <option value="EUR">EUR</option>
    </select>
  </div>
</div>
<div className="space-y-1">
  <Label>Cartridge Rated Yield (pages, pre-filled, editable) *</Label>
  <Input
    type="number" min="1"
    placeholder="e.g. 10000"
    value={form.cartridge_rated_yield_pages}
    onChange={set('cartridge_rated_yield_pages')}
  />
</div>
```

Also update `_log_out` display in the replacements table to show `cartridge_price_per_unit` column.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/settings/TonerReplacementsPage.tsx
git commit -m "feat: toner replacement form pre-fills cartridge price/yield from toner defaults"
```

---

## Task 18: Smoke test checklist (manual)

- [ ] `cd backend && alembic upgrade head` — both migrations apply cleanly
- [ ] Backend running on `:8001`, frontend on `:5173`
- [ ] Log in as `admin@printsight.com / Admin1234`
- [ ] TopBar shows `PrinterSelector` with printer name
- [ ] Dashboard shows hero banner for selected printer; Day/Week/Month/Year tabs work; gradient KPI cards render
- [ ] `/printers/new` → 5-step wizard; cannot proceed Step 1 without name; Step 2 requires at least one toner
- [ ] Create printer → redirects to detail page
- [ ] `/printers/{id}/edit` → edit name, upload image, see image in `PrinterSelector` thumb
- [ ] Delete Printer → archive works; hard-delete blocked with 409 if jobs exist; purge with name match succeeds
- [ ] `/printers/{id}/mapping` → Export JSON download; Import JSON → diff modal → Apply
- [ ] `/settings/costs` → Add paper with dimensions + tolerances + GSM range
- [ ] Toner table pencil → edit price → save → updated
- [ ] `/settings/toner-replacements` → log replacement → cartridge price pre-fills from toner → editable → saved correctly (verify in DB: `cartridge_price_per_unit` set)
- [ ] Upload CSV with no toners → disabled warning shown
