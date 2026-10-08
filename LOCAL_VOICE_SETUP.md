# Local voice audition on the RTX PC

This adds Chatterbox Turbo to the existing authenticated `/speech` route.
It does NOT replace Fish in the separate experimental WebRTC pipeline yet.
No automatic cloud fallback occurs. Leave the main app unchanged until auditioning.

1. Extract this package into a separate directory, for example C:\Users\lab\GIG-Local-Voice.
2. PowerShell in that directory: `powershell -ExecutionPolicy Bypass -File .\run_local_tts.ps1`
   This creates a separate Python 3.11 environment, downloads model weights and warms up.
   Requires Git, uv, internet for downloads and a CUDA-compatible NVIDIA driver.
   If the model requires a voice reference, set `$env:GIG_VOICE_REFERENCE='C:\path\voice.wav'`
   first, using a permitted recording longer than five seconds. Fish voice IDs do not transfer.
3. In a second terminal, same directory:
   `uv sync --frozen`
   `uv run python benchmark_voice.py --runs 30`
4. Listen to the WAVs in artifacts/voice-TIMESTAMP. Send results.csv and startup errors.
5. To try this voice through THIS copy of the ordinary phone app, set
   `$env:GIG_TTS_PROVIDER='chatterbox'` and run `powershell -ExecutionPolicy Bypass -File .\run_phone.ps1`.
   Stop a prior app occupying its port first; do not run two on the same port.
   Its phone link/tunnel must target that server. This does not update the existing Mac-hosted link.

The benchmark measures complete-segment generation, not streaming first audio. The phone
still receives a whole audio segment. Results are not comparable directly with Fish's previous
single first-message timing. No RTX result has yet been measured by the assistant.
Chatterbox is pinned to an inspected source commit, but transitive dependencies are not fully
locked; installation on Windows remains to be verified. GPU allocator metrics cover this TTS
process, not Ollama or driver usage. Run nvidia-smi to inspect total concurrent VRAM.
