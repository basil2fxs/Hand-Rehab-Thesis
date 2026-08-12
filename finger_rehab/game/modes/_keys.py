"""Tiny keyboard-name resolver shared by every mode's handle_event.

Pygame is annoyingly inconsistent: letter keys are `pygame.K_a` (lowercase)
but punctuation keys are `pygame.K_SEMICOLON` (uppercase). The mode keymaps
in config use lowercase names like `semicolon`, so a naive
`getattr(pygame, "K_" + name.lower())` lookup just misses every punctuation
key. I burned half an hour wondering why my right pinky press didn't
register before tracking this down.
"""
from __future__ import annotations

import pygame


def resolve_key(name: str) -> int | None:
    """Return the pygame K_* constant for `name`, or None if it doesn't
    match anything. Tries lowercase first (works for letters / digits),
    falls back to uppercase (works for SEMICOLON / SPACE / COMMA etc.)."""
    if not name:
        return None
    n = name.lower()
    code = getattr(pygame, f"K_{n}", None)
    if code is not None:
        return code
    return getattr(pygame, f"K_{n.upper()}", None)


def keymap_for_hand(hand_mode: str) -> str:
    """Pick which config key holds the right keyboard map for the active
    hand mode. Centralised so every mode (classic / adaptive / rhythm)
    agrees on which map to read.

    - `both`  -> `game.keyboard_map_bilateral` (8 keys)
    - `left`  -> `game.keyboard_map_left`     (FDSA, lanes 0..3)
    - `right` -> `game.keyboard_map`          (JKL;, lanes 0..3)
    """
    if hand_mode == "both":
        return "game.keyboard_map_bilateral"
    if hand_mode == "left":
        return "game.keyboard_map_left"
    return "game.keyboard_map"
