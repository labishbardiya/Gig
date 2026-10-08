"""Opt-in, single-user WebRTC voice runtime. Imported only with --extra voice.

Uses upstream Pipecat processors, not a reimplementation of turn detection.
No shell, account actions, or persistent memory are granted to this voice pipeline.
"""
import asyncio
import os
import time
from typing import Literal

from fastapi import HTTPException, Request
from pydantic import BaseModel, Field
from gig_backend.speech import api_key, fish_model, fish_voice


class Offer(BaseModel):
    sdp: str = Field(min_length=20, max_length=100_000)
    type: Literal['offer']


VOICE_PROMPT = '''You are GIG, an AI assistant having a spoken conversation.
Speak naturally and directly, usually in one or two short sentences. Use contractions.
Do not output Markdown, bullets, emojis, stage directions, or internal deliberation.
Ask one brief clarifying question when needed. Never invent what you can see.
This live voice channel currently has no camera, file-saving tools or account actions.
For scanning or saving, direct the user to the scan controls in the main GIG app.
Never claim an action succeeded. Do not pretend to be human. /no_think'''


def install_live_voice(app, authenticate, root):
    # Fail clearly at opt-in startup if the required extras are absent.
    from loguru import logger
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.worker import PipelineWorker, PipelineParams, ProcessorUnusablePolicy
    from pipecat.workers.runner import WorkerRunner
    from pipecat.processors.aggregators.llm_context import LLMContext
    from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair, LLMUserAggregatorParams
    from gig_backend.local_stt import LocalWhisperSTT
    from pipecat.services.ollama.llm import OLLamaLLMService
    from pipecat.services.fish.tts import FishAudioTTSService
    from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
    from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
    from pipecat.transports.base_transport import TransportParams

    # Upstream debug logs can contain transcripts; disable its default output.
    logger.remove()
    state = {'owner': None, 'connection': None, 'task': None, 'error': None,
             'phase': 'idle', 'started': None, 'runner': None}
    gate = asyncio.Lock()

    async def stop():
        runner = state['runner']
        connection = state['connection']
        task = state['task']
        if runner:
            await runner.cancel()
        if connection:
            await connection.disconnect()
        if task and not task.done() and task is not asyncio.current_task():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        state.update(owner=None, connection=None, task=None, runner=None, phase='idle')

    def check_origin(request):
        origin = request.headers.get('origin')
        if origin and origin.rstrip('/') != str(request.base_url).rstrip('/'):
            raise HTTPException(403, 'Cross-origin voice requests are not accepted')

    async def run(connection, stt):
        try:
            transport = SmallWebRTCTransport(webrtc_connection=connection,
                params=TransportParams(audio_in_enabled=True, audio_out_enabled=True))
            llm = OLLamaLLMService(base_url='http://127.0.0.1:11434/v1',
                settings=OLLamaLLMService.Settings(model=os.getenv('GIG_MODEL', 'qwen3:4b'),
                    max_tokens=256, extra={'extra_body': {'think': False}}))
            tts = FishAudioTTSService(api_key=api_key(root), output_format='pcm',
                settings=FishAudioTTSService.Settings(model=fish_model(), voice=fish_voice()))
            context = LLMContext([{'role':'system','content':VOICE_PROMPT}])
            user, assistant = LLMContextAggregatorPair(context,
                user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()))
            pipeline = Pipeline([transport.input(), stt, user, llm, tts, transport.output(), assistant])
            worker = PipelineWorker(pipeline, params=PipelineParams(enable_metrics=True),
                processor_unusable_policy=ProcessorUnusablePolicy.END)
            runner = WorkerRunner(handle_sigint=False)
            state['runner'] = runner
            await runner.add_workers(worker)

            @transport.event_handler('on_client_connected')
            async def connected(*_):
                state['phase'] = 'listening'

            @transport.event_handler('on_client_disconnected')
            async def disconnected(*_):
                await runner.cancel()

            # Maximum session bounds memory and unattended capture.
            await asyncio.wait_for(runner.run(), timeout=15*60)
        except asyncio.CancelledError:
            raise
        except Exception:
            state['error'] = 'Voice session ended. Check model/service availability; no automatic paid fallback.'
        finally:
            state['phase'] = 'ended'
            await connection.disconnect()

    @app.get('/voice/status')
    async def status(request: Request):
        owner = authenticate(request)
        if state['owner'] is not None and state['owner'] is not owner:
            return {'phase':'busy', 'error':None}
        return {'phase':state['phase'], 'error':state['error'],
                'tts':'Fish Audio '+fish_model(), 'stt':os.getenv('GIG_STT_MODEL','base'),
                'stt_device':os.getenv('GIG_STT_DEVICE','cpu'),
                'session_limit_minutes':15, 'tools_enabled':False}

    @app.post('/voice/offer')
    async def offer(body: Offer, request: Request):
        check_origin(request)
        owner = authenticate(request)
        if not api_key(root):
            raise HTTPException(503,'Configure Fish Audio on this PC first using setup_fish.py')
        async with gate:
            if state['task'] and not state['task'].done():
                raise HTTPException(409,'A voice session is already active. End it before starting another.')
            await stop()
            state.update(owner=owner, phase='loading', error=None, started=time.monotonic())
            try:
                # CPU int8 avoids CUDA/cuDNN DLL installation initially; GPU LLM still uses RTX.
                stt = await asyncio.to_thread(LocalWhisperSTT,
                    device=os.getenv('GIG_STT_DEVICE','cpu'),
                    compute_type=os.getenv('GIG_STT_COMPUTE','int8'),
                    model=os.getenv('GIG_STT_MODEL','base'))
                connection = SmallWebRTCConnection(ice_servers=[], connection_timeout_secs=30)
                state['connection'] = connection
                await connection.initialize(sdp=body.sdp, type=body.type)
                state['task'] = asyncio.create_task(run(connection, stt))
                return connection.get_answer()
            except Exception:
                await stop()
                raise HTTPException(503,'Voice startup failed. Run the voice preflight on the PC.')

    @app.post('/voice/stop')
    async def stop_session(request: Request):
        check_origin(request)
        owner = authenticate(request)
        async with gate:
            if state['owner'] is not None and state['owner'] is not owner:
                raise HTTPException(403,'This session belongs to another paired device')
            await stop()
        return {'stopped':True}

    from contextlib import asynccontextmanager
    previous_lifespan = app.router.lifespan_context
    @asynccontextmanager
    async def lifespan(application):
        async with previous_lifespan(application):
            try:
                yield
            finally:
                await stop()
    app.router.lifespan_context = lifespan
