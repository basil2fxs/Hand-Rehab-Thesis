"""Title and Settings layout: what is on screen, and where a click lands.

Two things get checked here that nothing else does.

The footer credit is an exact string. It carries the version the build
stamps into every session's metadata, so a mismatch between the line on
screen and SOFTWARE_VERSION would put one number in the thesis and a
different one in the recorded data.

The rest is hit boxes. Both screens draw some controls from a rect built
in one place and hit-test them from a rect built somewhere else. Where
those two can drift, a click registers on a control the therapist is not
pointing at, which on the Settings screen means buzzing the wrong finger.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from rehab.data.session import SOFTWARE_VERSION


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def title_screen():
    import pygame
    pygame.init()
    pygame.font.init()
    from rehab.config import Config
    from rehab.game.engine import GameEngine
    from rehab.hardware.keyboard_source import KeyboardOnlySource
    from rehab.ui.screens import TitleScreen
    cfg = Config.load()
    cfg.data.setdefault("ui", {})["resolution"] = [1280, 800]
    eng = GameEngine(cfg, KeyboardOnlySource())
    yield TitleScreen(eng), eng
    pygame.quit()


@pytest.fixture
def settings_screen():
    import pygame
    pygame.init()
    pygame.font.init()
    from rehab.config import Config
    from rehab.game.engine import GameEngine
    from rehab.hardware.keyboard_source import KeyboardOnlySource
    from rehab.ui.screens import DiagnosticsScreen
    cfg = Config.load()
    cfg.data.setdefault("ui", {})["resolution"] = [1280, 800]
    eng = GameEngine(cfg, KeyboardOnlySource())
    yield DiagnosticsScreen(eng), eng
    pygame.quit()


def captured_text(screen, monkeypatch) -> list[str]:
    """Every string the screen paints during one draw.

    draw_text is patched in the screens module rather than in widgets so
    the recorder sees the calls the screen itself makes.
    """
    import pygame
    import rehab.ui.screens as screens_mod

    seen: list[str] = []
    original = screens_mod.draw_text

    def recorder(surf, text, pos, *args, **kwargs):
        seen.append(str(text))
        return original(surf, text, pos, *args, **kwargs)

    monkeypatch.setattr(screens_mod, "draw_text", recorder)
    screen.draw(pygame.Surface((1280, 800)))
    return seen


class TestVersionIsOneNumber:
    def test_software_version_is_3_2(self):
        assert SOFTWARE_VERSION == "3.2"

    def test_the_mac_bundle_records_the_same_version(self):
        """finger_rehab.spec repeats the number as a literal, so it can
        drift from SOFTWARE_VERSION without anything failing until a
        built app reports a version the session data disagrees with."""
        spec = (REPO_ROOT / "finger_rehab.spec").read_text(encoding="utf-8")
        found = re.findall(
            r'"CFBundle(?:Short)?Version(?:String)?":\s*"([^"]+)"', spec)
        assert found, "no CFBundle version keys in finger_rehab.spec"
        for value in found:
            assert value == SOFTWARE_VERSION

    def test_session_metadata_carries_it(self):
        from rehab.data.session import Session
        assert Session(participant="T1").software_version == SOFTWARE_VERSION


class TestTitleFooter:
    EXPECTED = "Basil Toufexis | Curtin University 2026 | v3.2"

    def test_footer_reads_exactly_as_asked(self, title_screen, monkeypatch):
        screen, _ = title_screen
        assert self.EXPECTED in captured_text(screen, monkeypatch)

    def test_footer_tracks_software_version(self, title_screen, monkeypatch):
        screen, _ = title_screen
        drawn = captured_text(screen, monkeypatch)
        footer = next(t for t in drawn if t.startswith("Basil Toufexis"))
        assert footer.endswith(f"v{SOFTWARE_VERSION}")

    def test_footer_sits_inside_the_screen(self, title_screen):
        screen, _ = title_screen
        assert screen.layout.height - 20 < screen.layout.height


class TestTitleLayout:
    def test_every_control_is_still_there(self, title_screen):
        screen, _ = title_screen
        assert screen.name_input is not None
        assert screen.age_input is not None
        assert screen.start_btn.label == "START SESSION"
        labels = {label for _r, label, _i, _a in screen._pills}
        assert labels == {"Quit", "Info", "Calibrate", "Settings"}

    def test_the_session_controls_sit_inside_the_card(self, title_screen):
        """The card is drawn from CARD_TOP/CARD_H and the fields are
        placed from the same constants. If one moved without the other
        the button would float outside the block it commits."""
        screen, _ = title_screen
        card = screen.card_rect
        for control in (screen.name_input, screen.age_input,
                        screen.start_btn):
            assert card.contains(control.rect), (
                f"{control.rect} escapes the card {card}")

    def test_the_name_label_has_room_above_the_field(self, title_screen):
        """TextInput draws its label 26px above its rect, so the field
        cannot sit flush against the card's heading."""
        screen, _ = title_screen
        assert screen.name_input.rect.y - 26 > screen.card_rect.y + 20

    def test_nothing_on_the_title_screen_overlaps(self, title_screen):
        screen, _ = title_screen
        rects = [("name", screen.name_input.rect),
                 ("age", screen.age_input.rect),
                 ("start", screen.start_btn.rect)]
        rects += [(label, r) for r, label, _i, _a in screen._pills]
        for i, (an, ar) in enumerate(rects):
            for bn, br in rects[i + 1:]:
                assert not ar.colliderect(br), f"{an} overlaps {bn}"

    def test_everything_stays_on_screen(self, title_screen):
        screen, _ = title_screen
        w, h = screen.layout.width, screen.layout.height
        rects = [screen.card_rect, screen.name_input.rect,
                 screen.age_input.rect, screen.start_btn.rect]
        rects += [r for r, _l, _i, _a in screen._pills]
        for r in rects:
            assert r.left >= 0 and r.right <= w
            assert r.top >= 0 and r.bottom <= h

    def test_the_pills_sit_on_one_baseline(self, title_screen):
        screen, _ = title_screen
        tops = {r.top for r, _l, _i, _a in screen._pills}
        heights = {r.height for r, _l, _i, _a in screen._pills}
        assert len(tops) == 1 and len(heights) == 1

    def test_the_pills_clear_the_card_above_them(self, title_screen):
        screen, _ = title_screen
        for r, label, _i, _a in screen._pills:
            assert r.top > screen.card_rect.bottom, f"{label} runs into card"


class TestTitleClicks:
    """Every control is reachable with the mouse alone."""

    def _click(self, screen, pos):
        import pygame
        for kind in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            screen.handle_event(pygame.event.Event(
                kind, {"button": 1, "pos": pos}))

    @pytest.mark.parametrize("label", ["Quit", "Info", "Calibrate",
                                       "Settings"])
    def test_each_pill_fires_from_the_rect_it_is_drawn_in(
            self, title_screen, label, monkeypatch):
        screen, eng = title_screen
        fired: list[str] = []
        patched = []
        for rect, name, icon, _action in screen._pills:
            patched.append((rect, name, icon,
                            (lambda n=name: fired.append(n))))
        screen._pills = patched
        rect = next(r for r, n, _i, _a in screen._pills if n == label)
        self._click(screen, rect.center)
        assert fired == [label]

    def test_a_click_between_pills_fires_nothing(self, title_screen):
        screen, _ = title_screen
        fired: list[str] = []
        screen._pills = [(r, n, i, (lambda x=n: fired.append(x)))
                         for r, n, i, _a in screen._pills]
        gap_x = (screen.info_rect.right + screen.calibrate_rect.left) // 2
        self._click(screen, (gap_x, screen.info_rect.centery))
        assert fired == []

    def test_clicking_a_field_focuses_it(self, title_screen):
        screen, _ = title_screen
        self._click(screen, screen.name_input.rect.center)
        assert screen.name_input.focused is True
        self._click(screen, screen.age_input.rect.center)
        assert screen.age_input.focused is True
        assert screen.name_input.focused is False

    def test_start_commits_the_typed_name(self, title_screen):
        screen, eng = title_screen
        went: list[str] = []
        eng.show_mode_select = lambda: went.append("modes")
        screen.name_input.text = "P07"
        screen.age_input.text = "64"
        self._click(screen, screen.start_btn.rect.center)
        assert went == ["modes"]
        assert eng.session.participant == "P07"
        assert eng.session.age == "64"

    def test_the_info_overlay_swallows_the_next_click(self, title_screen):
        """The overlay is modal, so a click that closes it must not also
        start a session on the card underneath."""
        screen, eng = title_screen
        went: list[str] = []
        eng.show_mode_select = lambda: went.append("modes")
        screen._show_info = True
        self._click(screen, screen.start_btn.rect.center)
        assert screen._show_info is False
        assert went == []


class TestSettingsGroups:
    """Five labelled panels, every control inside the one it belongs to."""

    def test_the_five_group_headings_are_drawn(self, settings_screen,
                                               monkeypatch):
        import pygame
        import rehab.ui.screens as screens_mod
        screen, _ = settings_screen
        seen: list[str] = []
        original = screens_mod.DiagnosticsScreen._draw_band

        def recorder(self, surf, rect, title, hint=""):
            seen.append(title)
            return original(self, surf, rect, title, hint)

        monkeypatch.setattr(screens_mod.DiagnosticsScreen,
                            "_draw_band", recorder)
        screen.draw(pygame.Surface((1280, 800)))
        assert seen == ["SENSORY CUES", "LEVELS", "FINGER TEST",
                        "ARDUINO PORTS", "SESSION DATA"]

    def test_the_groups_do_not_overlap(self, settings_screen):
        screen, _ = settings_screen
        groups = {
            "cues": screen._cues_rect(),
            "levels": screen._levels_rect(),
            "fingers": screen._fingers_rect(),
            "ports": screen._ports_rect(),
            "data": screen._data_rect(),
        }
        names = list(groups)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                assert not groups[a].colliderect(groups[b]), \
                    f"{a} panel overlaps {b} panel"

    def test_the_groups_stay_on_screen(self, settings_screen):
        screen, _ = settings_screen
        w, h = screen.layout.width, screen.layout.height
        for rect in (screen._cues_rect(), screen._levels_rect(),
                     screen._fingers_rect(), screen._ports_rect(),
                     screen._data_rect()):
            assert rect.left >= 0 and rect.right <= w
            assert rect.top >= 0 and rect.bottom <= h

    def test_the_cue_pill_sits_in_the_cues_panel(self, settings_screen):
        screen, _ = settings_screen
        assert screen._cues_rect().contains(screen._cue_menu.rect)

    def test_the_sliders_sit_in_the_levels_panel(self, settings_screen):
        screen, _ = settings_screen
        panel = screen._levels_rect()
        for name, slider in screen._vol_sliders.items():
            assert panel.left <= slider.rect.left, name
            assert slider.rect.right <= panel.right, name

    def test_the_finger_tiles_sit_in_the_finger_panel(self, settings_screen):
        screen, _ = settings_screen
        panel = screen._fingers_rect()
        for ls in screen.lanes:
            assert panel.contains(ls.rect), f"lane {ls.lane} escapes"

    def test_the_port_controls_sit_in_the_ports_panel(self, settings_screen):
        screen, _ = settings_screen
        panel = screen._ports_rect()
        for dd in screen._port_dropdowns.values():
            assert panel.contains(dd.rect)
        for b in screen._panel_buttons:
            if b.label == "Open data folder":
                assert screen._data_rect().contains(b.rect)
            else:
                assert panel.contains(b.rect), b.label

    def test_the_sliders_do_not_reach_into_the_finger_tiles(
            self, settings_screen):
        """Slider hit rects are inflated vertically so the knob is easy
        to grab. That generosity must not extend over the tiles below,
        or a drag near the panel edge would buzz a finger."""
        screen, _ = settings_screen
        top = screen._fingers_rect().top
        for name, slider in screen._vol_sliders.items():
            hit = slider.rect.inflate(0, slider.KNOB_R * 2)
            assert hit.bottom < top, name

    def test_every_cue_switch_has_a_row(self, settings_screen):
        """Grouped by when the patient meets them, so the screen switch
        sits with the other two things that happen before the press
        rather than in a group of its own at the bottom."""
        screen, _ = settings_screen
        keys = [k for k, _l, _h in screen._cue_menu.rows if k is not None]
        assert keys == ["cue.buzz_before", "cue.sound_before",
                        "cue.show_target",
                        "cue.buzz_after", "cue.sound_after"]

    def test_shipped_defaults_are_the_before_press_cues(self):
        """Buzzer, sound and screen before the press; nothing after.
        A confirmation buzz on every correct press gets wearing, and it
        is not what the reaction-time comparison needs."""
        import yaml
        from pathlib import Path as _P
        # Relative to this file, not the working directory, so the test
        # passes wherever pytest is started from.
        root = _P(__file__).resolve().parents[1]
        cue = yaml.safe_load(
            (root / "config" / "default.yaml").read_text())["cue"]
        assert cue["buzz_before"] is True
        assert cue["sound_before"] is True
        assert cue["show_target"] is True
        assert cue["buzz_after"] is False
        assert cue["sound_after"] is False


class TestSettingsHitBoxes:
    def _click(self, screen, pos):
        import pygame
        for kind in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            screen.handle_event(pygame.event.Event(
                kind, {"button": 1, "pos": pos}))

    def test_the_cue_pill_opens_the_menu_where_it_is_drawn(
            self, settings_screen):
        screen, _ = settings_screen
        assert screen._cue_menu.is_open is False
        self._click(screen, screen._cue_menu.rect.center)
        assert screen._cue_menu.is_open is True

    def test_an_open_row_click_does_not_buzz_the_tile_underneath(
            self, settings_screen):
        """The open menu covers the finger tiles. Without the consume,
        toggling a cue would also fire a motor."""
        screen, _ = settings_screen
        buzzed: list[int] = []
        screen._buzz_finger = lambda ls: buzzed.append(ls.lane)
        menu = screen._cue_menu
        menu.is_open = True
        # Click where a row and a tile genuinely share pixels, not just
        # the centre of a row that happens to overlap by a few pixels at
        # its edge. Only a point inside both proves the row wins.
        shared = None
        for i, (key, _l, _h) in enumerate(menu.rows):
            if key is None:
                continue
            row = menu._row_rect(i)
            for ls in screen.lanes:
                overlap = row.clip(ls.rect)
                if overlap.width > 2 and overlap.height > 2:
                    shared = overlap
                    break
            if shared:
                break
        assert shared is not None, "the open menu is expected to cover a tile"
        assert any(ls.rect.collidepoint(shared.center) for ls in screen.lanes)
        self._click(screen, shared.center)
        assert buzzed == [], "the cue row click also buzzed a finger"
        assert menu.is_open is True, "a row click should leave the menu open"

    def test_a_tile_click_buzzes_that_tile_when_the_menu_is_shut(
            self, settings_screen):
        screen, _ = settings_screen
        buzzed: list[int] = []
        screen._buzz_finger = lambda ls: buzzed.append(ls.lane)
        target = screen.lanes[0]
        self._click(screen, target.rect.center)
        assert buzzed == [target.lane]

    def test_the_test_mode_pill_is_hit_where_it_was_drawn(
            self, settings_screen):
        """The pill's rect is measured from the rendered label during
        draw and cached for the hit test, so the two agree only if draw
        ran first. A click before any draw must not toggle anything."""
        import pygame
        screen, eng = settings_screen
        flipped: list[bool] = []
        screen._toggle_test_mode = lambda: flipped.append(True)
        assert screen._test_mode_rect.width == 0
        self._click(screen, (1200, 85))
        assert flipped == []

        screen.draw(pygame.Surface((1280, 800)))
        assert screen._test_mode_rect.width > 0
        self._click(screen, screen._test_mode_rect.center)
        assert flipped == [True]

    def test_the_lane_tiles_do_not_overlap_each_other(self, settings_screen):
        screen, _ = settings_screen
        for i, a in enumerate(screen.lanes):
            for b in screen.lanes[i + 1:]:
                assert not a.rect.colliderect(b.rect), \
                    f"lanes {a.lane} and {b.lane} overlap"

    def test_the_port_dropdown_rows_land_inside_the_screen(
            self, settings_screen):
        """The popup opens downward from the pill. With two rows near the
        bottom of the window its options could fall off the edge, where
        they are drawn but cannot be clicked."""
        screen, _ = settings_screen
        h = screen.layout.height
        for hand, dd in screen._port_dropdowns.items():
            last = dd._option_rect(len(dd.options) - 1)
            assert last.bottom <= h, f"{hand} dropdown runs off the bottom"

    def test_back_is_clickable(self, settings_screen):
        screen, eng = settings_screen
        went: list[str] = []
        screen.back_btn.on_click = lambda: went.append("title")
        self._click(screen, screen.back_btn.rect.center)
        assert went == ["title"]

    def test_the_status_line_starts_clear_of_the_back_button(
            self, settings_screen):
        screen, _ = settings_screen
        sx, _sy = screen._status_pos()
        assert sx > screen.back_btn.rect.right


class TestCuesOnTheResultsScreen:
    """Between two blocks is exactly when the cue condition gets
    changed: run one with the buzzer, run the next without, compare.
    Making that a trip back to the title screen and into Settings put
    four clicks between the researcher and the thing they came here to
    do, and the setting is recorded per trial anyway, so the two blocks
    stay separable afterwards."""

    def _results(self):
        import pygame
        from rehab.game.engine import GameEngine
        from rehab.config import Config
        from rehab.ui.theme import get as get_theme
        from rehab.ui.widgets import Layout
        from rehab.ui.screens import ResultsScreen
        pygame.init()
        pygame.font.init()
        pygame.display.set_mode((1280, 800))
        e = GameEngine.__new__(GameEngine)
        e.cfg = Config.load()
        e.theme = get_theme("clinical")
        e.layout = Layout(1280, 800, 1.0)
        e.hits, e.misses, e.score = 18, 6, 1200
        e.current_block, e.hand_mode = 1, "right"
        e.best_streak, e.per_lane_stats = 3, {}
        e.last_session_root = None
        e.session = type("S", (), {"participant": "T", "age": "60",
                                   "block_summary": {}})()
        e.stop_all_motors = lambda *a, **k: None
        return ResultsScreen(e), e

    def _click(self, screen, pos):
        import pygame
        for kind in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            screen.handle_event(pygame.event.Event(
                kind, {"button": 1, "pos": pos}))

    def test_the_menu_is_there(self):
        r, _ = self._results()
        keys = [k for k, _l, _h in r._cue_menu.rows if k]
        assert keys == ["cue.buzz_before", "cue.sound_before",
                        "cue.show_target",
                        "cue.buzz_after", "cue.sound_after"]

    def test_it_shares_one_definition_with_settings(self):
        """Two copies would drift, and a switch that means one thing on
        one screen and another elsewhere is worse than no switch."""
        from rehab.ui.screens import CUE_ROWS, DiagnosticsScreen
        r, _ = self._results()
        assert r._cue_menu.rows == list(CUE_ROWS)
        assert DiagnosticsScreen.CUE_ROWS is CUE_ROWS

    def test_toggling_changes_the_setting(self):
        r, e = self._results()
        self._click(r, r._cue_menu.rect.center)
        assert r._cue_menu.is_open
        idx = next(i for i, (k, _l, _h) in enumerate(r._cue_menu.rows)
                   if k == "cue.buzz_before")
        before = bool(e.cfg.get("cue.buzz_before"))
        self._click(r, r._cue_menu._row_rect(idx).center)
        assert bool(e.cfg.get("cue.buzz_before")) is not before

    def test_the_menu_stays_open_across_toggles(self):
        """Several switches usually get set in one visit."""
        r, _ = self._results()
        self._click(r, r._cue_menu.rect.center)
        idx = next(i for i, (k, _l, _h) in enumerate(r._cue_menu.rows) if k)
        self._click(r, r._cue_menu._row_rect(idx).center)
        assert r._cue_menu.is_open

    def test_it_opens_upward_and_stays_on_screen(self):
        """The pill sits low, so a list opening downward would run off
        the bottom and those rows could not be clicked at all."""
        r, _ = self._results()
        assert r._cue_menu.open_upwards
        rects = [r._cue_menu._row_rect(i)
                 for i in range(len(r._cue_menu.rows))]
        assert min(x.top for x in rects) >= 0
        assert max(x.bottom for x in rects) <= 800

    def test_an_open_menu_does_not_leak_clicks_to_the_buttons(self):
        """Its rows sit over the buttons when open. A click landing on
        both would flip a switch and start a block at once."""
        r, _ = self._results()
        fired = []
        r.again_btn.on_click = lambda: fired.append("again")
        self._click(r, r._cue_menu.rect.center)          # open it
        idx = next(i for i, (k, _l, _h) in enumerate(r._cue_menu.rows) if k)
        row = r._cue_menu._row_rect(idx)
        if row.colliderect(r.again_btn.rect):
            self._click(r, row.center)
            assert not fired, "click reached the button under the menu"

    def test_the_buttons_still_work_when_it_is_shut(self):
        r, _ = self._results()
        fired = []
        r.again_btn.on_click = lambda: fired.append("again")
        self._click(r, r.again_btn.rect.center)
        assert fired
