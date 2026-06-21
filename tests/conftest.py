"""Shared test helpers."""

from __future__ import annotations

from PIL import Image


def count_ink_pixels(img: Image.Image, threshold: int = 200) -> int:
    """Count 'dark/ink' pixels in an image.

    A pixel counts as ink if it is reasonably opaque AND noticeably darker than
    white in at least one RGB channel. This works for both opaque paper
    backgrounds (dark ink on light paper) and transparent backgrounds (any
    visible ink shows up via alpha).

    Args:
        img: Any PIL image; converted to RGBA internally.
        threshold: A channel value below this (0-255) is considered "dark".

    Returns:
        Number of ink pixels.
    """
    rgba = img.convert("RGBA")
    raw = rgba.tobytes()  # tightly packed RGBA, 4 bytes/pixel
    count = 0
    for i in range(0, len(raw), 4):
        r, g, b, a = raw[i], raw[i + 1], raw[i + 2], raw[i + 3]
        if a < 16:
            continue  # effectively transparent
        if r < threshold or g < threshold or b < threshold:
            count += 1
    return count
