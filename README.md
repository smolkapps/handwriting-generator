# handwriting-generator

Render text as a natural-looking **handwriting** image (PNG) from the command
line or as a Python library. It draws a handwriting-style font glyph-by-glyph
and applies subtle, seeded per-glyph randomization (baseline wander, slight
rotation, size wobble) so the result looks hand-written instead of typeset.

This is a **font-rendering** approach — **not** machine learning. It runs fully
**offline**: no network access or API keys at runtime. (A font is downloaded
once at build time and committed into the package.)

## Install

```bash
pip install .
# or, for development with tests:
pip install -e ".[test]"
```

Runtime dependency: [Pillow](https://python-pillow.org/).

## CLI

Two equivalent entry points are installed: `handwriting-generator` and the
shorter `handwrite`.

```bash
# Simple
handwriting-generator "Dear John, I hope this letter finds you well." -o note.png

# From a file (use '-' for stdin)
handwriting-generator --input letter.txt -o letter.png

# Messy notebook style, reproducible
handwrite "Meeting notes" --paper lined --jitter 1.8 --seed 42 -o notes.png

# Neat, narrow column, custom ink color
handwrite "Tidy and straight" --jitter 0 --width 600 --color "#1a1a8a" -o tidy.png
```

### Flags

| Flag | Default | Meaning |
|------|---------|---------|
| `TEXT` (positional) | — | Text to render (omit when using `--input`). |
| `--input`, `-i` | — | Read text from a file (`-` = stdin). |
| `--output`, `-o` | `handwriting.png` | Output PNG path. |
| `--font` | bundled *Shadows Into Light* | Path to a `.ttf`/`.otf` font. |
| `--size` | `48` | Font size in points. |
| `--color` | `#1a1a8a` | Ink color (`#hex`, name, or `rgb(...)`). |
| `--width` | `1000` | Word-wrap column width in px (`0` disables wrapping). |
| `--jitter` | `1.0` | Messiness. `0` = neat; higher = messier. |
| `--line-spacing` | `1.0` | Line-height multiplier. |
| `--paper` | `blank` | `blank`, `lined`, or `none` (transparent). |
| `--margin` | `40` | Padding around the text, in px. |
| `--seed` | none | RNG seed; same text+seed+settings ⇒ byte-identical PNG. |

Long text is word-wrapped to `--width`, and the image grows taller to fit all
lines.

## Library

```python
from handwriting_generator import HandwritingRenderer, RenderConfig, render_text

# One-shot helper
render_text("Hello, world!", "hello.png", paper="lined", jitter=1.2, seed=7)

# Or keep a configured renderer
cfg = RenderConfig(size=56, color="#222222", width=800, jitter=0.8, seed=1)
renderer = HandwritingRenderer(cfg)
img = renderer.render("Reusable renderer")   # a PIL RGBA Image
renderer.save("Reusable renderer", "out.png")
```

## Determinism

Pass `--seed` (CLI) or `seed=` (library) to make output reproducible: the same
text, seed, and settings always produce a **byte-identical** PNG. Without a
seed, the jitter is randomized on each run.

## Licensing

- **Code:** MIT (see [`LICENSE`](LICENSE)).
- **Bundled font:** *Shadows Into Light* by Kimberly Geswein is licensed under
  the **SIL Open Font License, Version 1.1**. Its full license text ships with
  the package at
  [`handwriting_generator/fonts/OFL.txt`](handwriting_generator/fonts/OFL.txt).
  The OFL is **not** the same as the MIT license that covers the code; it
  governs the font file only. You may swap in any other font with `--font`.
