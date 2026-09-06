"""A silent playback failure must never be logged as delivered speech."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from finger_rehab.game.modes.syllables import SyllablesMode
from scripts.build_lab_package import make_source
import pytest


def test_failed_playback_records_failure_instead_of_speech(tmp_path):
    mode=SyllablesMode.__new__(SyllablesMode)
    mode.speech_backend='file';mode.speech_volume=1.;mode.word_hand='right'
    mode.speech_path=lambda stem:tmp_path/'word.ogg'
    raw=Mock();mode.engine=SimpleNamespace(audio=SimpleNamespace(play_speech=lambda *a,**k:False),raw_logger=raw)
    mode._speak('word','word')
    assert mode.speech_failures==1
    assert raw.queue_event.call_args.args[0]=='speech_failed'


def test_lab_rebuild_refuses_to_delete_psychopy_recordings(tmp_path):
    saved=tmp_path/'package/source/sessions/person/trials.csv'
    saved.parent.mkdir(parents=True);saved.write_text('recording')
    with pytest.raises(SystemExit,match='contains sessions'):
        make_source(tmp_path/'repo',tmp_path/'package')
    assert saved.read_text()=='recording'


def test_release_config_excludes_local_settings_and_calibration():
    import ast
    from pathlib import Path
    tree = ast.parse((Path(__file__).resolve().parents[1] / "finger_rehab.spec").read_text())
    assignment = next(n for n in tree.body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == "datas" for t in n.targets))
    entries = ast.literal_eval(assignment.value)
    config_sources = {src for src, dst in entries if dst == "config" or src.startswith("config")}
    assert config_sources == {"config/default.yaml", "config/eeg_lab.yaml",
                              "config/pattern_sequence_template.yaml"}
