# GIG software implementation and acceptance record

Updated 8 October 2026. This file separates running code, tested paths, and unconnected services. It is the implementation record for the phone prototype, not a claim that all final glasses features are complete.

## Current shape

Phone browser → paired FastAPI gateway → local Ollama for ordinary text/vision questions. Explicitly chosen Kimi uses NVIDIA cloud if an operator configures a valid key. Saved chats and user-authored memories live in SQLite. Scans have a separate review/save workflow. Speech replies use configured Fish Audio or the experimental local TTS server. The agent task panel queues a typed task, requires user approval, and calls an isolated OpenClaw Gateway through a server-side bearer token when enabled.

The OpenClaw Gateway is pinned to `2026.9.8` in `vendor/openclaw-runtime/package-lock.json`. Its operator API is never placed in browser code. `openclaw/openclaw.json` binds it to loopback, disables its control UI, and limits tool exposure. The app's own approval is at **task level**, not tool level. The supplied restricted policy is intentionally read-only. Drive, email, calendar, and computer actions are not enabled through this OpenClaw instance.

## What is tested

- 51 backend tests as of this record: pairing/auth, local and cloud selection, document validation/save, call ledger, persistent chats, explicit memory editing and search, task gate/rejection, interrupted-run recovery.
- Desktop and phone-size browser checks: pairing, live UI, multi-chat navigation, memory management, task-disabled state, text greeting, speech and motion toggles, no horizontal overflow.
- OpenClaw 2026.9.8 package installs and validates its config. Its authenticated loopback `/v1/models` endpoint returned `openclaw/gig`.
- OpenClaw model completion succeeded on this Mac: the isolated Gateway returned `GIG ready` from the local `qwen3:4b` model. Its first configuration failed from a 4k Ollama context while OpenClaw sent about 6.9k tokens. A 16k context and reduced bootstrap/skill injection fixed the completion path. One approved task through the full phone API completed in **30.1 seconds** and wrote two chat messages. This is a single warm local result, not a latency distribution or a PC measurement.
- The UI now includes chat title search, JSON export, explicit memory search/edit/delete and a per-task lifecycle timeline. The timeline records state transitions, not OpenClaw's internal tool calls.

## Gaps that prevent a 100% software claim

- No tested computer-use worker or safe per-tool approval/execution trace. The app cannot currently control the PC from the phone.
- No connected Google OAuth account, Drive upload acceptance, email, calendar or task provider acceptance on the target PC.
- The browser voice path uses browser speech recognition and synchronous TTS. The Pipecat/WebRTC path is opt-in and is not wired into this phone UI; conversational interruption and first-audio latency are not established end to end.
- Visual research with citations, long-horizon question clarification, semantic memory retrieval, person recognition, display overlay and physical privacy-switch events are not accepted on the target device.
- No complete network test from the Moto Edge 50 Fusion through the selected private tunnel to the RTX PC. No target-PC latency distribution, failure recovery, or power test.

## Bring up on the RTX PC

1. Install Node 26.1+ and `uv`; install Ollama and pull `qwen3:4b` plus the configured vision model. Use `nvidia-smi` and `ollama ps` to verify GPU placement. The 12 GB RTX 3060 is the target server; the Mac is a development stand-in.
2. In the project folder, run `uv sync --frozen --python 3.13` and `npm install --prefix vendor/openclaw-runtime --ignore-scripts --save-exact openclaw@2026.9.8`.
3. Run `uv run python run_harness.py`. This starts the two loopback services with one fresh private token and prints the phone app's local address. The pairing code is in `data/openclaw-state/phone/phone-pair-code`; do not transmit that file publicly.
4. Before making the phone URL reachable outside the PC, configure an authenticated private tunnel, verify both the paired phone flow and the OpenClaw model completion, then measure p50/p95 separately for model, first voice audio, full spoken reply, image question, scan and approved task completion. Do not expose raw Ollama or OpenClaw publicly.

## Why this design

The [NVIDIA NOOA technical report](https://arxiv.org/abs/2607.20709) identifies typed contracts, bounded tool results, explicit state and model-callable APIs as useful harness elements. GIG currently applies typed API inputs, bounded history/results, durable SQLite state and a separately approved run lifecycle. Pass-by-reference, code-as-action and adaptive loop engineering from that report are not implemented in GIG. The [NVIDIA technical article](https://developer.nvidia.com/blog/six-agent-harness-capabilities-for-higher-model-performance/) describes the same six ideas, but it does not establish GIG performance.

The [OpenClaw Gateway documentation](https://docs.openclaw.ai/gateway/openai-http-api) says its compatible HTTP endpoint grants operator-level authority. That is why the gateway is loopback only, the token stays server-side, and the initial tool policy is restricted. Its [tool policy](https://docs.openclaw.ai/gateway/config-tools/tool-policy) allows later capability expansion, but each additional action needs a tested boundary and actual account connection.
