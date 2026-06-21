"""Command-line interface for handwriting-generator.

Thin argparse wrapper over :mod:`handwriting_generator.render`. All real work
lives in the library; this module only parses flags and wires them up.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from . import __version__
from .fonts import DEFAULT_FONT_NAME
from .paper import VALID_PAPER_STYLES
from .render import HandwritingRenderer, RenderConfig


def _positive_int(value: str) -> int:
    ivalue = int(value)
    if ivalue <= 0:
        raise argparse.ArgumentTypeError(f"must be a positive integer, got {value!r}")
    return ivalue


def _nonneg_float(value: str) -> float:
    fvalue = float(value)
    if fvalue < 0:
        raise argparse.ArgumentTypeError(f"must be >= 0, got {value!r}")
    return fvalue


def _positive_float(value: str) -> float:
    fvalue = float(value)
    if fvalue <= 0:
        raise argparse.ArgumentTypeError(f"must be > 0, got {value!r}")
    return fvalue


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="handwriting-generator",
        description=(
            "Render text as a natural-looking handwriting PNG using a "
            "handwriting-style font with subtle per-glyph randomization. "
            "Runs fully offline."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    src = parser.add_argument_group("input")
    src.add_argument(
        "text",
        nargs="?",
        help="The text to render. Omit when using --input.",
    )
    src.add_argument(
        "--input",
        "-i",
        metavar="FILE",
        help="Read text from FILE instead of the positional argument "
        "(use '-' for stdin).",
    )

    parser.add_argument(
        "--output",
        "-o",
        metavar="PATH",
        default="handwriting.png",
        help="Output PNG path.",
    )

    style = parser.add_argument_group("style")
    style.add_argument(
        "--font",
        metavar="PATH",
        default=None,
        help=f"Path to a .ttf/.otf font. Default: bundled '{DEFAULT_FONT_NAME}' "
        "(SIL OFL).",
    )
    style.add_argument(
        "--size",
        type=_positive_int,
        default=48,
        help="Font size in points.",
    )
    style.add_argument(
        "--color",
        default="#1a1a8a",
        metavar="COLOR",
        help="Ink color (e.g. '#1a1a8a', 'black', 'rgb(20,20,138)').",
    )
    style.add_argument(
        "--width",
        type=int,
        default=1000,
        metavar="PX",
        help="Word-wrap column width in pixels. Use 0 to disable wrapping "
        "(only explicit newlines break lines).",
    )
    style.add_argument(
        "--jitter",
        type=_nonneg_float,
        default=1.0,
        metavar="FLOAT",
        help="Messiness: 0 = neat/straight; higher = messier (per-glyph "
        "baseline offset, rotation, and size wobble).",
    )
    style.add_argument(
        "--line-spacing",
        type=_positive_float,
        default=1.0,
        metavar="MULT",
        help="Line height multiplier (1.0 = font default).",
    )
    style.add_argument(
        "--paper",
        choices=VALID_PAPER_STYLES,
        default="blank",
        help="Background: 'blank' sheet, 'lined' notebook, or 'none' (transparent).",
    )
    style.add_argument(
        "--margin",
        type=_positive_int,
        default=40,
        metavar="PX",
        help="Padding around the text on all sides, in pixels.",
    )
    style.add_argument(
        "--seed",
        type=int,
        default=None,
        metavar="N",
        help="RNG seed for reproducible output. Same text+seed+settings => "
        "byte-identical PNG.",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def _read_text(args: argparse.Namespace, parser: argparse.ArgumentParser) -> str:
    if args.input is not None:
        if args.input == "-":
            return sys.stdin.read()
        path = Path(args.input)
        if not path.is_file():
            parser.error(f"input file not found: {args.input}")
        return path.read_text(encoding="utf-8")
    if args.text is not None:
        return args.text
    parser.error("no text given: pass TEXT positionally or use --input FILE")
    raise AssertionError("unreachable")  # parser.error exits


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    text = _read_text(args, parser)

    # Treat --width 0 as "disable wrapping" (None inside the library).
    width: Optional[int] = args.width if args.width and args.width > 0 else None

    config = RenderConfig(
        font_path=args.font,
        size=args.size,
        color=args.color,
        width=width,
        jitter=args.jitter,
        line_spacing=args.line_spacing,
        paper=args.paper,
        margin=args.margin,
        seed=args.seed,
    )

    try:
        renderer = HandwritingRenderer(config)
        w, h = renderer.save(text, args.output)
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {args.output} ({w}x{h})")
    return 0


def run() -> None:
    """Console-script entry point."""
    raise SystemExit(main())


if __name__ == "__main__":  # pragma: no cover
    run()
