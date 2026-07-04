"""handwriting_generator — render text as natural-looking handwriting PNGs.

A font-rendering approach (NOT machine learning): a handwriting-style font is
drawn glyph-by-glyph with subtle, seeded per-glyph randomization (baseline
offset, rotation, size wobble) so the output looks hand-written rather than
typeset. No network or API access is required at runtime.
"""

from .render import HandwritingRenderer, RenderConfig, render_text
from .fonts import default_font_path

__all__ = [
    "HandwritingRenderer",
    "RenderConfig",
    "render_text",
    "default_font_path",
    "__version__",
]

__version__ = "0.2.0"
