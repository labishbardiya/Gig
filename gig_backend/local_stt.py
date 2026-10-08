"""Small Pipecat adapter for faster-whisper without platform-specific MLX imports."""
import asyncio
import io
import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel
from pipecat.frames.frames import TranscriptionFrame, ErrorFrame
from pipecat.services.stt_service import SegmentedSTTService
from pipecat.services.settings import STTSettings
from pipecat.utils.time import time_now_iso8601


class LocalWhisperSTT(SegmentedSTTService):
    def __init__(self, model='base', device='cpu', compute_type='int8'):
        super().__init__(settings=STTSettings(model=model, language=None))
        self.engine = WhisperModel(model, device=device, compute_type=compute_type)

    def transcribe(self, audio):
        samples, sample_rate = sf.read(io.BytesIO(audio), dtype='float32')
        if sample_rate != 16000:
            import soxr
            samples = soxr.resample(samples, sample_rate, 16000)
        if samples.ndim > 1:
            samples = samples.mean(axis=1)
        if samples.size == 0 or np.max(np.abs(samples)) < 0.001:
            return ''
        segments, _ = self.engine.transcribe(samples, beam_size=1, condition_on_previous_text=False)
        # Consume the lazy generator in the worker thread, never on the audio event loop.
        return ' '.join(s.text.strip() for s in segments if s.no_speech_prob < 0.6).strip()

    async def run_stt(self, audio):
        try:
            await self.start_processing_metrics()
            text = await asyncio.to_thread(self.transcribe, audio)
            if text:
                yield TranscriptionFrame(text, '', time_now_iso8601())
        except Exception:
            yield ErrorFrame('Local speech recognition failed')
        finally:
            await self.stop_processing_metrics()
