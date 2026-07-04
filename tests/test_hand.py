"""End-to-end tests for personal-handwriting capture (template -> ingest -> render).

No real handwriting is needed: we synthesize a "filled" template by drawing each
guide character darkly into its write-box with the bundled font, then ingest and
render that. Fully deterministic, no private data.
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from handwriting_generator import template as T
from handwriting_generator.cli import main
from handwriting_generator.fonts import default_font_path
from handwriting_generator.hand import HandPack, hands_dir
from handwriting_generator.ingest import ingest
from handwriting_generator.render import HandwritingRenderer, RenderConfig

CHARSET = "aeht"  # enough to spell "theat", "heat", etc.


def _synthesize_filled(charset: str = CHARSET, samples: int = 1, rotate: float = 0.0):
    """Draw dark glyphs into each write-box to mimic a hand-filled template."""
    img = T.build_template(charset, samples).convert("RGB")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(str(default_font_path()), size=72)
    ascent, _descent = font.getmetrics()
    for i, ch in enumerate(T.cell_slots(charset, samples)):
        if not ch.strip():
            continue
        ox, oy = T.cell_origin(i)
        baseline_y = oy + T.BASELINE_IN_CELL
        gl = font.getlength(ch)
        draw.text(
            (ox + (T.CELL_W - gl) / 2, baseline_y - ascent),
            ch,
            font=font,
            fill=(10, 10, 10),
        )
    if rotate:
        img = img.rotate(
            rotate, expand=True, resample=Image.BICUBIC, fillcolor=(255, 255, 255)
        )
    return img


def _dark_pixels(path) -> int:
    arr = np.asarray(Image.open(path).convert("RGB"))
    return int((arr.min(axis=2) < 120).sum())


def test_template_matches_geometry():
    img = T.build_template("abc", samples=2)
    assert (img.width, img.height) == T.page_size(len(T.cell_slots("abc", 2)))


def test_ingest_then_render(tmp_path):
    filled = tmp_path / "filled.png"
    _synthesize_filled().save(filled)
    pack_dir = tmp_path / "me"

    meta = ingest([filled], pack_dir, charset=CHARSET, samples=1, name="me")
    for ch in CHARSET:
        assert meta["glyphs"].get(ch), f"character {ch!r} was not captured"
    assert meta["glyph_count"] == len(CHARSET)
    assert (pack_dir / "hand.json").is_file()

    pack = HandPack(pack_dir)
    assert all(pack.has(ch) for ch in CHARSET)

    out = tmp_path / "out.png"
    HandwritingRenderer(RenderConfig(hand_path=str(pack_dir), seed=1, width=0)).save(
        "theat", out
    )
    assert out.is_file()
    assert _dark_pixels(out) > 100, "rendered hand text has no visible ink"


def test_hand_differs_from_font(tmp_path):
    filled = tmp_path / "f.png"
    _synthesize_filled().save(filled)
    pack_dir = tmp_path / "h"
    ingest([filled], pack_dir, charset=CHARSET, samples=1)

    font_out = tmp_path / "font.png"
    hand_out = tmp_path / "hand.png"
    HandwritingRenderer(RenderConfig(seed=3, width=0)).save("heat", font_out)
    HandwritingRenderer(RenderConfig(hand_path=str(pack_dir), seed=3, width=0)).save(
        "heat", hand_out
    )
    assert Image.open(font_out).tobytes() != Image.open(hand_out).tobytes()


def test_multi_sample_variation(tmp_path):
    filled = tmp_path / "f.png"
    _synthesize_filled(samples=2).save(filled)
    pack_dir = tmp_path / "v"
    meta = ingest([filled], pack_dir, charset=CHARSET, samples=2)
    for ch in CHARSET:
        assert len(meta["glyphs"][ch]) == 2


def test_missing_glyph_falls_back(tmp_path):
    filled = tmp_path / "f.png"
    _synthesize_filled(charset="ae").save(filled)
    pack_dir = tmp_path / "partial"
    ingest([filled], pack_dir, charset="ae", samples=1)

    out = tmp_path / "o.png"
    # 'c' and 'f' were never captured -> must not crash, must still ink them.
    HandwritingRenderer(RenderConfig(hand_path=str(pack_dir), seed=4, width=0)).save(
        "cafe", out
    )
    assert out.is_file()
    assert _dark_pixels(out) > 100


def test_registration_survives_rotation(tmp_path):
    filled = tmp_path / "rot.png"
    _synthesize_filled(rotate=2.5).save(filled)
    pack_dir = tmp_path / "rothand"
    meta = ingest([filled], pack_dir, charset=CHARSET, samples=1)
    assert len(meta["glyphs"]) >= len(CHARSET) - 1


def test_hands_dir_env(tmp_path, monkeypatch):
    monkeypatch.setenv("HANDWRITING_HOME", str(tmp_path))
    assert hands_dir() == tmp_path / "hands"


def test_cli_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setenv("HANDWRITING_HOME", str(tmp_path))
    tmpl = tmp_path / "t.png"
    assert main(["template", "-o", str(tmpl), "--charset", CHARSET]) == 0
    assert tmpl.is_file()

    filled = tmp_path / "filled.png"
    _synthesize_filled().save(filled)
    assert (
        main(["ingest", "-t", str(filled), "--name", "cli", "--charset", CHARSET]) == 0
    )

    out = tmp_path / "o.png"
    assert main(["theat", "--hand", "cli", "-o", str(out), "--width", "0"]) == 0
    assert out.is_file()
