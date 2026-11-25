"""Contact sheets: one image showing every candidate with its label, for choosing by eye."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


def contact_sheet(rows: list[tuple[str, list[Path]]], out: Path, thumb_w: int = 360) -> Path:
    thumbs = []
    for label, paths in rows:
        row = []
        for p in paths:
            if p.exists():
                im = Image.open(p).convert("RGB")
                im.thumbnail((thumb_w, thumb_w))
                row.append(im)
        thumbs.append((label, row))
    if not any(r for _, r in thumbs):
        return out
    cell_h = max(im.height for _, r in thumbs for im in r) + 28
    cols = max(len(r) for _, r in thumbs)
    sheet = Image.new("RGB", (cols * (thumb_w + 8) + 8, len(thumbs) * (cell_h + 8) + 8), (30, 30, 30))
    d = ImageDraw.Draw(sheet)
    for ri, (label, row) in enumerate(thumbs):
        for ci, im in enumerate(row):
            x, y = 8 + ci * (thumb_w + 8), 8 + ri * (cell_h + 8)
            sheet.paste(im, (x, y + 24))
            d.text((x + 4, y + 4), f"{label}  candidate {ci}", fill=(255, 255, 255))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=88)
    return out
