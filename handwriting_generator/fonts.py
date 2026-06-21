"""Bundled-font discovery.

The package ships a permissively-licensed handwriting font ("Shadows Into
Light" by Kimberly Geswein, SIL Open Font License 1.1) under
``handwriting_generator/fonts/``. The accompanying ``OFL.txt`` is the font's
license and is distributed alongside it as the OFL requires.
"""

from __future__ import annotations

from pathlib import Path

#: Filename of the bundled default handwriting font.
DEFAULT_FONT_FILENAME = "ShadowsIntoLight.ttf"

#: Human-readable name of the bundled font (for README / --help / metadata).
DEFAULT_FONT_NAME = "Shadows Into Light"


def fonts_dir() -> Path:
    """Absolute path to the directory holding the bundled font + license."""
    return Path(__file__).resolve().parent / "fonts"


def default_font_path() -> Path:
    """Absolute path to the bundled default handwriting font (``.ttf``).

    Raises:
        FileNotFoundError: if the bundled font is missing from the install
            (e.g. packaging dropped the package data).
    """
    path = fonts_dir() / DEFAULT_FONT_FILENAME
    if not path.is_file():
        raise FileNotFoundError(
            f"Bundled handwriting font not found at {path!s}. "
            "The package data may not have been installed correctly."
        )
    return path


def license_path() -> Path:
    """Absolute path to the bundled font's OFL license text."""
    return fonts_dir() / "OFL.txt"
