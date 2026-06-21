"""Tests for the argparse CLI."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from handwriting_generator.cli import main

from .conftest import count_ink_pixels


def test_cli_positional_text_writes_png(tmp_path: Path, capsys):
    out = tmp_path / "note.png"
    rc = main(["Dear John, hello there.", "-o", str(out), "--seed", "1"])
    assert rc == 0
    assert out.is_file()

    captured = capsys.readouterr()
    assert str(out) in captured.out  # prints the written path

    with Image.open(out) as img:
        assert img.format == "PNG"
        assert count_ink_pixels(img) > 0


def test_cli_input_file(tmp_path: Path):
    src = tmp_path / "letter.txt"
    src.write_text("Reading from a file works fine.", encoding="utf-8")
    out = tmp_path / "letter.png"
    rc = main(["--input", str(src), "-o", str(out), "--seed", "2"])
    assert rc == 0
    with Image.open(out) as img:
        assert count_ink_pixels(img) > 0


def test_cli_stdin(tmp_path: Path, monkeypatch):
    import io
    import sys

    monkeypatch.setattr(sys, "stdin", io.StringIO("from stdin"))
    out = tmp_path / "stdin.png"
    rc = main(["--input", "-", "-o", str(out), "--seed", "3"])
    assert rc == 0
    assert out.is_file()


def test_cli_seed_reproducible(tmp_path: Path):
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    main(
        [
            "Some longer text to render here",
            "-o",
            str(a),
            "--seed",
            "7",
            "--jitter",
            "1.5",
        ]
    )
    main(
        [
            "Some longer text to render here",
            "-o",
            str(b),
            "--seed",
            "7",
            "--jitter",
            "1.5",
        ]
    )
    assert a.read_bytes() == b.read_bytes()


def test_cli_all_paper_styles(tmp_path: Path):
    for style in ("blank", "lined", "none"):
        out = tmp_path / f"{style}.png"
        rc = main(["text here", "-o", str(out), "--paper", style, "--seed", "1"])
        assert rc == 0
        assert out.is_file()


def test_cli_missing_text_errors(tmp_path: Path, capsys):
    # No positional and no --input => argparse error (exit code 2).
    try:
        main(["-o", str(tmp_path / "x.png")])
    except SystemExit as e:
        assert e.code == 2
    else:
        raise AssertionError("expected SystemExit from parser.error")


def test_cli_missing_input_file_errors(tmp_path: Path):
    try:
        main(
            [
                "--input",
                str(tmp_path / "does-not-exist.txt"),
                "-o",
                str(tmp_path / "x.png"),
            ]
        )
    except SystemExit as e:
        assert e.code == 2
    else:
        raise AssertionError("expected SystemExit for missing input file")


def test_cli_bad_font_returns_error_code(tmp_path: Path, capsys):
    out = tmp_path / "x.png"
    rc = main(["hi", "-o", str(out), "--font", str(tmp_path / "nope.ttf")])
    assert rc == 1
    assert "error" in capsys.readouterr().err.lower()


def test_cli_width_zero_disables_wrap(tmp_path: Path):
    out = tmp_path / "x.png"
    rc = main(["a b c d e f g", "-o", str(out), "--width", "0", "--seed", "1"])
    assert rc == 0
    assert out.is_file()


def test_cli_jitter_zero_vs_default_differ(tmp_path: Path):
    neat = tmp_path / "neat.png"
    messy = tmp_path / "messy.png"
    text = "the quick brown fox jumps over the lazy dog"
    main([text, "-o", str(neat), "--jitter", "0", "--seed", "1"])
    main([text, "-o", str(messy), "--jitter", "2", "--seed", "1"])
    assert neat.read_bytes() != messy.read_bytes()
