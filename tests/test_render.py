"""Tests for the core renderer."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from handwriting_generator import HandwritingRenderer, RenderConfig, render_text
from handwriting_generator.fonts import default_font_path, license_path

from .conftest import count_ink_pixels

SHORT = "Hi"
LONG = (
    "Dear John, I hope this letter finds you well. It has been a long while "
    "since we last spoke, and there is much I have been meaning to tell you "
    "about the garden, the dog, and the long winter nights here by the sea."
)


# --- bundled font ----------------------------------------------------------


def test_bundled_font_exists():
    p = default_font_path()
    assert p.is_file()
    assert p.suffix == ".ttf"
    assert p.stat().st_size > 1000


def test_bundled_license_exists():
    lic = license_path()
    assert lic.is_file()
    text = lic.read_text(encoding="utf-8")
    assert "SIL Open Font License" in text


# --- basic render: opens, mode/size, non-blank -----------------------------


def test_render_returns_rgba_image():
    img = HandwritingRenderer(RenderConfig(seed=1)).render(SHORT)
    assert isinstance(img, Image.Image)
    assert img.mode == "RGBA"
    w, h = img.size
    assert w > 0 and h > 0


def test_saved_png_opens_with_expected_mode_and_size(tmp_path: Path):
    out = tmp_path / "note.png"
    size = render_text(SHORT, out, seed=1)
    assert out.is_file()
    assert out.stat().st_size > 0

    with Image.open(out) as img:
        assert img.format == "PNG"
        assert img.mode == "RGBA"
        assert img.size == size  # reported size matches the file


def test_render_is_not_blank():
    img = HandwritingRenderer(RenderConfig(seed=1, paper="blank")).render(SHORT)
    ink = count_ink_pixels(img)
    assert ink > 0, "expected dark ink pixels, image appears blank"


def test_render_not_blank_on_transparent_paper():
    img = HandwritingRenderer(RenderConfig(seed=1, paper="none")).render(SHORT)
    # On a transparent background the ink still has opaque alpha.
    ink = count_ink_pixels(img)
    assert ink > 0


def test_render_not_blank_on_lined_paper():
    img = HandwritingRenderer(RenderConfig(seed=1, paper="lined")).render(SHORT)
    assert count_ink_pixels(img) > 0


# --- determinism via seed --------------------------------------------------


def test_same_seed_is_byte_identical(tmp_path: Path):
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    render_text(LONG, a, seed=12345, jitter=1.5)
    render_text(LONG, b, seed=12345, jitter=1.5)
    assert a.read_bytes() == b.read_bytes()


def test_same_seed_identical_in_memory():
    cfg = lambda: RenderConfig(seed=99, jitter=1.3)  # noqa: E731
    img1 = HandwritingRenderer(cfg()).render(LONG)
    img2 = HandwritingRenderer(cfg()).render(LONG)
    assert img1.tobytes() == img2.tobytes()


def test_different_seeds_differ():
    img1 = HandwritingRenderer(RenderConfig(seed=1, jitter=1.5)).render(LONG)
    img2 = HandwritingRenderer(RenderConfig(seed=2, jitter=1.5)).render(LONG)
    assert img1.tobytes() != img2.tobytes()


# --- wrapping grows height -------------------------------------------------


def test_long_text_is_taller_than_short_text():
    short = HandwritingRenderer(RenderConfig(seed=1, width=600)).render(SHORT)
    long = HandwritingRenderer(RenderConfig(seed=1, width=600)).render(LONG)
    assert long.size[1] > short.size[1], "wrapped long text should be taller"


def test_narrower_width_wraps_to_more_lines_and_taller():
    wide = HandwritingRenderer(RenderConfig(seed=1, width=2000)).render(LONG)
    narrow = HandwritingRenderer(RenderConfig(seed=1, width=400)).render(LONG)
    assert narrow.size[1] > wide.size[1]


def test_explicit_newlines_add_height():
    one = HandwritingRenderer(RenderConfig(seed=1, width=0)).render("line one")
    three = HandwritingRenderer(RenderConfig(seed=1, width=0)).render(
        "line one\nline two\nline three"
    )
    assert three.size[1] > one.size[1]


# --- jitter 0 vs non-zero differ -------------------------------------------


def test_jitter_zero_vs_nonzero_differ():
    neat = HandwritingRenderer(RenderConfig(seed=1, jitter=0.0)).render(LONG)
    messy = HandwritingRenderer(RenderConfig(seed=1, jitter=2.0)).render(LONG)
    assert neat.size[0] > 0 and messy.size[0] > 0
    # Compare on a common canvas so a size delta alone doesn't trivially "pass";
    # paste both onto identical white canvases and compare bytes.
    w = max(neat.size[0], messy.size[0])
    h = max(neat.size[1], messy.size[1])

    def on_canvas(im):
        c = Image.new("RGBA", (w, h), (255, 255, 255, 255))
        c.alpha_composite(im, (0, 0))
        return c.tobytes()

    assert on_canvas(neat) != on_canvas(messy)


def test_jitter_zero_is_deterministic_without_seed():
    # With jitter 0 there is no randomness to observe, so two runs (even with no
    # seed) must match.
    a = HandwritingRenderer(RenderConfig(jitter=0.0)).render(LONG)
    b = HandwritingRenderer(RenderConfig(jitter=0.0)).render(LONG)
    assert a.tobytes() == b.tobytes()


# --- color / config plumbing ----------------------------------------------


def test_custom_color_changes_ink():
    blue = HandwritingRenderer(
        RenderConfig(seed=1, color="#0000ff", paper="blank")
    ).render(SHORT)
    red = HandwritingRenderer(
        RenderConfig(seed=1, color="#ff0000", paper="blank")
    ).render(SHORT)
    assert blue.tobytes() != red.tobytes()


def test_size_affects_dimensions():
    small = HandwritingRenderer(RenderConfig(seed=1, size=24, width=0)).render(SHORT)
    big = HandwritingRenderer(RenderConfig(seed=1, size=96, width=0)).render(SHORT)
    assert big.size[1] > small.size[1]


# --- validation ------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"size": 0},
        {"size": -5},
        {"jitter": -1},
        {"line_spacing": 0},
        {"margin": -1},
    ],
)
def test_invalid_config_raises(kwargs):
    with pytest.raises(ValueError):
        RenderConfig(**kwargs)


def test_bad_paper_style_raises():
    with pytest.raises(ValueError):
        HandwritingRenderer(RenderConfig(paper="rainbow")).render(SHORT)


def test_missing_font_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        HandwritingRenderer(RenderConfig(font_path=tmp_path / "nope.ttf"))


def test_empty_text_still_produces_valid_image():
    img = HandwritingRenderer(RenderConfig(seed=1)).render("")
    assert img.mode == "RGBA"
    assert img.size[0] > 0 and img.size[1] > 0
