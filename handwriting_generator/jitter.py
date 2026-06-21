"""Per-glyph randomization ("jitter") that makes typeset text look handwritten.

The renderer draws each glyph individually and perturbs it slightly. All
randomness flows from a single seeded :class:`random.Random` instance so that a
given ``(text, seed, settings)`` triple always produces byte-identical output.

A ``jitter`` strength of ``0.0`` disables all perturbation (neat, ruler-straight
text). Larger values produce messier writing: bigger baseline wander, more
rotation, and more size wobble.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class GlyphJitter:
    """Concrete perturbation applied to one glyph.

    Attributes:
        dx: Horizontal nudge in pixels (advance is computed from the *unjittered*
            glyph so dx does not accumulate drift across a line).
        dy: Vertical baseline offset in pixels (positive = lower).
        rotation: Rotation in degrees (counter-clockwise positive).
        scale: Multiplicative size factor around 1.0.
    """

    dx: float
    dy: float
    rotation: float
    scale: float


# Base magnitudes at jitter == 1.0. Chosen to look like natural handwriting
# variance at the default size without becoming illegible.
_BASE_DY = 2.2  # px of vertical baseline wander
_BASE_DX = 0.9  # px of horizontal nudge
_BASE_ROTATION = 2.6  # degrees of per-glyph tilt
_BASE_SCALE = 0.05  # +/- fraction of size wobble


def glyph_jitter(rng: random.Random, jitter: float) -> GlyphJitter:
    """Sample a :class:`GlyphJitter` for the next glyph from ``rng``.

    Always draws the *same number* of values from ``rng`` regardless of
    ``jitter`` so that the RNG stream stays aligned (and seeds stay
    reproducible) even when jitter is 0.

    Args:
        rng: Seeded RNG; advanced by exactly four draws per call.
        jitter: Non-negative strength multiplier (0 disables perturbation).

    Returns:
        The sampled perturbation. With ``jitter == 0`` every field is the
        identity value (0 offsets, 0 rotation, scale 1.0).
    """
    # Draw unconditionally to keep the stream deterministic across jitter values.
    r_dy = rng.uniform(-1.0, 1.0)
    r_dx = rng.uniform(-1.0, 1.0)
    r_rot = rng.uniform(-1.0, 1.0)
    r_scale = rng.uniform(-1.0, 1.0)

    if jitter <= 0.0:
        return GlyphJitter(dx=0.0, dy=0.0, rotation=0.0, scale=1.0)

    return GlyphJitter(
        dx=r_dx * _BASE_DX * jitter,
        dy=r_dy * _BASE_DY * jitter,
        rotation=r_rot * _BASE_ROTATION * jitter,
        scale=1.0 + r_scale * _BASE_SCALE * jitter,
    )


def line_baseline_offset(rng: random.Random, jitter: float) -> float:
    """Sample a small whole-line vertical drift so lines aren't perfectly level.

    Advances ``rng`` by exactly one draw. Returns 0.0 when ``jitter == 0``.
    """
    r = rng.uniform(-1.0, 1.0)
    if jitter <= 0.0:
        return 0.0
    return r * _BASE_DY * 0.8 * jitter
