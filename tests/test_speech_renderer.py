"""Exercise cloud response decoding without credentials or network calls."""
import io
import sys
import wave
from types import SimpleNamespace
from scripts.render_syllables_speech import _render_cloud


def test_polly_pcm_becomes_valid_wav(tmp_path, monkeypatch):
    seen={}
    def render(**kwargs):
        seen.update(kwargs);return {'AudioStream':io.BytesIO(b'\x00\x00'*160)}
    monkeypatch.setitem(sys.modules,'boto3',SimpleNamespace(client=lambda name:SimpleNamespace(synthesize_speech=render)))
    path=tmp_path/'word.wav'
    assert _render_cloud('polly','apple',None,path,'Olivia')
    with wave.open(str(path)) as w:
        assert w.getnframes()==160
        assert w.getframerate()==16000
    assert seen['TextType']=='text'
    assert seen['Engine']=='neural'
