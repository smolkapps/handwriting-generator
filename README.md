# handwriting-generator

Render text as a natural-looking **handwriting** image (PNG) from the command
line or as a Python library. It draws a handwriting-style font glyph-by-glyph
and applies subtle, seeded per-glyph randomization (baseline wander, slight
rotation, size wobble) so the result looks hand-written instead of typeset.

Two ways to get handwriting:

- **A handwriting-style font** (the default) — zero setup, looks hand-written.
- **Your _own_ handwriting** — fill in a printable template once, and the tool
  renders text from your real, scanned pen strokes (see
  [Your own handwriting](#your-own-handwriting)).

Both use **font/image compositing** — **not** machine learning — and run fully
**offline** (no network or API keys at runtime).

## Install

```bash
pip install .
# or, for development with tests:
pip install -e ".[test]"
```

Runtime dependencies: [Pillow](https://python-pillow.org/) and NumPy.

## CLI

Two equivalent entry points are installed: `handwriting-generator` and the
shorter `handwrite`.

```bash
# Simple
handwriting-generator "Dear John, I hope this letter finds you well." -o note.png

# From a file (use '-' for stdin)
handwriting-generator --input letter.txt -o letter.png

# Multiple lines (the shell's $'...' turns \n into real newlines)
handwrite $'Dear Sam,\nThanks for the book!\n\n— Alex' --paper lined -o card.png

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
| `--hand` | — | Render in **your** handwriting: a pack made with `ingest` (by name or dir). |
| `--size` | `48` | Font size in points. |
| `--color` | `#1a1a8a` | Ink color (`#hex`, name, or `rgb(...)`). |
| `--width` | `1000` | Word-wrap column width in px (`0` disables wrapping). |
| `--jitter` | `1.0` | Messiness. `0` = neat; higher = messier. |
| `--line-spacing` | `1.0` | Line-height multiplier. |
| `--paper` | `blank` | `blank`, `lined`, or `none` (transparent). |
| `--margin` | `40` | Padding around the text, in px. |
| `--seed` | none | RNG seed; same text+seed+settings ⇒ byte-identical PNG. |

Long text is word-wrapped to `--width`, and the image grows taller to fit all
lines. The default ink color is a deep blue (`#1a1a8a`) by design; pass
`--color black` for black.

## Your own handwriting

Capture your real handwriting once, then render anything in it. No ML, no
tablet — just a printed page and a scan.

**1. Print a template**

```bash
handwriting-generator template -o my-template.png
```

A grid with one box per character (letters, digits, punctuation), each with a
faint guide to trace and a baseline. Print it and fill every box with a dark
pen — trace the guides or write freely. For natural variation, generate a few
boxes per character with `--samples 3` and write each slightly differently.

**2. Scan it and build your "hand"**

Scan or photograph the filled sheet (flat and well-lit — the four corner marks
let the tool correct a slightly skewed phone photo), then:

```bash
handwriting-generator ingest --template my-template-scan.png --name me
```

Each box is cropped into a glyph and saved as a *hand pack* under
`~/.handwriting-generator/hands/me/` (override with `--out DIR` or the
`HANDWRITING_HOME` env var). Repeat `--template` to combine several pages.

**3. Write in your own hand**

```bash
handwriting-generator "This is my actual handwriting." --hand me -o mine.png
```

Characters you didn't capture fall back to the `--font` glyph, and `--jitter`,
`--color`, `--paper`, `--seed`, etc. all still apply.

> **Note:** this reproduces your **letterforms** faithfully — print-style,
> disconnected letters. It does not yet join letters into flowing cursive
> (contextual ligatures are a possible future enhancement). Write tiny marks
> like `.` and `,` clearly so they register.

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
