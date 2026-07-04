"""Printable capture template + shared cell geometry.

The ``template`` subcommand prints a grid the user fills in by hand: one
write-box per character (optionally several samples each), with a faint guide
glyph and a baseline to trace over. ``ingest`` later crops each box using the
SAME geometry defined here, so the two must stay in sync — hence the shared
constants live in this one module.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import List, Optional, Tuple, Union

from PIL import Image, ImageDraw, ImageFont

from .fonts import default_font_path

PathLike = Union[str, Path]

#: Characters captured by default (letters, digits, common punctuation).
DEFAULT_CHARSET = (
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,!?'\"-:;()&@#/$%"
)

# --- Cell / grid geometry (shared with ingest — do not drift) -------------
COLS = 8  #: write-boxes per row
CELL_W = 190  #: px, full cell width
CELL_H = 210  #: px, full cell height
LABEL_H = 34  #: px, top strip holding the printed char label (never cropped)
GRID_MARGIN = 60  #: px, page margin around the grid
MARK = 22  #: px, registration-mark square side
BASELINE_IN_CELL = 150  #: px from cell top to the writing baseline
CAP_PX = 96  #: px, nominal cap height above baseline (the render-scale reference)

_GUIDE_GREY = (198, 198, 198)  # faint guide glyph — thresholded out on ingest
_BASELINE_GREY = (150, 175, 210)  # faint baseline rule
_BORDER_GREY = (205, 205, 205)
_LABEL_RGB = (40, 40, 40)
_MARK_RGB = (0, 0, 0)


def grid_dims(n_cells: int) -> Tuple[int, int]:
    """Return ``(cols, rows)`` needed to hold ``n_cells`` write-boxes."""
    rows = max(1, math.ceil(n_cells / COLS))
    return COLS, rows


def page_size(n_cells: int) -> Tuple[int, int]:
    """Return the ``(width, height)`` of the template page for ``n_cells``."""
    cols, rows = grid_dims(n_cells)
    return 2 * GRID_MARGIN + cols * CELL_W, 2 * GRID_MARGIN + rows * CELL_H


def registration_marks(page_w: int, page_h: int) -> List[Tuple[int, int]]:
    """Canonical centers of the four corner registration marks (TL,TR,BL,BR)."""
    off = GRID_MARGIN // 2
    return [
        (off, off),
        (page_w - off, off),
        (off, page_h - off),
        (page_w - off, page_h - off),
    ]


def cell_origin(index: int) -> Tuple[int, int]:
    """Top-left ``(x, y)`` of the cell at layout position ``index``."""
    col = index % COLS
    row = index // COLS
    return GRID_MARGIN + col * CELL_W, GRID_MARGIN + row * CELL_H


def writebox(index: int) -> Tuple[int, int, int, int]:
    """Crop rectangle ``(left, top, right, bottom)`` of a cell's writing area.

    This is everything *below* the label strip — so the printed character label
    is never captured as ink.
    """
    ox, oy = cell_origin(index)
    return ox + 2, oy + LABEL_H + 1, ox + CELL_W - 2, oy + CELL_H - 2


def writebox_baseline(index: int) -> float:
    """Y of the writing baseline relative to this cell's write-box top."""
    return float(BASELINE_IN_CELL - LABEL_H - 1)


def cell_slots(charset: str, samples: int) -> List[str]:
    """Flat list mapping each layout slot to its character (``samples`` each)."""
    slots: List[str] = []
    for ch in charset:
        slots.extend([ch] * samples)
    return slots


def build_template(
    charset: str = DEFAULT_CHARSET,
    samples: int = 1,
    guide_font_path: Optional[PathLike] = None,
) -> Image.Image:
    """Render the blank capture template as an ``RGB`` image.

    Args:
        charset: Characters to include, one write-box each (times ``samples``).
        samples: Number of write-boxes per character (for natural variation).
        guide_font_path: Font for the faint guide glyphs; bundled default if None.
    """
    if samples < 1:
        raise ValueError("samples must be >= 1")
    if not charset:
        raise ValueError("charset must not be empty")

    slots = cell_slots(charset, samples)
    page_w, page_h = page_size(len(slots))

    img = Image.new("RGB", (page_w, page_h), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    for mx, my in registration_marks(page_w, page_h):
        draw.rectangle(
            [mx - MARK // 2, my - MARK // 2, mx + MARK // 2, my + MARK // 2],
            fill=_MARK_RGB,
        )

    font_path = Path(guide_font_path) if guide_font_path else default_font_path()
    guide_font = ImageFont.truetype(str(font_path), size=CAP_PX)
    label_font = ImageFont.truetype(str(font_path), size=22)

    for i, ch in enumerate(slots):
        ox, oy = cell_origin(i)
        draw.rectangle([ox, oy, ox + CELL_W - 1, oy + CELL_H - 1], outline=_BORDER_GREY)
        draw.line(
            [(ox, oy + LABEL_H), (ox + CELL_W - 1, oy + LABEL_H)], fill=_BORDER_GREY
        )
        label = ch if ch.strip() else "(space)"
        draw.text((ox + 8, oy + 6), label, font=label_font, fill=_LABEL_RGB)

        by = oy + BASELINE_IN_CELL
        draw.line([(ox + 6, by), (ox + CELL_W - 6, by)], fill=_BASELINE_GREY)

        if ch.strip():
            try:
                gl = guide_font.getlength(ch)
                asc, _desc = guide_font.getmetrics()
                gx = ox + (CELL_W - gl) / 2
                draw.text((gx, by - asc), ch, font=guide_font, fill=_GUIDE_GREY)
            except Exception:  # pragma: no cover - guide is best-effort
                pass

    return img


def save_template(
    path: PathLike,
    charset: str = DEFAULT_CHARSET,
    samples: int = 1,
    guide_font_path: Optional[PathLike] = None,
) -> Tuple[int, int]:
    """Build the template and write it to ``path`` (PNG). Returns its size."""
    img = build_template(charset, samples, guide_font_path)
    out = Path(path)
    if out.parent and not out.parent.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, format="PNG")
    return img.size
