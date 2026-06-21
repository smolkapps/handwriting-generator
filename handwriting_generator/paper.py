"""Paper backgrounds drawn behind the handwriting.

Three styles:
  * ``none``  — fully transparent background (RGBA, alpha 0). Good for
    compositing the ink onto something else.
  * ``blank`` — an opaque off-white sheet, no rules.
  * ``lined`` — an opaque off-white sheet with faint horizontal rule lines
    spaced to the text's line height, plus a margin rule.
"""

from __future__ import annotations

from typing import Tuple

from PIL import Image, ImageDraw

PaperStyle = str  # one of: "none", "blank", "lined"
VALID_PAPER_STYLES = ("none", "blank", "lined")

# Off-white paper and faint blue rule, chosen to read as notebook paper.
_PAPER_RGB = (253, 251, 245)
_RULE_RGB = (170, 196, 230)
_MARGIN_RULE_RGB = (224, 170, 170)


def make_paper(
    size: Tuple[int, int],
    style: PaperStyle,
    line_height: float,
    margin: int,
    first_baseline: float,
) -> Image.Image:
    """Create the background image of ``size`` in the requested ``style``.

    Args:
        size: ``(width, height)`` in pixels.
        style: One of :data:`VALID_PAPER_STYLES`.
        line_height: Vertical distance between text lines (for spacing rules).
        margin: Left/top margin in pixels (for the margin rule placement).
        first_baseline: Y of the first text baseline, so rules sit under text.

    Returns:
        An ``RGBA`` image. ``none`` is transparent; the others are opaque.

    Raises:
        ValueError: if ``style`` is not recognized.
    """
    if style not in VALID_PAPER_STYLES:
        raise ValueError(
            f"Unknown paper style {style!r}; expected one of {VALID_PAPER_STYLES}."
        )

    width, height = size

    if style == "none":
        return Image.new("RGBA", size, (0, 0, 0, 0))

    img = Image.new("RGBA", size, _PAPER_RGB + (255,))

    if style == "lined":
        draw = ImageDraw.Draw(img)
        # Horizontal rules: place one just below each baseline, marching down by
        # line_height, covering the whole sheet.
        if line_height >= 1:
            y = first_baseline + max(2.0, line_height * 0.12)
            while y < height:
                draw.line([(0, y), (width, y)], fill=_RULE_RGB + (255,), width=1)
                y += line_height
        # Vertical margin rule a little inside the left margin.
        margin_x = max(4, int(margin * 0.6))
        draw.line(
            [(margin_x, 0), (margin_x, height)],
            fill=_MARGIN_RULE_RGB + (255,),
            width=1,
        )

    return img
