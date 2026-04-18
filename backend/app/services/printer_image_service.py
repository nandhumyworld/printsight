"""Save and delete printer images on disk."""
from __future__ import annotations

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
