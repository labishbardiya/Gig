# GIG live voice backend — validation build

This is an opt-in backend, not a claim that the entire GIG project is finished.

## Windows setup

Extract this package into `C:\Users\lab\GIG-Backend`. In PowerShell:

```powershell
cd C:\Users\lab\GIG-Backend
ollama pull qwen3:4b
uv sync --frozen --extra voice --python 3.13
uv run python setup_fish.py
powershell -ExecutionPolicy Bypass -File .\run_voice.ps1
```

Enter the Fish API key only at the hidden prompt. No keys are included in this package.
Keep Ollama running. The server listens on localhost port 8767. Do not expose Ollama directly.
The existing phone UI remains available, but its ordinary speech button is NOT yet wired
to the new WebRTC endpoints. Do not assume opening the UI enables live voice.

## Pipeline

Phone microphone → WebRTC → Silero voice activity and Pipecat turn handling →
local Whisper base (CPU int8) → Qwen3 4B via Ollama (RTX) → Fish streaming speech → WebRTC speaker.

Pipecat owns the conversation pipeline and interruption handling. Fish receives reply text;
speech recognition is local. This is not fully offline. Voice tools and camera context are not
connected in this pipeline; existing scan/save routes remain separate.

## API contract

Pair using the existing main app first. The session cookie authenticates all voice requests.
POST /voice/offer accepts {sdp, type: "offer"} and returns the WebRTC answer.
GET /voice/status reports session state. POST /voice/stop ends the session.
One active session is permitted, with a fifteen-minute limit. Client must stop microphone
tracks on hang-up and page exit. Browser must request echo cancellation and create an
audio transceiver before producing the offer. Camera capture is not requested.

## Network requirement

HTTPS is required on the phone for microphone permission. A private VPN or a properly
configured TURN relay is required when phone and PC cannot exchange WebRTC media directly.
An ngrok or VS Code HTTP tunnel alone is not a WebRTC media relay. This build supplies no
public STUN/TURN servers. Private network connectivity and firewall rules must be verified
before presenting the phone link as ready. Never disable the firewall globally.

## Verified and outstanding

Verified on the Mac: dependency installation, model load, route imports, existing 44 tests,
and a real Fish s2.1-pro-free WebSocket request returning PCM audio. That single test took
4.22 seconds from connection start to the first received audio message; it is NOT an
end-to-end phone or RTX latency measurement and is not yet the responsiveness target.

Outstanding: Windows installation, live phone client wiring, WebRTC network/audio test,
interruption test, multi-turn tests, tool integration, and measured end-of-utterance to
first-played-audio median/p95. ChatGPT-level naturalness has not been established.

Audio quality depends on the selected voice, reply style, segmentation and timing. This
backend cannot make a poor voice reference natural by transport changes alone.
