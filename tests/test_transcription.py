import pytest
from fastapi import HTTPException
from gig_backend.transcription import transcribe_audio, _gate


def test_invalid_audio_returns_controlled_error():
    with pytest.raises(HTTPException) as error:
        transcribe_audio(b'not audio')
    assert error.value.status_code == 503
    assert not _gate.locked()


def test_concurrent_transcription_rejected():
    _gate.acquire()
    try:
        with pytest.raises(HTTPException) as error:
            transcribe_audio(b'audio')
        assert error.value.status_code == 429
    finally:
        _gate.release()
