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


class _Fmt(
    argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter
):
    """Show argument defaults *and* keep the examples block literally."""


_EXAMPLES = """\
examples:
  # generic handwriting font
  handwriting-generator "Hello, world!" -o out.png

  # multi-line text from a file, on lined notebook paper
  handwriting-generator --input note.txt --paper lined -o note.png
  handwriting-generator $'Dear Sam,\\nThanks for the book!' --color black

  # YOUR own handwriting -- capture once, reuse forever:
  handwriting-generator template -o my-template.png      # print & fill in by hand
  handwriting-generator ingest -t my-template-scan.png --name me
  handwriting-generator "in my own hand" --hand me -o mine.png

note: default ink is blue (#1a1a8a) by design; pass --color black for black.
      "template" and "ingest" are subcommands; to render those literal words use
      e.g.  handwriting-generator render "template"
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="handwriting-generator",
        description=(
            "Render text as a natural-looking handwriting PNG. Uses a "
            "handwriting-style font with subtle per-glyph randomization by "
            "default, OR your own real handwriting captured with the 'template' "
            "and 'ingest' subcommands. Runs fully offline (no ML, no network)."
        ),
        epilog=_EXAMPLES,
        formatter_class=_Fmt,
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
        "--hand",
        metavar="NAME|DIR",
        default=None,
        help="Render in YOUR captured handwriting: a hand pack made with the "
        "'ingest' subcommand (by --name, or a directory path). Characters you "
        "didn't capture fall back to --font.",
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
    raw = list(sys.argv[1:] if argv is None else argv)
    if raw and raw[0] == "template":
        return _cmd_template(raw[1:])
    if raw and raw[0] == "ingest":
        return _cmd_ingest(raw[1:])
    if raw and raw[0] == "render":
        # Explicit escape so the literal words "template"/"ingest" can be rendered.
        raw = raw[1:]

    parser = build_parser()
    args = parser.parse_args(raw)

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
        hand_path=args.hand,
    )

    try:
        renderer = HandwritingRenderer(config)
        w, h = renderer.save(text, args.output)
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {args.output} ({w}x{h})")
    return 0


def _cmd_template(argv: Sequence[str]) -> int:
    p = argparse.ArgumentParser(
        prog="handwriting-generator template",
        description="Generate a printable template for capturing your handwriting. "
        "Print it, write each character in its box (trace the faint guide or "
        "write freely), then scan/photograph it and feed it to 'ingest'.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--output", "-o", default="handwriting-template.png", metavar="PATH")
    p.add_argument(
        "--charset",
        default=None,
        help="Characters to capture (default: letters, digits, common punctuation).",
    )
    p.add_argument(
        "--samples",
        type=_positive_int,
        default=1,
        help="Write-boxes per character; more gives more natural variation.",
    )
    p.add_argument(
        "--font", default=None, metavar="PATH", help="Font for the faint guide glyphs."
    )
    args = p.parse_args(argv)

    from .template import DEFAULT_CHARSET, save_template

    charset = args.charset if args.charset is not None else DEFAULT_CHARSET
    try:
        w, h = save_template(
            args.output,
            charset=charset,
            samples=args.samples,
            guide_font_path=args.font,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote {args.output} ({w}x{h}).")
    print(
        "Print it, write each character in its box, scan/photograph it flat, then:\n"
        "  handwriting-generator ingest --template FILLED.png --name NAME"
    )
    return 0


def _cmd_ingest(argv: Sequence[str]) -> int:
    p = argparse.ArgumentParser(
        prog="handwriting-generator ingest",
        description="Turn filled-in template scans into a reusable 'hand pack' of "
        "your real glyphs, usable via --hand.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--template",
        "-t",
        action="append",
        required=True,
        metavar="IMG",
        help="A filled-in, scanned template image. Repeat -t for multiple pages.",
    )
    p.add_argument(
        "--name",
        default=None,
        help="Store the hand pack under this name "
        "(~/.handwriting-generator/hands/NAME).",
    )
    p.add_argument(
        "--out",
        default=None,
        metavar="DIR",
        help="Explicit output directory (overrides --name).",
    )
    p.add_argument(
        "--charset",
        default=None,
        help="Charset the template was generated with (default: the standard set).",
    )
    p.add_argument(
        "--samples",
        type=_positive_int,
        default=1,
        help="Samples-per-character the template was generated with.",
    )
    args = p.parse_args(argv)

    if not args.out and not args.name:
        p.error("provide --name NAME or --out DIR")
    for t in args.template:
        if not Path(t).is_file():
            p.error(f"template image not found: {t}")

    from .hand import hands_dir
    from .ingest import ingest
    from .template import DEFAULT_CHARSET

    out = args.out if args.out else str(hands_dir() / args.name)
    charset = args.charset if args.charset is not None else DEFAULT_CHARSET
    try:
        meta = ingest(
            args.template,
            out,
            charset=charset,
            samples=args.samples,
            name=args.name,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    n_glyphs = meta.get("glyph_count", 0)
    n_chars = len(meta.get("glyphs", {}))
    print(f"Captured {n_glyphs} glyph(s) across {n_chars} character(s) -> {out}")
    ref = args.name if args.name else out
    print(f'Render with:  handwriting-generator "your text" --hand {ref}')
    if n_glyphs == 0:
        print(
            "warning: no ink detected. Use a dark pen, write inside the boxes, and "
            "scan/photograph the sheet flat and well-lit.",
            file=sys.stderr,
        )
        return 1
    return 0


def run() -> None:
    """Console-script entry point."""
    raise SystemExit(main())


if __name__ == "__main__":  # pragma: no cover
    run()
