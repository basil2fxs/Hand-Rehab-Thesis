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


# Lane palette intentionally avoids green and red so the hit/miss flash
# (which uses green and red across the whole tile) reads as feedback, not
# as the lane's default identity. Order: index = blue, middle = purple,
# ring = gold/yellow, little = orange. Same scheme across all themes so
# muscle memory carries between sessions.
CLINICAL = Theme(
    name="clinical",
    background=(248, 250, 252),
    foreground=(15, 23, 42),
    muted=(100, 116, 139),
    accent=(37, 99, 235),
    success=(22, 163, 74),
    warning=(202, 138, 4),
    error=(220, 38, 38),
    # Light pastels for idle. No light green, no light red.
    lane_idle=((191, 219, 254),   # light blue (index)
               (221, 214, 254),   # light purple (middle)
               (253, 230, 138),   # light gold (ring)
               (254, 215, 170)),  # light orange (little)
    # Saturated versions of the same hues for the "stim fired" state.
    lane_active=((37, 99, 235),    # blue
                  (124, 58, 237),   # purple
                  (202, 138, 4),    # gold
                  (234, 88, 12)),   # orange
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
    # Dim variants of the same blue / purple / gold / orange.
    lane_idle=((30, 58, 138),       # deep blue
               (76, 29, 149),       # deep purple
               (113, 63, 18),       # deep gold/brown
               (124, 45, 18)),      # deep orange
    lane_active=((96, 165, 250),
                  (167, 139, 250),
                  (250, 204, 21),
                  (251, 146, 60)),
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
    # Distinct dark backgrounds for each finger that are NOT green or red.
    lane_idle=((40, 40, 100),    # navy
               (70, 40, 100),    # plum
               (100, 100, 40),   # olive/gold
               (100, 60, 40)),   # rust/orange
    # Vivid contrast variants; cyan/magenta/yellow/white skip green and red.
    lane_active=((255, 255, 0),
                  (0, 255, 255),
                  (255, 0, 255),
                  (255, 255, 255)),
    lane_hit=(0, 255, 0),
    lane_miss=(255, 0, 0),
)


THEMES = {t.name: t for t in (CLINICAL, DARK, HIGH_CONTRAST)}


def get(name: str) -> Theme:
    return THEMES.get(name, CLINICAL)
