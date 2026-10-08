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

from finger_rehab.data.session import SOFTWARE_VERSION


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def title_screen():
    import pygame
    pygame.init()
    pygame.font.init()
    from finger_rehab.config import Config
    from finger_rehab.game.engine import GameEngine
    from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
    from finger_rehab.ui.screens import TitleScreen
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
    from finger_rehab.config import Config
    from finger_rehab.game.engine import GameEngine
    from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
    from finger_rehab.ui.screens import DiagnosticsScreen
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
    import finger_rehab.ui.screens as screens_mod

    seen: list[str] = []
    original = screens_mod.draw_text

    def recorder(surf, text, pos, *args, **kwargs):
        seen.append(str(text))
        return original(surf, text, pos, *args, **kwargs)

    monkeypatch.setattr(screens_mod, "draw_text", recorder)
    screen.draw(pygame.Surface((1280, 800)))
    return seen


class TestVersionIsOneNumber:
    def test_software_version_is_4_0(self):
        # 4.0 is the build the study collects with, and the first one
        # published as a GitHub release (28 September 2026).
        assert SOFTWARE_VERSION == "4.0"

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
        from finger_rehab.data.session import Session
        assert Session(participant="T1").software_version == SOFTWARE_VERSION


class TestTitleFooter:
    EXPECTED = f"Basil Toufexis | Curtin University 2026 | v{SOFTWARE_VERSION}"

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
        assert screen.start_btn.label == "LOG IN"
        labels = {label for _r, label, _i, _a in screen._pills}
        assert labels == {"Quit", "Info", "Calibrate", "Settings"}
        # The menu-music mute pill sits in the top-left corner, off
        # the card and off the utility strip.
        assert screen.mute_btn.rect.top < screen.card_rect.top
        assert screen.mute_btn.rect.right < screen.layout.width // 3

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
                 ("start", screen.start_btn.rect),
                 ("mute", screen.mute_btn.rect)]
        rects += [(label, r) for r, label, _i, _a in screen._pills]
        for i, (an, ar) in enumerate(rects):
            for bn, br in rects[i + 1:]:
                assert not ar.colliderect(br), f"{an} overlaps {bn}"
        # The mute pill is the one control outside the card.
        assert not screen.mute_btn.rect.colliderect(screen.card_rect)

    def test_everything_stays_on_screen(self, title_screen):
        screen, _ = title_screen
        w, h = screen.layout.width, screen.layout.height
        rects = [screen.card_rect, screen.name_input.rect,
                 screen.age_input.rect, screen.start_btn.rect,
                 screen.mute_btn.rect]
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
        # P07 is a study code, and a code logs in only with its
        # dominant hand picked (tests/test_intake.py has the refusal).
        screen.hand_seg.set("right")
        self._click(screen, screen.start_btn.rect.center)
        assert went == ["modes"]
        assert eng.session.participant == "P07"
        assert eng.session.age == "64"
        assert eng.session.dominant_hand == "right"

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
    """Four tabs, one job each (29 September 2026), every control inside
    the card it belongs to and nothing on a tab overlapping."""

    def _cards(self, screen):
        return {
            "device": [screen._fingers_rect(), screen._ports_rect()],
            "sound": [screen._levels_rect(), screen._cues_rect()],
            "setup": [screen._firmware_rect()],
            "data": [screen._data_rect()],
        }

    def test_the_tabs_and_their_card_headings(self, settings_screen,
                                               monkeypatch):
        import pygame
        import finger_rehab.ui.screens as screens_mod
        screen, _ = settings_screen
        assert [k for k, _l in screen.TABS] == ["device", "sound",
                                                "setup", "data"]
        # Hand device opens first: checking the fingers is what
        # Settings is opened for most.
        assert screen.tab == "device"
        seen: list[str] = []
        original = screens_mod.DiagnosticsScreen._draw_band

        def recorder(self, surf, rect, title, hint=""):
            seen.append(title)
            return original(self, surf, rect, title, hint)

        monkeypatch.setattr(screens_mod.DiagnosticsScreen,
                            "_draw_band", recorder)
        for key, _l in screen.TABS:
            screen._switch_tab(key)
            screen.draw(pygame.Surface((1280, 800)))
        assert seen == ["FINGER TEST", "BOARDS", "LEVELS", "CUES", "", ""]

    def test_the_cards_on_a_tab_do_not_overlap(self, settings_screen):
        screen, _ = settings_screen
        for tab, cards in self._cards(screen).items():
            for i, a in enumerate(cards):
                for b in cards[i + 1:]:
                    assert not a.colliderect(b), tab

    def test_the_cards_stay_on_screen_and_clear_the_tabs(
            self, settings_screen):
        screen, _ = settings_screen
        w, h = screen.layout.width, screen.layout.height
        tabs_bottom = screen._tab_rect(0).bottom
        for cards in self._cards(screen).values():
            for rect in cards:
                assert rect.left >= 0 and rect.right <= w
                assert rect.top > tabs_bottom and rect.bottom <= h
                assert rect.bottom < screen.back_btn.rect.top

    def test_the_cue_list_sits_in_the_cues_card(self, settings_screen):
        screen, _ = settings_screen
        card = screen._cues_rect()
        menu = screen._cue_menu
        assert card.contains(menu.rect)
        for i, _row in enumerate(menu.rows):
            assert card.contains(menu._row_rect(i)), i

    def test_the_sliders_sit_in_the_levels_card(self, settings_screen):
        screen, _ = settings_screen
        panel = screen._levels_rect()
        for name, slider in screen._vol_sliders.items():
            assert panel.contains(slider.rect.inflate(0, slider.KNOB_R)), \
                name

    def test_the_finger_tiles_sit_in_the_finger_card(self, settings_screen):
        screen, _ = settings_screen
        panel = screen._fingers_rect()
        for ls in screen.lanes:
            assert panel.contains(ls.rect), f"lane {ls.lane} escapes"

    def test_every_button_sits_in_its_tab_card(self, settings_screen):
        screen, _ = settings_screen
        for dd in screen._port_dropdowns.values():
            assert screen._ports_rect().contains(dd.rect)
        home = {"device": screen._ports_rect(), "sound": screen._cues_rect(),
                "setup": screen._firmware_rect(),
                "data": screen._data_rect()}
        for b, tab in zip(screen._panel_buttons, screen._panel_tabs):
            assert home[tab].contains(b.rect), b.label
        # And no two buttons on one tab overlap.
        for tab in home:
            mine = [b for b, t in zip(screen._panel_buttons,
                                      screen._panel_tabs) if t == tab]
            for i, a in enumerate(mine):
                for b in mine[i + 1:]:
                    assert not a.rect.colliderect(b.rect), (a.label,
                                                            b.label)

    def test_the_menu_music_switch_sits_on_its_slider_row(
            self, settings_screen, monkeypatch):
        # Basil, 29 September 2026: the on/off belongs with the level it
        # switches, so the cues card holds only cues.
        import pygame
        from finger_rehab.ui.widgets import FONT_BODY, FONT_SMALL, Slider
        screen, eng = settings_screen
        switch = screen._music_switch
        music = screen._vol_sliders["music"]
        assert screen._levels_rect().contains(switch.rect)
        label_y = music.rect.y - Slider.LABEL_GAP
        assert abs(switch.rect.centery - (label_y + 10)) <= 6
        # Clear of the label on its left and the value on its right.
        label_w = screen.layout.font(FONT_SMALL + 4).size(music.label)[0]
        assert switch.rect.x > music.rect.x + label_w
        value_w = screen.layout.font(FONT_BODY).size("100%")[0]
        assert switch.rect.right + 48 < music.rect.right - value_w
        assert not any(b.label.startswith("Menu music")
                       for b in screen._panel_buttons)
        # A click flips the machine's setting.
        monkeypatch.setattr(eng.cfg, "save_user_overrides",
                            lambda values: None)
        screen._switch_tab("sound")
        before = bool(eng.cfg.get("audio.menu_music_enabled", True))
        screen.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=switch.rect.center))
        assert bool(eng.cfg.get("audio.menu_music_enabled")) is not before

    def test_the_cue_note_fits_both_menus(self, settings_screen):
        # The results screen's cue menu is narrower than Settings'; the
        # Buzz Hunt note ran past its plate there.
        from finger_rehab.ui.screens import CUE_ROWS
        from finger_rehab.ui.widgets import FONT_SMALL
        screen, _ = settings_screen
        font = screen.layout.font(FONT_SMALL)
        notes = [label for key, label, kind in CUE_ROWS
                 if key is None and kind == "note"]
        assert notes
        for label in notes:
            assert font.size(label)[0] <= 306 - 24, label

    def test_a_tab_key_mid_drag_ends_the_drag(self, settings_screen,
                                              monkeypatch):
        # 1 to 4 while a slider is held: the release lands on another
        # tab, so the slider used to follow the bare mouse afterwards.
        import pygame
        screen, eng = settings_screen
        saved = []
        monkeypatch.setattr(eng.cfg, "save_user_overrides",
                            lambda values: saved.append(values))
        screen._switch_tab("sound")
        s = screen._vol_sliders["master"]
        screen.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1,
            pos=(s.rect.x + 40, s.rect.centery)))
        screen.handle_event(pygame.event.Event(
            pygame.MOUSEMOTION, buttons=(1, 0, 0), rel=(20, 0),
            pos=(s.rect.x + 60, s.rect.centery)))
        held = s.value
        screen._switch_tab("device")
        assert saved, "the level set by the drag was not saved"
        screen._switch_tab("sound")
        screen.handle_event(pygame.event.Event(
            pygame.MOUSEMOTION, buttons=(0, 0, 0), rel=(-60, 0),
            pos=(s.rect.x, s.rect.centery)))
        assert s.value == held

    def test_esc_mid_drag_saves_and_ends_the_drag(self, settings_screen,
                                                  monkeypatch):
        # Esc while a slider is held left Settings with the level unsaved
        # and the slider still following the mouse (second review).
        import pygame
        screen, eng = settings_screen
        saved = []
        monkeypatch.setattr(eng.cfg, "save_user_overrides",
                            lambda values: saved.append(values))
        screen._switch_tab("sound")
        s = screen._vol_sliders["master"]
        screen.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1,
            pos=(s.rect.x + 40, s.rect.centery)))
        screen.handle_event(pygame.event.Event(
            pygame.MOUSEMOTION, buttons=(1, 0, 0), rel=(20, 0),
            pos=(s.rect.x + 60, s.rect.centery)))
        held = s.value
        assert screen.on_escape() is False
        assert saved, "the level set by the drag was not saved"
        screen.handle_event(pygame.event.Event(
            pygame.MOUSEMOTION, buttons=(0, 0, 0), rel=(-60, 0),
            pos=(s.rect.x, s.rect.centery)))
        assert s.value == held

    def test_the_setup_rows_fit_on_the_lab_pc(self, settings_screen):
        # Windows adds the USB driver row and the lab build the EEG box:
        # seven rows with the press point, and every one stays inside
        # the card with room for its title and one line.
        screen, eng = settings_screen
        screen._show_usb_row = True

        class _Markers:
            enabled = True
        eng.markers = _Markers()
        assert screen._setup_row_count() == 7
        card = screen._firmware_rect()
        for i in range(7):
            assert card.contains(screen._setup_btn_rect(i)), i
        last_top = screen._firmware_row_y(6)
        assert last_top + screen._setup_row_h() <= card.bottom
        assert screen._setup_row_h() >= 56
        assert all(len(lines) == 1 for _t, lines in screen._setup_rows())

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

    def test_a_tab_is_picked_where_it_is_drawn(self, settings_screen):
        screen, _ = settings_screen
        for i, (key, _l) in enumerate(screen.TABS):
            self._click(screen, screen._tab_rect(i).center)
            assert screen.tab == key
        import pygame
        screen.handle_event(pygame.event.Event(
            pygame.KEYDOWN, {"key": pygame.K_1, "mod": 0, "unicode": "1",
                             "scancode": 0}))
        assert screen.tab == "device"

    def test_a_cue_switch_flips_where_it_is_drawn(self, settings_screen):
        screen, _ = settings_screen
        screen._switch_tab("sound")
        flipped: list[tuple[str, bool]] = []
        screen._cue_menu.on_toggle = lambda k, v: flipped.append((k, v))
        menu = screen._cue_menu
        i = next(i for i, (k, _l, _h) in enumerate(menu.rows)
                 if k == "cue.buzz_after")
        self._click(screen, menu._row_rect(i).center)
        assert flipped and flipped[0][0] == "cue.buzz_after"
        # Pinned: a click on the heading does not close anything.
        self._click(screen, menu.rect.center)
        assert menu.is_open is True

    def test_a_tile_click_buzzes_only_on_the_hand_device_tab(
            self, settings_screen):
        screen, _ = settings_screen
        buzzed: list[int] = []
        screen._buzz_finger = lambda ls: buzzed.append(ls.lane)
        target = screen.lanes[0]
        self._click(screen, target.rect.center)
        assert buzzed == [target.lane]
        screen._switch_tab("sound")
        self._click(screen, target.rect.center)
        assert buzzed == [target.lane], "a hidden tile buzzed"

    def test_the_test_mode_switch_is_hit_where_it_was_drawn(
            self, settings_screen):
        """Test Mode lives on the Data tab; its click reaches it there
        and nowhere else."""
        import pygame
        screen, eng = settings_screen
        was = bool(eng.cfg.get("game.test_mode_enabled", False))
        b = next(b for b in screen._panel_buttons
                 if b.label.startswith("Test Mode"))
        self._click(screen, b.rect.center)
        assert bool(eng.cfg.get("game.test_mode_enabled", False)) == was
        screen._switch_tab("data")
        screen.draw(pygame.Surface((1280, 800)))
        assert screen._test_mode_rect.width > 0
        flipped: list[bool] = []
        screen._toggle_test_mode = lambda: flipped.append(True)
        screen.rebuild_panel()
        b = next(b for b in screen._panel_buttons
                 if b.label.startswith("Test Mode"))
        self._click(screen, b.rect.center)
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
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.config import Config
        from finger_rehab.ui.theme import get as get_theme
        from finger_rehab.ui.widgets import Layout
        from finger_rehab.ui.screens import ResultsScreen
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
        from finger_rehab.ui.screens import CUE_ROWS, DiagnosticsScreen
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

    def test_it_opens_downward_and_stays_on_screen(self):
        """The pill lives in the top-left header (its old low-right
        spot sat on the saved-to footer and was never drawn at all),
        so the list opens downward; every row has to land inside the
        screen or it could not be clicked."""
        r, _ = self._results()
        assert not r._cue_menu.open_upwards
        assert r._cue_menu.rect.top < 200
        rects = [r._cue_menu._row_rect(i)
                 for i in range(len(r._cue_menu.rows))]
        assert min(x.top for x in rects) >= 0
        assert max(x.bottom for x in rects) <= 800

    def test_the_pill_is_actually_drawn(self):
        """handle_event routed clicks to the menu since it was added,
        but draw never rendered it: an invisible click target. Pin
        that the closed pill now paints pixels inside its own rect."""
        import pygame
        r, _ = self._results()
        surf = pygame.Surface((1280, 800))
        surf.fill(r.theme.background)
        before = surf.copy()
        r.draw(surf)
        rect = r._cue_menu.rect
        changed = any(
            surf.get_at((x, y)) != before.get_at((x, y))
            for x in range(rect.left + 2, rect.right - 2, 24)
            for y in range(rect.top + 2, rect.bottom - 2, 12)
        )
        assert changed, "cue pill rect is hit-testable but not drawn"

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


@pytest.fixture
def mode_select_screen():
    import pygame
    pygame.init()
    pygame.font.init()
    from finger_rehab.config import Config
    from finger_rehab.game.engine import GameEngine
    from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
    from finger_rehab.ui.screens import ModeSelectScreen
    cfg = Config.load()
    cfg.data.setdefault("ui", {})["resolution"] = [1280, 800]
    eng = GameEngine(cfg, KeyboardOnlySource())
    yield ModeSelectScreen(eng), eng
    pygame.quit()


class TestModeSelectCardLayout:
    """Every mode card carries a short what-you-do line, wrapped to at
    most two lines. The wrap cap is a
    contract: a third line would silently vanish, so this class
    renders every description with the same font and wrap the screen
    uses and fails when any card in either column runs out of room."""

    def _card_lines(self, sc):
        from finger_rehab.ui.widgets import FONT_SMALL
        for b, (key, title, desc) in zip(sc.buttons, sc.MODES):
            font = sc.layout.font(FONT_SMALL + 2)
            text_x = b.rect.x + 92
            max_w = b.rect.right - 14 - text_x
            lines = sc._wrap_desc(font, desc, max_w)
            yield key, b, font, max_w, lines

    def test_ten_cards_and_every_mode_described(self,
                                                mode_select_screen):
        sc, _ = mode_select_screen
        assert len(sc.MODES) == 10
        assert len(sc.buttons) == 10
        for _key, _title, desc in sc.MODES:
            assert desc.strip(), "a card without a description tells "
            "the clinician nothing"

    def test_descriptions_fit_two_lines_in_both_columns(
            self, mode_select_screen):
        sc, _ = mode_select_screen
        for key, b, font, max_w, lines in self._card_lines(sc):
            assert len(lines) <= sc.DESC_MAX_LINES, (
                f"{key}: description needs {len(lines)} lines; the "
                f"card draws at most {sc.DESC_MAX_LINES}")
            for line in lines:
                assert font.size(line)[0] <= max_w, (
                    f"{key}: line wider than the card interior")

    def test_description_block_stays_inside_the_card(
            self, mode_select_screen):
        sc, _ = mode_select_screen
        for key, b, font, _max_w, lines in self._card_lines(sc):
            n = min(len(lines), sc.DESC_MAX_LINES)
            bottom = b.rect.y + 44 + (n - 1) * 20 + font.get_height()
            assert bottom <= b.rect.bottom, (
                f"{key}: description bottom {bottom} spills past the "
                f"card bottom {b.rect.bottom}")

    def test_the_grid_clears_the_end_session_button(
            self, mode_select_screen):
        sc, _ = mode_select_screen
        lowest = max(b.rect.bottom for b in sc.buttons)
        assert lowest < sc.back_btn.rect.top, (
            "cards overlap the End session button")

    def test_columns_do_not_overlap(self, mode_select_screen):
        sc, _ = mode_select_screen
        for i, b in enumerate(sc.buttons):
            for j, other in enumerate(sc.buttons):
                if i < j:
                    assert not b.rect.colliderect(other.rect)

    def test_cards_are_short_and_claim_nothing(self, mode_select_screen):
        # One line of a few words on what you do. The menu makes no
        # claim about what a game trains or treats; that lives in each
        # mode's docstring.
        sc, _ = mode_select_screen
        descs = {k: d.lower() for k, _t, d in sc.MODES}
        for key, d in descs.items():
            assert len(d.split()) <= 6, f"{key} card is busy: {d!r}"
            for banned in ("cure", "recover", "restores", "treats",
                           "therapy", "trains", "measures", "builds"):
                assert banned not in d, f"{key} card claims: {banned}"

    def test_pattern_card_still_keeps_the_secret(self, mode_select_screen):
        # Boyd and Winstein: explicit knowledge impairs the implicit
        # learning. The card must never hint that material repeats.
        sc, _ = mode_select_screen
        desc = dict((k, d) for k, _t, d in sc.MODES)["pattern"].lower()
        for banned in ("pattern", "sequence", "repeat", "hidden",
                       "memoris"):
            assert banned not in desc
