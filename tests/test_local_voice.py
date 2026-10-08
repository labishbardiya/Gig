import httpx
import pytest
from fastapi import HTTPException
from gig_backend.speech import synthesize

def test_local_voice_wav(monkeypatch, tmp_path):
    monkeypatch.setenv('GIG_TTS_PROVIDER', 'chatterbox')
    wav = b'RIFF0000WAVEdata'
    def post(self, url, **kwargs):
        assert url == 'http://127.0.0.1:8768/tts'
        return httpx.Response(200, content=wav, request=httpx.Request('POST',url))
    monkeypatch.setattr(httpx.Client, 'post', post)
    assert synthesize('Hello', tmp_path) == wav

def test_local_voice_failure_never_cloud_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv('GIG_TTS_PROVIDER', 'chatterbox')
    def post(*args, **kwargs):
        raise httpx.ConnectError('offline')
    monkeypatch.setattr(httpx.Client, 'post', post)
    with pytest.raises(HTTPException) as error:
        synthesize('Hello', tmp_path)
    assert error.value.status_code == 503

def test_local_voice_length_limit(monkeypatch, tmp_path):
    monkeypatch.setenv('GIG_TTS_PROVIDER', 'chatterbox')
    with pytest.raises(HTTPException) as error:
        synthesize('a'*1001, tmp_path)
    assert error.value.status_code == 422
