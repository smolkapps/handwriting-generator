"""Turn filled-in capture templates into a reusable "hand pack".

A hand pack is a directory of per-glyph coverage images (mode ``L``: 0 = no ink,
255 = full ink) plus a ``hand.json`` manifest. :mod:`.hand` loads it and
:mod:`.render` stamps the glyphs, so the JSON contract below must match
``hand.HandPack``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from PIL import Image

from . import template as T

PathLike = Union[str, Path]

INK_THRESHOLD = 128  # grayscale <= this counts as pen ink (guides print lighter)
_ALPHA_DARK = 55.0  # gray at/below -> fully opaque ink
_ALPHA_LIGHT = 165.0  # gray at/above -> transparent (drops faint guide/baseline)
MIN_INK_PIXELS = 14  # a write-box with fewer ink pixels is treated as empty
SIDE_BEARING = 0.11  # per-side advance padding as a fraction of CAP_PX


def _to_gray(img: Image.Image) -> np.ndarray:
    return np.asarray(img.convert("L"), dtype=np.uint8)


def _find_marks(gray: np.ndarray) -> Optional[List[Tuple[float, float]]]:
    """Centers of the 4 corner registration marks (TL, TR, BL, BR), or None.

    Looks in each corner third for a solid-dark blob and returns its centroid.
    """
    h, w = gray.shape
    qh, qw = h // 3, w // 3
    regions = [
        (0, 0, qh, qw),
        (0, w - qw, qh, w),
        (h - qh, 0, h, qw),
        (h - qh, w - qw, h, w),
    ]
    centers: List[Tuple[float, float]] = []
    need = max(9, (T.MARK * T.MARK) // 4)
    for y0, x0, y1, x1 in regions:
        sub = gray[y0:y1, x0:x1]
        ys, xs = np.nonzero(sub <= 80)
        if len(xs) < need:
            return None
        centers.append((x0 + float(xs.mean()), y0 + float(ys.mean())))
    return centers


def _perspective_coeffs(
    out_pts: Sequence[Tuple[float, float]], src_pts: Sequence[Tuple[float, float]]
) -> List[float]:
    """8 coeffs mapping OUTPUT (x,y) -> SOURCE for ``Image.PERSPECTIVE``."""
    a = []
    b = []
    for (ox, oy), (sx, sy) in zip(out_pts, src_pts):
        a.append([ox, oy, 1, 0, 0, 0, -sx * ox, -sx * oy])
        b.append(sx)
        a.append([0, 0, 0, ox, oy, 1, -sy * ox, -sy * oy])
        b.append(sy)
    res = np.linalg.solve(np.asarray(a, dtype=float), np.asarray(b, dtype=float))
    return res.tolist()


def _to_canonical(img: Image.Image, page: Tuple[int, int]) -> np.ndarray:
    """Warp/scale ``img`` to canonical template geometry; return grayscale."""
    page_w, page_h = page
    gray_full = _to_gray(img)
    marks = _find_marks(gray_full)
    if marks is not None:
        try:
            dst = T.registration_marks(page_w, page_h)  # canonical (output) pts
            coeffs = _perspective_coeffs(dst, marks)  # output -> source
            warped = img.convert("RGB").transform(
                (page_w, page_h),
                Image.PERSPECTIVE,
                coeffs,
                resample=Image.BICUBIC,
                fillcolor=(255, 255, 255),
            )
            return _to_gray(warped)
        except Exception:  # pragma: no cover - fall back to a plain resize
            pass
    return _to_gray(img.convert("RGB").resize(page, resample=Image.BICUBIC))


def _extract_glyph(
    gray: np.ndarray, index: int
) -> Optional[Tuple[np.ndarray, float, float]]:
    """Extract ``(coverage, baseline_off, advance)`` from write-box ``index``.

    ``coverage`` is a tight ``uint8`` ink-alpha crop; ``baseline_off`` is the
    baseline's y within that crop; ``advance`` is the pen advance in px.
    """
    l, t, r, b = T.writebox(index)
    cell = gray[t:b, l:r].astype(np.float32)
    if cell.size == 0:
        return None
    ink = cell <= INK_THRESHOLD
    if int(ink.sum()) < MIN_INK_PIXELS:
        return None

    ys, xs = np.nonzero(ink)
    top, bot = int(ys.min()), int(ys.max())
    left, right = int(xs.min()), int(xs.max())

    sub = cell[top : bot + 1, left : right + 1]
    alpha = np.clip(
        (_ALPHA_LIGHT - sub) / (_ALPHA_LIGHT - _ALPHA_DARK) * 255.0, 0, 255
    ).astype(np.uint8)

    baseline_off = T.writebox_baseline(index) - top
    advance = (right - left + 1) + 2 * SIDE_BEARING * T.CAP_PX
    return alpha, float(baseline_off), float(advance)


def ingest(
    template_paths: Sequence[PathLike],
    out_dir: PathLike,
    *,
    charset: str = T.DEFAULT_CHARSET,
    samples: int = 1,
    name: Optional[str] = None,
) -> dict:
    """Build a hand pack in ``out_dir`` from one or more filled templates.

    Args:
        template_paths: Filled-in template image(s) (same charset/samples used
            to generate them).
        out_dir: Destination directory for the hand pack.
        charset/samples: Must match what ``template`` was generated with.
        name: Display name stored in the manifest (defaults to the dir name).

    Returns:
        The manifest dict that was written to ``out_dir/hand.json``.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    slots = T.cell_slots(charset, samples)
    page = T.page_size(len(slots))

    glyphs: Dict[str, List[dict]] = {}
    advances: List[float] = []

    for tpath in template_paths:
        with Image.open(tpath) as im:
            gray = _to_canonical(im, page)
        for i, ch in enumerate(slots):
            if not ch.strip():
                continue
            rec = _extract_glyph(gray, i)
            if rec is None:
                continue
            cov, baseline_off, advance = rec
            samp_idx = len(glyphs.get(ch, []))
            fname = f"g{ord(ch)}_{samp_idx}.png"
            Image.fromarray(cov, mode="L").save(out / fname)
            glyphs.setdefault(ch, []).append(
                {
                    "file": fname,
                    "w": int(cov.shape[1]),
                    "h": int(cov.shape[0]),
                    "baseline_off": round(baseline_off, 2),
                    "advance": round(advance, 2),
                }
            )
            advances.append(advance)

    if advances:
        space_advance = round(float(np.median(advances)) * 0.6, 1)
    else:
        space_advance = round(0.5 * T.CAP_PX, 1)

    meta = {
        "version": 1,
        "name": name or out.name,
        "cap_px": T.CAP_PX,
        "space_advance": space_advance,
        "glyph_count": sum(len(v) for v in glyphs.values()),
        "glyphs": glyphs,
    }
    (out / "hand.json").write_text(json.dumps(meta, indent=2))
    return meta
