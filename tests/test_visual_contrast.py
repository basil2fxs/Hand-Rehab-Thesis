"""Text remains legible on every theme's buttons and finger fills."""
from finger_rehab.ui.theme import THEMES
from finger_rehab.ui.widgets import contrast_text, surface_colour


def luminance(rgb):
    channels=[c/255 for c in rgb]
    return sum((c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4)*w
               for c,w in zip(channels,(.2126,.7152,.0722)))


def test_contrast_on_every_finger_state():
    for theme in THEMES.values():
        for fill in (*theme.lane_idle,*theme.lane_active,theme.accent,surface_colour(theme)):
            a,b=sorted([luminance(fill),luminance(contrast_text(fill))])
            assert (b+.05)/(a+.05)>=4.5
