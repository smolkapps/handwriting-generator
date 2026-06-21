"""Text layout: word-wrapping and line breaking against font metrics.

This module is pure (no drawing). It turns a block of text into a list of
lines, each fitting within an optional pixel width, measured with the actual
font so wrapping matches what will be rendered.
"""

from __future__ import annotations

from typing import List, Optional

from PIL import ImageFont


def measure_text_width(font: ImageFont.FreeTypeFont, text: str) -> float:
    """Width in pixels of ``text`` rendered with ``font`` (advance width).

    Uses the font's horizontal advance via ``getlength`` which is the correct
    measure for laying glyphs out left-to-right (it includes side bearings the
    way text advances, unlike a tight pixel bbox).
    """
    if not text:
        return 0.0
    return float(font.getlength(text))


def wrap_text(
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: Optional[float],
) -> List[str]:
    """Break ``text`` into lines that each fit within ``max_width`` pixels.

    Behavior:
      * Explicit newlines in ``text`` are always honored as hard breaks.
      * Within each paragraph, words are greedily packed onto a line until the
        next word would exceed ``max_width``.
      * ``max_width is None`` (or <= 0) disables wrapping: each input line
        becomes exactly one output line.
      * A single word longer than ``max_width`` is hard-split character by
        character so it never overflows.
      * Blank input lines are preserved (as empty strings) so paragraph spacing
        survives.

    Args:
        text: The source text. May contain ``\n``.
        font: The font used to measure widths.
        max_width: Target wrap width in pixels, or ``None`` to disable.

    Returns:
        A list of line strings (without trailing newlines).
    """
    hard_lines = text.split("\n")

    if max_width is None or max_width <= 0:
        return hard_lines

    out: List[str] = []
    for paragraph in hard_lines:
        if paragraph == "":
            # Preserve intentional blank lines / paragraph breaks.
            out.append("")
            continue

        words = paragraph.split(" ")
        current = ""

        for word in words:
            # Words split on a single space; collapse runs of spaces gracefully
            # by skipping the empties they produce.
            if word == "":
                continue

            candidate = word if current == "" else f"{current} {word}"
            if measure_text_width(font, candidate) <= max_width:
                current = candidate
                continue

            # `candidate` overflows. Flush what we have (if any) first.
            if current:
                out.append(current)
                current = ""

            # Now place `word` alone. If it still overflows on its own, it must
            # be hard-split so nothing ever exceeds max_width.
            if measure_text_width(font, word) <= max_width:
                current = word
            else:
                out.extend(_hard_split_word(word, font, max_width))
                # _hard_split_word returns complete lines except possibly a
                # trailing remainder we keep building on.
                if out and measure_text_width(font, out[-1]) <= max_width:
                    current = out.pop()
                else:
                    current = ""

        out.append(current)

    return out


def _hard_split_word(
    word: str,
    font: ImageFont.FreeTypeFont,
    max_width: float,
) -> List[str]:
    """Split a single over-wide ``word`` into chunks each within ``max_width``.

    Greedy per-character accumulation. Guarantees progress even if a single
    character is wider than ``max_width`` (that character becomes its own line).
    """
    pieces: List[str] = []
    chunk = ""
    for ch in word:
        candidate = chunk + ch
        if chunk and measure_text_width(font, candidate) > max_width:
            pieces.append(chunk)
            chunk = ch
        else:
            chunk = candidate
    if chunk:
        pieces.append(chunk)
    return pieces
