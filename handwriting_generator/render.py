"""Core rendering: text -> handwritten-looking PNG.

Pipeline:
  1. Load the handwriting font (bundled default unless overridden).
  2. Word-wrap the text to the requested pixel width (:mod:`.layout`).
  3. Compute the canvas size from line count, line height, and margins.
  4. Draw each glyph onto a transparent ink layer, perturbed per glyph by a
     seeded RNG (:mod:`.jitter`).
  5. Composite the ink over the chosen paper background (:mod:`.paper`).
  6. Return / save a PNG.

Everything is deterministic given ``RenderConfig.seed``: the same text, seed and
settings produce byte-identical PNGs.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Union

from PIL import Image, ImageColor, ImageDraw, ImageFont

from . import jitter as _jitter
from . import paper as _paper
from .fonts import default_font_path
from .hand import HandPack
from .layout import measure_text_width, wrap_text

PathLike = Union[str, Path]


@dataclass
class RenderConfig:
    """Settings controlling a render.

    Attributes:
        font_path: Path to a ``.ttf``/``.otf`` font, or ``None`` for the bundled
            default handwriting font.
        size: Font size in points (pixels at 72 dpi).
        color: Ink color as anything :func:`PIL.ImageColor.getrgb` accepts
            (e.g. ``"#1a1a8a"``, ``"black"``, ``"rgb(20,20,138)"``).
        width: Target wrap width in pixels for word-wrapping, or ``None`` to
            disable wrapping (only explicit newlines break lines).
        jitter: Non-negative messiness strength. ``0`` = neat; larger = messier.
        line_spacing: Multiplier on the natural line height (1.0 = font default).
        paper: Background style: ``"blank"``, ``"lined"`` or ``"none"``
            (transparent).
        margin: Padding in pixels around the text on all sides.
        seed: RNG seed for reproducible jitter. ``None`` = nondeterministic.
    """

    font_path: Optional[PathLike] = None
    size: int = 48
    color: str = "#1a1a8a"
    width: Optional[int] = 1000
    jitter: float = 1.0
    line_spacing: float = 1.0
    paper: str = "blank"
    margin: int = 40
    seed: Optional[int] = None
    hand_path: Optional[PathLike] = None

    def __post_init__(self) -> None:
        if self.size <= 0:
            raise ValueError(f"size must be positive, got {self.size}")
        if self.jitter < 0:
            raise ValueError(f"jitter must be >= 0, got {self.jitter}")
        if self.line_spacing <= 0:
            raise ValueError(f"line_spacing must be positive, got {self.line_spacing}")
        if self.margin < 0:
            raise ValueError(f"margin must be >= 0, got {self.margin}")


class HandwritingRenderer:
    """Renders text into a handwriting-style :class:`PIL.Image.Image`."""

    # Extra padding (multiples of font size) reserved around each rotated glyph
    # tile so rotation/scale never clips the glyph.
    _GLYPH_PAD_FACTOR = 0.6

    def __init__(self, config: Optional[RenderConfig] = None) -> None:
        self.config = config or RenderConfig()
        self._font = self._load_font(self.config.font_path, self.config.size)
        self._ink = ImageColor.getrgb(self.config.color)
        if self.config.hand_path is not None:
            self._hand: Optional[HandPack] = HandPack.load(str(self.config.hand_path))
            self._hand_scale = self.config.size / self._hand.cap_px
        else:
            self._hand = None
            self._hand_scale = 1.0

    # -- public API ---------------------------------------------------------

    def render(self, text: str) -> Image.Image:
        """Render ``text`` and return an ``RGBA`` :class:`PIL.Image.Image`."""
        cfg = self.config
        font = self._font

        ascent, descent = font.getmetrics()
        natural_line_height = ascent + descent
        line_height = natural_line_height * cfg.line_spacing

        # Inner width available for text (canvas width minus both margins) when a
        # wrap width is requested. We wrap to cfg.width directly (it is the text
        # column width); the canvas then adds margins on top.
        wrap_width = float(cfg.width) if cfg.width else None
        lines = wrap_text(text, font, wrap_width)
        if not lines:
            lines = [""]

        canvas_w, canvas_h, text_w = self._canvas_size(
            lines, font, line_height, ascent, descent
        )

        # Ink layer (transparent); we draw dark glyphs onto it, then composite.
        ink_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

        rng = random.Random(cfg.seed)
        first_baseline = cfg.margin + ascent

        baseline = float(first_baseline)
        for line in lines:
            line_drift = _jitter.line_baseline_offset(rng, cfg.jitter)
            self._draw_line(
                ink_layer,
                line,
                font,
                x0=float(cfg.margin),
                baseline=baseline + line_drift,
                rng=rng,
            )
            baseline += line_height

        background = _paper.make_paper(
            (canvas_w, canvas_h),
            cfg.paper,
            line_height=line_height,
            margin=cfg.margin,
            first_baseline=first_baseline,
        )

        out = Image.alpha_composite(background, ink_layer)
        return out

    def save(self, text: str, path: PathLike) -> Tuple[int, int]:
        """Render ``text`` and write a PNG to ``path``.

        Returns:
            The ``(width, height)`` of the written image.
        """
        img = self.render(text)
        out_path = Path(path)
        if out_path.parent and not out_path.parent.exists():
            out_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path, format="PNG")
        return img.size

    # -- internals ----------------------------------------------------------

    @staticmethod
    def _load_font(font_path: Optional[PathLike], size: int) -> ImageFont.FreeTypeFont:
        path = Path(font_path) if font_path is not None else default_font_path()
        if not path.is_file():
            raise FileNotFoundError(f"Font file not found: {path!s}")
        try:
            return ImageFont.truetype(str(path), size=size)
        except OSError as exc:  # pragma: no cover - exercised via bad-font path
            raise OSError(f"Could not load font {path!s}: {exc}") from exc

    def _canvas_size(
        self,
        lines: List[str],
        font: ImageFont.FreeTypeFont,
        line_height: float,
        ascent: int,
        descent: int,
    ) -> Tuple[int, int, float]:
        """Compute ``(width, height, max_text_width)`` for the canvas."""
        cfg = self.config
        max_text_w = 0.0
        for line in lines:
            max_text_w = max(max_text_w, self._line_advance(line, font))

        # Allow jitter room so rotated/offset glyphs at line ends don't clip.
        jitter_pad = cfg.jitter * cfg.size * 0.25

        if cfg.width:
            # Honor the requested text column width so wrapping & canvas agree.
            content_w = max(float(cfg.width), max_text_w)
        else:
            content_w = max_text_w

        width = int(round(content_w + 2 * cfg.margin + jitter_pad)) or 1

        n = len(lines)
        # Height: top margin + ascent for first line, then (n-1) line advances,
        # + descent + bottom margin, + jitter room.
        content_h = ascent + (n - 1) * line_height + descent
        height = int(round(content_h + 2 * cfg.margin + jitter_pad)) or 1

        return max(width, 1), max(height, 1), max_text_w

    def _draw_line(
        self,
        ink_layer: Image.Image,
        line: str,
        font: ImageFont.FreeTypeFont,
        x0: float,
        baseline: float,
        rng: random.Random,
    ) -> None:
        """Draw one line of glyphs onto ``ink_layer`` at the given baseline."""
        cfg = self.config
        pen_x = x0
        pad = int(cfg.size * self._GLYPH_PAD_FACTOR) + 2
        hand = self._hand

        for ch in line:
            j = _jitter.glyph_jitter(rng, cfg.jitter)

            # Prefer a captured glyph from the user's hand pack when present.
            if hand is not None and hand.has(ch):
                rec = hand.sample(ch, rng)
                self._stamp_hand(
                    ink_layer, hand, rec, pen_x=pen_x, baseline=baseline, jitter=j
                )
                pen_x += hand.advance(ch, rec, self._hand_scale) + j.dx
                continue

            # Advance width from the unperturbed glyph keeps spacing stable.
            advance = font.getlength(ch)

            if ch == " " or not ch.strip():
                # Whitespace contributes advance only; nothing to draw.
                pen_x += advance + j.dx
                continue

            self._stamp_glyph(
                ink_layer,
                ch,
                font,
                pen_x=pen_x,
                baseline=baseline,
                jitter=j,
                pad=pad,
            )
            pen_x += advance + j.dx

    def _stamp_glyph(
        self,
        ink_layer: Image.Image,
        ch: str,
        font: ImageFont.FreeTypeFont,
        pen_x: float,
        baseline: float,
        jitter: _jitter.GlyphJitter,
        pad: int,
    ) -> None:
        """Render a single character onto a padded tile, rotate/scale it, paste.

        The glyph is drawn onto a small transparent RGBA tile sized to the
        glyph's ink bbox plus padding, then rotated (and optionally scaled),
        then alpha-composited onto ``ink_layer`` at the correct baseline-aligned
        position.
        """
        cfg = self.config

        # Tight ink bbox of the glyph relative to an origin we control. Draw the
        # glyph at (pad, pad) on a tile and find where its ink lands.
        tile_w = int(font.getlength(ch)) + 2 * pad
        ascent, descent = font.getmetrics()
        tile_h = ascent + descent + 2 * pad
        if tile_w <= 0 or tile_h <= 0:
            return

        tile = Image.new("RGBA", (tile_w, tile_h), (0, 0, 0, 0))
        tdraw = ImageDraw.Draw(tile)
        # Draw so the glyph baseline sits at y = pad + ascent inside the tile.
        draw_origin = (pad, pad)
        tdraw.text(draw_origin, ch, font=font, fill=self._ink + (255,))

        # Optional size wobble.
        if abs(jitter.scale - 1.0) > 1e-6:
            new_w = max(1, int(round(tile_w * jitter.scale)))
            new_h = max(1, int(round(tile_h * jitter.scale)))
            tile = tile.resize((new_w, new_h), resample=Image.BICUBIC)
            scale = jitter.scale
        else:
            scale = 1.0

        # Optional rotation about the tile center.
        if abs(jitter.rotation) > 1e-6:
            tile = tile.rotate(
                jitter.rotation,
                resample=Image.BICUBIC,
                expand=True,
            )

        # Position: we want the glyph's baseline origin (draw_origin, scaled) to
        # land at (pen_x, baseline + dy). After rotate(expand=True)/resize the
        # tile grew symmetrically about its center, so compute the center shift.
        scaled_origin_x = draw_origin[0] * scale
        scaled_origin_y = (draw_origin[1] + ascent) * scale  # baseline inside tile

        # Center of the (possibly grown) tile.
        cx = tile.width / 2.0
        cy = tile.height / 2.0

        # Where the origin point sits relative to tile center, before rotation,
        # in the scaled (pre-rotation) tile. Because rotation is about center and
        # expand keeps the center fixed, the center maps to center; the origin
        # moves, but for our purposes pasting by aligning the *center* to the
        # intended center keeps glyphs visually correct and is stable/det.
        #
        # Intended center in canvas coords = intended origin + (center - origin).
        pre_w = max(1, int(round(tile_w * scale)))
        pre_h = max(1, int(round(tile_h * scale)))
        pre_cx = pre_w / 2.0
        pre_cy = pre_h / 2.0

        intended_origin_x = pen_x
        intended_origin_y = baseline + jitter.dy

        intended_center_x = intended_origin_x + (pre_cx - scaled_origin_x)
        intended_center_y = intended_origin_y + (pre_cy - scaled_origin_y)

        paste_x = int(round(intended_center_x - cx))
        paste_y = int(round(intended_center_y - cy))

        ink_layer.alpha_composite(tile, dest=(max(paste_x, 0), max(paste_y, 0)))

    def _stamp_hand(
        self,
        ink_layer: Image.Image,
        hand: HandPack,
        rec: Optional[dict],
        pen_x: float,
        baseline: float,
        jitter: _jitter.GlyphJitter,
    ) -> None:
        """Stamp one captured glyph tile at the baseline, perturbed by jitter.

        Mirrors :meth:`_stamp_glyph`'s center-based placement, but the tile is a
        pre-inked coverage image from the hand pack rather than a font draw. The
        tile's pen origin is ``(0, baseline_y)`` (left ink edge, writing baseline).
        """
        if rec is None:
            return
        tile, baseline_y = hand.glyph_tile(rec, self._hand_scale, self._ink)
        origin_x = 0.0

        tw, th = tile.width, tile.height
        if abs(jitter.scale - 1.0) > 1e-6:
            tile = tile.resize(
                (
                    max(1, int(round(tw * jitter.scale))),
                    max(1, int(round(th * jitter.scale))),
                ),
                resample=Image.BICUBIC,
            )
            scale = jitter.scale
        else:
            scale = 1.0

        pre_w = max(1, int(round(tw * scale)))
        pre_h = max(1, int(round(th * scale)))

        if abs(jitter.rotation) > 1e-6:
            tile = tile.rotate(jitter.rotation, resample=Image.BICUBIC, expand=True)

        scaled_origin_x = origin_x * scale
        scaled_origin_y = baseline_y * scale
        pre_cx = pre_w / 2.0
        pre_cy = pre_h / 2.0
        cx = tile.width / 2.0
        cy = tile.height / 2.0

        intended_origin_x = pen_x
        intended_origin_y = baseline + jitter.dy
        intended_center_x = intended_origin_x + (pre_cx - scaled_origin_x)
        intended_center_y = intended_origin_y + (pre_cy - scaled_origin_y)

        paste_x = int(round(intended_center_x - cx))
        paste_y = int(round(intended_center_y - cy))
        ink_layer.alpha_composite(tile, dest=(max(paste_x, 0), max(paste_y, 0)))

    def _line_advance(self, line: str, font: ImageFont.FreeTypeFont) -> float:
        """Total advance width of ``line`` under the active glyph source.

        Falls back to the font's whole-string measure when no hand pack is
        active, keeping font-only output byte-identical to before.
        """
        if self._hand is None:
            return measure_text_width(font, line)
        total = 0.0
        for ch in line:
            if self._hand.has(ch):
                total += self._hand.nominal_advance(ch, self._hand_scale)
            else:
                total += font.getlength(ch)
        return total


def render_text(text: str, output_path: PathLike, **kwargs) -> Tuple[int, int]:
    """Convenience one-shot: render ``text`` to ``output_path`` as PNG.

    ``kwargs`` are forwarded to :class:`RenderConfig`. Returns the image
    ``(width, height)``.
    """
    config = RenderConfig(**kwargs)
    return HandwritingRenderer(config).save(text, output_path)
