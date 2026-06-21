"""Tests for the pure layout / word-wrap logic."""

from __future__ import annotations

from PIL import ImageFont

from handwriting_generator.fonts import default_font_path
from handwriting_generator.layout import measure_text_width, wrap_text


def _font(size=48):
    return ImageFont.truetype(str(default_font_path()), size=size)


def test_no_wrap_when_width_none():
    font = _font()
    lines = wrap_text("hello world foo bar baz", font, None)
    assert lines == ["hello world foo bar baz"]


def test_explicit_newlines_always_split():
    font = _font()
    lines = wrap_text("a\nb\nc", font, None)
    assert lines == ["a", "b", "c"]


def test_wrap_breaks_long_paragraph_into_multiple_lines():
    font = _font()
    text = "the quick brown fox jumps over the lazy dog again and again"
    lines = wrap_text(text, font, max_width=200.0)
    assert len(lines) > 1
    # Every wrapped line fits within the width.
    for ln in lines:
        assert measure_text_width(font, ln) <= 200.0


def test_blank_lines_preserved():
    font = _font()
    lines = wrap_text("para one\n\npara two", font, max_width=1000.0)
    assert "" in lines
    assert lines[0].startswith("para one")
    assert lines[-1].startswith("para two")


def test_single_overlong_word_is_hard_split():
    font = _font()
    word = "supercalifragilisticexpialidocious"
    lines = wrap_text(word, font, max_width=80.0)
    assert len(lines) > 1
    for ln in lines:
        assert ln  # no empty fragments
        assert measure_text_width(font, ln) <= 80.0
    # Re-joining the fragments reproduces the original word (no chars dropped).
    assert "".join(lines) == word


def test_wrap_width_zero_disables_wrapping():
    font = _font()
    text = "aaa bbb ccc ddd eee fff ggg hhh"
    lines = wrap_text(text, font, max_width=0)
    assert lines == [text]


def test_measure_empty_is_zero():
    assert measure_text_width(_font(), "") == 0.0
