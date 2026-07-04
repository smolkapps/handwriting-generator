"""Load a captured "hand pack" and provide its glyphs to the renderer.

A hand pack is produced by :mod:`.ingest`: a directory of per-glyph coverage
images (mode ``L``) plus a ``hand.json`` manifest. This module resolves packs by
name or path, samples glyph variants, and builds ready-to-stamp RGBA tiles.
"""

from __future__ import annotations

import json
import os
import random
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

from PIL import Image

PathLike = Union[str, Path]


def hands_dir() -> Path:
    """Directory where named hand packs live (``$HANDWRITING_HOME`` overrides)."""
    base = os.environ.get("HANDWRITING_HOME")
    root = Path(base) if base else Path.home() / ".handwriting-generator"
    return root / "hands"


def resolve_pack(name_or_path: PathLike) -> Path:
    """Resolve a hand pack by direct path or by name under :func:`hands_dir`."""
    p = Path(name_or_path)
    if (p / "hand.json").is_file():
        return p
    named = hands_dir() / str(name_or_path)
    if (named / "hand.json").is_file():
        return named
    raise FileNotFoundError(
        f"hand pack {str(name_or_path)!r} not found (looked in {p} and {named}). "
        "Create one with: handwriting-generator ingest --template FILLED.png "
        "--name NAME"
    )


class HandPack:
    """A user's captured handwriting: glyph coverage tiles + metrics."""

    def __init__(self, path: PathLike) -> None:
        self.dir = Path(path)
        meta = json.loads((self.dir / "hand.json").read_text())
        self.name: str = meta.get("name", self.dir.name)
        self.cap_px: float = float(meta.get("cap_px", 96))
        self.space_advance: float = float(meta.get("space_advance", 0.5 * self.cap_px))
        self._glyphs: Dict[str, List[dict]] = meta.get("glyphs", {})
        self._cache: Dict[str, Image.Image] = {}

    @classmethod
    def load(cls, name_or_path: PathLike) -> "HandPack":
        return cls(resolve_pack(name_or_path))

    def has(self, ch: str) -> bool:
        return bool(self._glyphs.get(ch))

    @property
    def covered(self) -> Sequence[str]:
        return tuple(self._glyphs.keys())

    def _coverage(self, fname: str) -> Image.Image:
        if fname not in self._cache:
            self._cache[fname] = Image.open(self.dir / fname).convert("L")
        return self._cache[fname]

    def sample(self, ch: str, rng: random.Random) -> Optional[dict]:
        """Pick one glyph variant for ``ch`` (random when several were captured)."""
        opts = self._glyphs.get(ch)
        if not opts:
            return None
        if len(opts) == 1:
            return opts[0]
        return opts[rng.randrange(len(opts))]

    def advance(self, ch: str, rec: Optional[dict], scale: float) -> float:
        if rec is None or not ch.strip():
            return self.space_advance * scale
        return float(rec["advance"]) * scale

    def nominal_advance(self, ch: str, scale: float) -> float:
        """A stable (sample-independent) advance for ``ch`` — for canvas sizing.

        Uses the widest captured sample so laid-out text never clips.
        """
        opts = self._glyphs.get(ch)
        if not opts:
            return self.space_advance * scale
        return max(float(o["advance"]) for o in opts) * scale

    def glyph_tile(
        self, rec: dict, scale: float, color: Tuple[int, int, int]
    ) -> Tuple[Image.Image, float]:
        """Return ``(rgba_tile, baseline_y)`` — the inked glyph tinted to color.

        ``baseline_y`` is the writing baseline's y within the returned tile, and
        the tile's left edge is the glyph's left ink edge (pen origin x = 0).
        """
        cov = self._coverage(rec["file"])
        w = max(1, int(round(rec["w"] * scale)))
        h = max(1, int(round(rec["h"] * scale)))
        cov = cov.resize((w, h), resample=Image.BICUBIC)
        tile = Image.new("RGBA", (w, h), (color[0], color[1], color[2], 0))
        tile.putalpha(cov)
        return tile, float(rec["baseline_off"]) * scale
