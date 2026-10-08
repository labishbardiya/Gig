"""Server-side Fish TTS. No paid fallback; no text/audio retained on disk."""
import os
import time
from dataclasses import dataclass
from pathlib import Path
import httpx
from fastapi import HTTPException

VOICE = '77cb6d35c3b64dda804ad4df94d6008f'
MODEL = 's2.1-pro-free'


@dataclass(frozen=True)
class SynthesisResult:
    """Audio plus timing for one complete server-side TTS request.

    ``request_ms`` deliberately measures from the backend starting its call to
    receiving the whole audio response. It is *not* microphone-to-speaker
    latency: browser upload/download and audio playback are outside this
    process. Keeping that distinction explicit prevents misleading demo
    performance claims.
    """
    audio: bytes
    request_ms: float
    provider: str

def api_key(root):
    key = os.getenv('FISH_AUDIO_API_KEY', '').strip()
    if key:
        return key
    try:
        return (Path(root)/'fish-api-key').read_text().strip()
    except OSError:
        return ''

def synthesize_with_metrics(text, root):
    """Generate speech without persisting input or audio, with bounded output."""
    started = time.perf_counter()
    if os.getenv('GIG_TTS_PROVIDER', 'fish') == 'chatterbox':
        if len(text) > 1000:
            raise HTTPException(422, 'Local voice audition accepts up to 1000 characters.')
        try:
            with httpx.Client(timeout=120, trust_env=False) as client:
                response = client.post('http://127.0.0.1:8768/tts', json={'text':text})
                response.raise_for_status()
                audio = response.content
                if len(audio) > 8_000_000 or audio[:4] != b'RIFF' or audio[8:12] != b'WAVE':
                    raise HTTPException(502, 'Local voice returned an invalid WAV.')
                return SynthesisResult(audio, round((time.perf_counter() - started) * 1000, 1), 'chatterbox')
        except httpx.HTTPError:
            raise HTTPException(503, 'Local voice is unavailable. No cloud fallback was attempted.')
    key = api_key(root)
    if not key:
        raise HTTPException(503, 'Fish Audio is not connected. Add its API key privately on the server.')
    try:
        with httpx.Client(timeout=httpx.Timeout(40, connect=10), trust_env=False) as client:
            with client.stream('POST', 'https://api.fish.audio/v1/tts',
                headers={'Authorization': 'Bearer '+key, 'Content-Type':'application/json', 'model':MODEL},
                json={'text':text, 'reference_id':VOICE, 'format':'mp3'}) as response:
                if response.status_code in (401,403):
                    raise HTTPException(503, 'Fish Audio rejected the API key or voice access.')
                if response.status_code == 402:
                    raise HTTPException(503, 'Fish Audio free access is unavailable for this account. No paid fallback was attempted.')
                if response.status_code == 429:
                    raise HTTPException(429, 'Fish Audio is rate-limited. Please try again later.')
                response.raise_for_status()
                audio = bytearray()
                for chunk in response.iter_bytes():
                    audio.extend(chunk)
                    if len(audio) > 8_000_000:
                        raise HTTPException(502, 'Speech response exceeded the size limit.')
                if not audio or not (audio[:3] == b'ID3' or (len(audio)>1 and audio[0]==255 and audio[1]&224==224)):
                    raise HTTPException(502, 'Fish Audio returned an invalid MP3 response.')
                return SynthesisResult(bytes(audio), round((time.perf_counter() - started) * 1000, 1), 'fish')
    except httpx.TimeoutException:
        raise HTTPException(504, 'Speech generation timed out. Your text answer is still available.')
    except httpx.HTTPError:
        raise HTTPException(502, 'Fish Audio request failed. Your text answer is still available.')


def synthesize(text, root):
    """Backward-compatible convenience API for callers that only need audio."""
    return synthesize_with_metrics(text, root).audio
