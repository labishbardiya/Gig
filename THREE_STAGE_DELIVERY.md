# GIG: three-stage software delivery

Updated 7 October 2026. Stages are acceptance gates, not three messages or a guarantee of universal task competence.

## Architecture

Glasses/pod captures permitted audio and selected frames, plays audio and displays cards.
PC hosts the agent, GPU inference, document processing, memory and tool workers.
Laptop is the development/control client, not a mandatory relay.
Orin is an optional measured worker, not worn and not a compulsory extra network hop.
Prefer private encrypted transport. Never publish an unauthenticated model server.
VS Code is a development access channel, not the production glasses transport.
Hardware capture-off must work independently; backend cancellation and buffer deletion complement it.

## 1. Distributed intelligence foundation — IN PROGRESS

Deliver authenticated backend/worker connectivity, model adapters, streaming and cancellation,
bounded jobs, session state, restart recovery, and timing instrumentation.
Measure Qwen3.5-4B versus Gemma 4 E4B quantized candidates on the actual PC; cap context and concurrency.
Typed tool proposals must pass deterministic policy before execution; models never receive approval credentials.
Keep provider runtimes isolated so incompatible ML packages do not share one environment.

Gate: real image/text requests run on PC GPU from the laptop; authenticated connections,
offline/timeout behavior and restart tests pass; record revision, quantization, context,
GPU allocation and p50/p95 timing. Mock tests are not this gate.

## 2. Complete agreed backend capabilities — PENDING

- Voice: VAD, ASR, contextual conversation, streamed TTS, interruption and captions.
- Visual conversation: selected timestamped frames, clarification questions, object detection only where useful.
- Documents: crop/rectify, OCR, searchable PDF, preview and approved Drive upload.
- Research: search, retrieve, citations and source-grounded responses; retrieved instructions remain untrusted.
- Memory: explicit save, provenance, correction, retrieval, export, deletion and retention.
- Work: Google OAuth adapters for Drive/calendar/email/tasks; scoped grants and previews for external writes.
- Computer use: isolated browser/desktop worker, restricted workspace, verified outcomes, no arbitrary shell tool.
- CALL-E: explicit recipient/context approval, AI disclosure, no automatic redial after uncertain submission.
- Display: concise cards, manual region magnification, consented-person labels if enrollment is supplied.
- Memory-support mode: opt-in reminders and recall, never presented as dementia treatment.

Gate: each flow passes fixtures AND a consented live account/device test. Credentials, remote
PC access and hardware protocol are dependencies; an unconfigured adapter is not a completed feature.

## 3. Client integration, hardening and release — PENDING

Build companion/frontend after backend contracts; integrate real pod/display/audio protocols.
Test hardware privacy events, stale-frame rejection, interruption, network loss, recovery,
duplicate actions, prompt injection, secret isolation, deletion and account revocation.
Package pinned dependencies, model manifests, deployment/runbooks and reproducible demo evidence.

Gate: all agreed scenarios pass end-to-end on target hardware; publish actual latency distributions
and failures. Report capture-to-transcript, first token, first audible response, full reply,
capture-to-caption and tool completion separately. Do not sum stage p95s as a measured end-to-end p95.
No numeric latency guarantee until measured. Training our own model remains a research track;
replacement requires evidence on these same tests, not inclusion just to claim novelty.

## Research shortlist (not a universal SOTA ranking)

- Qwen3.5-4B: image/text reasoning baseline; compact size is a hypothesis for our 12 GB GPU budget.
  https://huggingface.co/Qwen/Qwen3.5-4B
- Gemma 4 E4B: competing multimodal candidate. Compare visual grounding/tool reliability and memory use.
  https://huggingface.co/google/gemma-4-E4B-it
- Qwen3-ASR-0.6B: speech candidate; compare noisy English/Hindi/code-switch audio against faster-whisper.
  https://huggingface.co/Qwen/Qwen3-ASR-0.6B
- Qwen3-TTS 0.6B CustomVoice: voice candidate, not a Hindi-coverage assumption; compare first-audio latency.
  https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice
- PP-OCRv6: updated OCR candidate replacing v5 as the first comparison target; verify required scripts
  separately, especially Devanagari. Publisher benchmarks are not GIG measurements.
  https://github.com/PaddlePaddle/PaddleOCR
- LangGraph: stateful orchestration and checkpoints, not an intelligence model or safety boundary.
  Side effects still need an independent durable ledger and idempotency.
  https://docs.langchain.com/oss/python/langgraph/durable-execution

Selection scorecard: task correctness, visual grounding, valid tool arguments, Hindi/English quality,
license, p50/p95 latency, peak VRAM/RAM and recovery. Pin the winning artifacts after real tests.

## Current evidence and blockers

Existing backend: chat graph, consented notes, CALL-E proposal/approval ledger and research catalog CLI.
New slice: configurable Ollama origin and authenticated inventory readiness; remote cleartext rejected.
No model inference/GPU benchmark was completed in this session.
VS Code reported connection to tunnel+da-arvr-01 could not be established.
Aside browser daemon is unavailable. Restore remote access before PC deployment.
Papers catalog is discovery only; primary model cards/repos above validate candidates.
