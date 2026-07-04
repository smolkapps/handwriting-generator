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


def _ncc(a, b) -> float:
    """Normalized cross-correlation of two same-shape arrays (1.0 = identical)."""
    a = a.astype(float) - a.astype(float).mean()
    b = b.astype(float) - b.astype(float).mean()
    denom = np.sqrt((a * a).sum()) * np.sqrt((b * b).sum())
    return float((a * b).sum() / denom) if denom > 1e-9 else 0.0


def test_full_page_capture_is_accurate(tmp_path):
    """Full multi-row page: captured glyphs must match what was written.

    Guards against registration-mark detection being polluted by the sheet's own
    ink (which silently mis-warps every glyph). A one-row charset hides this, so
    use the full alphabet (4 rows).
    """
    charset = "abcdefghijklmnopqrstuvwxyz"
    filled = _synthesize_filled(charset)
    fpath = tmp_path / "full.png"
    filled.save(fpath)
    pack_dir = tmp_path / "full"
    meta = ingest([fpath], pack_dir, charset=charset, samples=1)
    assert len(meta["glyphs"]) == len(charset), "not every glyph was captured"

    from handwriting_generator.ingest import _extract_glyph, _to_gray

    gray = _to_gray(filled)  # synthetic fill is already canonical size
    pack = HandPack(pack_dir)
    checked = 0
    for i, ch in enumerate(T.cell_slots(charset, 1)):
        truth = _extract_glyph(gray, i)
        assert truth is not None, f"no truth ink for {ch!r}"
        tcov = truth[0].astype(float)
        rec = pack._glyphs[ch][0]
        stored = np.asarray(
            pack._coverage(rec["file"]).resize((tcov.shape[1], tcov.shape[0]))
        ).astype(float)
        ncc = _ncc(tcov, stored)
        assert ncc > 0.6, f"{ch!r} capture uncorrelated with input (ncc={ncc:.2f})"
        checked += 1
    assert checked >= 20


def test_blank_template_captures_nothing(tmp_path):
    """A printed-but-unfilled template (only faint guides) must capture 0 glyphs."""
    blank = tmp_path / "blank.png"
    T.build_template(CHARSET, 1).save(blank)
    pack_dir = tmp_path / "blank"
    meta = ingest([blank], pack_dir, charset=CHARSET, samples=1)
    assert meta["glyph_count"] == 0
    assert meta["glyphs"] == {}


def test_baseline_placement(tmp_path):
    """Rendered captured glyphs must sit on the writing baseline."""
    from PIL import ImageFont

    filled = tmp_path / "f.png"
    _synthesize_filled().save(filled)
    pack_dir = tmp_path / "bl"
    ingest([filled], pack_dir, charset=CHARSET, samples=1)

    size, margin = 48, 40
    img = HandwritingRenderer(
        RenderConfig(
            hand_path=str(pack_dir),
            size=size,
            margin=margin,
            seed=1,
            width=0,
            jitter=0.0,
            paper="none",
        )
    ).render("hate")  # no descenders -> ink bottom should land near the baseline
    alpha = np.asarray(img)[:, :, 3]
    rows = np.nonzero(alpha.max(axis=1) > 40)[0]
    assert len(rows) > 0, "nothing rendered"
    bottom = int(rows.max())
    ascent = ImageFont.truetype(str(default_font_path()), size).getmetrics()[0]
    baseline = margin + ascent
    assert abs(bottom - baseline) <= 0.4 * size, (
        f"ink bottom {bottom} not near baseline {baseline}"
    )


def test_render_escape_for_reserved_words(tmp_path):
    """`render` subcommand escape renders the literal words 'template'/'ingest'."""
    out = tmp_path / "word.png"
    assert main(["render", "template", "-o", str(out), "--width", "0"]) == 0
    assert out.is_file()


def test_scaled_rotated_full_page_capture(tmp_path):
    """A scaled + rotated full page (realistic scan) must still capture accurately.

    Guards the erosion-based mark detector's skew tolerance — a tight-window
    detector regressed this to mean NCC ~0.31.
    """
    from PIL import Image as _Image

    from handwriting_generator.ingest import _extract_glyph, _to_gray

    charset = "abcdefghijklmnopqrstuvwxyz0123456789"
    truth = _synthesize_filled(charset)
    w, h = truth.size
    scan = truth.resize((int(w * 1.4), int(h * 1.4)), _Image.BICUBIC).rotate(
        3, expand=True, resample=_Image.BICUBIC, fillcolor=(255, 255, 255)
    )
    fp = tmp_path / "scan.png"
    scan.save(fp)
    pack_dir = tmp_path / "sc"
    meta = ingest([fp], pack_dir, charset=charset, samples=1)
    assert len(meta["glyphs"]) == len(charset)

    gray = _to_gray(truth)
    pack = HandPack(pack_dir)
    nccs = []
    for i, ch in enumerate(T.cell_slots(charset, 1)):
        t = _extract_glyph(gray, i)
        if t is None or ch not in pack._glyphs:
            continue
        tcov = t[0].astype(float)
        rec = pack._glyphs[ch][0]
        stored = np.asarray(
            pack._coverage(rec["file"]).resize((tcov.shape[1], tcov.shape[0]))
        ).astype(float)
        nccs.append(_ncc(tcov, stored))
    mean_ncc = sum(nccs) / len(nccs)
    assert mean_ncc > 0.75, f"skewed-scan capture degraded (mean NCC={mean_ncc:.2f})"
