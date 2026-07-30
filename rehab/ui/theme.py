"""Colour themes. Three ship by default."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    name: str
    background: tuple[int, int, int]
    foreground: tuple[int, int, int]
    muted: tuple[int, int, int]
    accent: tuple[int, int, int]
    success: tuple[int, int, int]
    warning: tuple[int, int, int]
    error: tuple[int, int, int]
    lane_idle: tuple[tuple[int, int, int], ...]
    lane_active: tuple[tuple[int, int, int], ...]
    lane_hit: tuple[int, int, int]
    lane_miss: tuple[int, int, int]


# Fixed finger colours, identical on both hands and in every theme:
# index = orange, middle = light blue, ring = black, pinky = yellow.
# Idle tiles are the softer cut, lane_active is the same colour pushed
# harder for the "stim fired" state. Green and red stay out of the
# palette so the full-tile hit/miss flash still reads as feedback.
# LaneStrip picks white or dark label text from the fill's luminance,
# which is what keeps the black ring tile readable.
CLINICAL = Theme(
    name="clinical",
    background=(248, 250, 252),
    foreground=(15, 23, 42),
    muted=(100, 116, 139),
    accent=(37, 99, 235),
    success=(22, 163, 74),
    warning=(202, 138, 4),
    error=(220, 38, 38),
    lane_idle=((254, 215, 170),   # light orange (index)
               (186, 230, 253),   # light blue (middle)
               (71, 85, 105),     # slate black (ring)
               (254, 240, 138)),  # light yellow (pinky)
    lane_active=((234, 88, 12),    # orange
                  (14, 165, 233),   # light blue
                  (15, 23, 42),     # black
                  (202, 138, 4)),   # yellow
    lane_hit=(34, 197, 94),
    lane_miss=(239, 68, 68),
)


DARK = Theme(
    name="dark",
    background=(15, 23, 42),
    foreground=(241, 245, 249),
    muted=(148, 163, 184),
    accent=(96, 165, 250),
    success=(74, 222, 128),
    warning=(250, 204, 21),
    error=(248, 113, 113),
    # Same orange / light blue / black / yellow order, dimmed for the
    # dark background. "Black" becomes a near-black grey so the tile is
    # still distinguishable from the page behind it.
    lane_idle=((124, 45, 18),       # deep orange (index)
               (12, 74, 110),       # deep light-blue (middle)
               (24, 24, 27),        # near black (ring)
               (113, 63, 18)),      # deep yellow (pinky)
    lane_active=((251, 146, 60),
                  (56, 189, 248),
                  (82, 82, 91),
                  (250, 204, 21)),
    lane_hit=(74, 222, 128),
    lane_miss=(248, 113, 113),
)


HIGH_CONTRAST = Theme(
    name="high_contrast",
    background=(0, 0, 0),
    foreground=(255, 255, 255),
    muted=(200, 200, 200),
    accent=(255, 255, 0),
    success=(0, 255, 0),
    warning=(255, 165, 0),
    error=(255, 0, 0),
    # Same orange / light blue / black / yellow order at high contrast.
    # On a pure black page the ring finger uses greys so the tile stays
    # visible while keeping its black identity.
    lane_idle=((110, 55, 0),      # dark orange (index)
               (0, 70, 110),      # dark light-blue (middle)
               (55, 55, 58),      # dark grey/black (ring)
               (110, 110, 0)),    # dark yellow (pinky)
    lane_active=((255, 165, 0),
                  (0, 200, 255),
                  (190, 190, 195),
                  (255, 255, 0)),
    lane_hit=(0, 255, 0),
    lane_miss=(255, 0, 0),
)


THEMES = {t.name: t for t in (CLINICAL, DARK, HIGH_CONTRAST)}


def get(name: str) -> Theme:
    return THEMES.get(name, CLINICAL)
