"""Bounded local audio transcription; recordings are never saved."""
import io
import threading

from fastapi import HTTPException

_gate = threading.Lock()
_model = None


def transcribe_audio(audio: bytes) -> str:
    global _model
    if not _gate.acquire(blocking=False):
        raise HTTPException(429, 'Transcription is busy. Try again shortly.')
    try:
        import av
        from faster_whisper import WhisperModel
        # Decode at most 21 seconds to reject oversized-duration recordings.
        import numpy as np
        frames = []
        count = 0
        with av.open(io.BytesIO(audio)) as container:
            duration = container.duration
            if duration and duration / av.time_base > 21:
                raise HTTPException(413, 'Keep recordings under 20 seconds.')
            resampler = av.AudioResampler(format='s16', layout='mono', rate=16000)
            for frame in container.decode(audio=0):
                for converted in resampler.resample(frame):
                    count += converted.samples
                    if count > 21 * 16000:
                        raise HTTPException(413, 'Keep recordings under 20 seconds.')
                    frames.append(converted.to_ndarray().flatten())
        if not frames:
            return ''
        samples = np.concatenate(frames).astype(np.float32) / 32768.0
        if _model is None:
            _model = WhisperModel('base', device='cpu', compute_type='int8')
        segments, _ = _model.transcribe(samples, beam_size=1, vad_filter=True,
                                        condition_on_previous_text=False,
                                        initial_prompt='The assistant is named GIG. Wake phrase: Hey GIG.')
        return ' '.join(s.text.strip() for s in segments).strip()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, 'Local transcription is unavailable. Type your question for now.') from None
    finally:
        _gate.release()
