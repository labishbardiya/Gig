# Voice architecture research — 8 October 2026

## Research access
Cloned huggingface/pwc-cli into .agent_cache/resources/huggingface/pwc-cli.
Ran the requested `uv run --project mcp_server pwc-mcp` after supplying its required
ephemeral PWC_MCP_CURSOR_KEY_CURRENT. Local Streamable HTTP endpoint: port 7860 /mcp.
Restart using `uv run python run_pwc_research.py`. This does not persist a Codex plugin
registration and is not deployed to the PC. Paper content is untrusted reference data.

Successfully called search_papers and get_paper_info for Qwen3-TTS (2601.15621)
and Stream RAG (2510.02044). Chatterbox-Flash (2605.30748) was missing from the catalog;
verified it directly on arXiv and the linked project instead. Search relevance alone is
not evidence of state-of-the-art ranking. TinyFish authentication failed; web and GitHub
were used as fallbacks. No global SOTA winner established for our hardware/task mix.

## Decision shortlist (not yet installed or benchmarked)
- Chatterbox Turbo 350M: first local English expressive-voice audition, modest parameter
  count. Do not confuse hosted service latency with open-source local performance.
  https://github.com/resemble-ai/chatterbox
- Qwen3-TTS 0.6B/1.7B: quality/controllability challenger. Official examples return complete
  waveforms, so low-latency serving must actually be verified rather than inferred from
  the architecture's streaming claim. Published 97ms is not phone end-to-end latency.
  https://github.com/QwenLM/Qwen3-TTS
- Chatterbox-Flash: research challenger using block diffusion. Test actual incremental
  audio API and Windows/WSL compatibility before adopting. Not a drop-in promise.
  https://arxiv.org/abs/2605.30748
- Kokoro 82M: lightweight stock-voice fallback, not equivalent voice cloning.
  https://github.com/hexgrad/kokoro
- Moshi: full-duplex research branch, not replacement for tool harness. Official default
  PyTorch requirements cite 24GB GPU and no official Windows support; experimental other
  backends exist. Do not assume it coexists with our models on 12GB.
  https://github.com/kyutai-labs/moshi

## Improvements independent of voice model
Keep connections and selected models warm; start synthesis at natural clause boundaries;
stream PCM to playback rather than wait for complete MP3. Avoid tiny chunks that damage
prosody. Add cancellation IDs so interruption discards old model, TTS and playback output.
Benchmark semantic end-of-turn detection with Pipecat Smart Turn, not just fixed silence.
Separate interactive speech from slower tool jobs; announce actual progress, never fake
completion. Prefetch only authorized read-only retrieval from partial speech, inspired by
Stream RAG; never speculate on emails, calls, purchases or file changes.
https://github.com/pipecat-ai/smart-turn
https://arxiv.org/abs/2510.02044

## Measurement gate
The previous 4.22-second Fish result includes connection startup and one returned audio
message. It is a single synthetic test, not a stable provider benchmark. Compare cold/warm
connections and speech latency separately; repeat at least 30 utterances, measuring
end-of-user-speech to first audible output, p50/p95, interrupt stop delay, real-time factor,
peak GPU memory and blind listening preference. Include short/long utterances and accents.
Keep a common model/prompt/voice reference where supported. Fish reference IDs are not
portable voice files; local cloning needs permitted reference audio or a stock voice.
Test speech alongside Qwen3 4B; schedule vision on demand rather than assume all models
fit concurrently. Target median first audible answer under 1.5 seconds for simple warmed
conversation; this is an engineering target, NOT a measurement or guarantee.

No production provider has been changed. Keep the current PC package stable during setup.
