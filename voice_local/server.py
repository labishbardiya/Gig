"""Loopback-only Chatterbox audition service. Never expose this port publicly."""
import io
import os
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

model = None
gate = threading.Lock()

@asynccontextmanager
async def lifespan(app):
    global model
    import torch
    from chatterbox.tts_turbo import ChatterboxTurboTTS
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA unavailable. Install CUDA PyTorch; this launcher requires the RTX PC.')
    model = ChatterboxTurboTTS.from_pretrained(device='cuda')
    reference = os.getenv('GIG_VOICE_REFERENCE')
    if reference:
        model.prepare_conditionals(reference)
    if model.conds is None:
        raise RuntimeError('Set GIG_VOICE_REFERENCE to a permitted WAV recording longer than five seconds.')
    with torch.inference_mode():
        model.generate('Hello. I am ready.')
    torch.cuda.synchronize()
    yield
    model = None

app = FastAPI(lifespan=lifespan)

class Speech(BaseModel):
    text: str = Field(min_length=1, max_length=1000)

@app.get('/health')
def health():
    return {'ready': model is not None, 'provider':'chatterbox-turbo', 'streaming':False}

@app.post('/tts')
def speak(body: Speech):
    if not body.text.strip():
        raise HTTPException(422, 'Blank text')
    if model is None:
        raise HTTPException(503, 'Model unavailable')
    if not gate.acquire(blocking=False):
        raise HTTPException(429, 'Voice is busy')
    try:
        import torch
        import soundfile as sf
        torch.cuda.synchronize()
        started = time.perf_counter()
        torch.cuda.reset_peak_memory_stats()
        with torch.inference_mode():
            wav = model.generate(body.text)
        torch.cuda.synchronize()
        samples = wav.detach().float().cpu().numpy().reshape(-1)
        elapsed = time.perf_counter()-started
        output = io.BytesIO()
        sf.write(output, samples, model.sr, format='WAV', subtype='PCM_16')
        return Response(output.getvalue(), media_type='audio/wav', headers={
            'Cache-Control':'no-store', 'X-Synthesis-Seconds':str(elapsed),
            'X-Audio-Seconds':str(len(samples)/model.sr),
            'X-Peak-Allocated-MiB':str(torch.cuda.max_memory_allocated()/1048576)})
    except Exception:
        raise HTTPException(503, 'Local synthesis failed; check model/device availability')
    finally:
        gate.release()
