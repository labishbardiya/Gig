# GIG Backend

Backend and phone prototype for our custom glasses. Created 2026-10-07.

**2026-10-08:** See [SCAN_WORKFLOW.md](SCAN_WORKFLOW.md) for the implemented phone
scan/review/private-save workflow, Drive authorization setup, measured local smoke
test and pending direct RTX deployment. The older backend scope below predates
that separate phone gateway. OpenClaw integration remains pending.

Research tooling: see [RESEARCH_CLIENT.md](RESEARCH_CLIENT.md) for the verified read-only Papers catalog client, source limitations and SOTA comparison workflow.

Phone-GIG Drive authorization and local semantic-memory setup: see
[DRIVE_AND_MEMORY_SETUP.md](DRIVE_AND_MEMORY_SETUP.md). These credentials remain
outside the repository and outside the public QR tunnel.

## Start

### Optional cloud chat and Fish Audio

GIG loads `C:\\Users\\lab\\Desktop\\gig\\.env` automatically. Add secrets only in
that local file; it is Git-ignored. Start by copying `.env.example` if `.env` does
not already exist, then fill in only the integrations you plan to use:

```dotenv
GIG_NVIDIA_API_KEY=your_nvidia_key
FISH_AUDIO_API_KEY=your_fish_audio_key
```

`GIG_NVIDIA_API_KEY` enables the optional **Kimi** selection in the phone UI.
`FISH_AUDIO_API_KEY` enables Fish Audio spoken replies. A missing or invalid key
does not affect the local Ollama chat path; the UI will report the unavailable
feature. Restart GIG after changing `.env`.

For a short, supervised public demonstration only, set `GIG_DEMO_NO_PAIRING=1`
when starting the phone server. This removes the six-digit pairing screen, which
means anyone who knows the public tunnel URL can use the demo. Do not enable it
for a persistent or sensitive deployment.

Double-click `run.command`, or run:

```sh
cd ~/Desktop/gig
./run.command
```

API documentation: http://127.0.0.1:8765/docs

On first startup a private bearer token is created in `data/api-token`. Read it locally and use the docs' **Authorize** button; never send it in chat or commit it. The server binds only to localhost. The launcher sets restrictive file creation permissions. Do not expose this development service to the internet.

Install/reproduce dependencies with `uv sync --frozen`; exact versions are in `uv.lock`. Run tests with `uv run pytest -q`.

## Implemented

- FastAPI and strict Pydantic schemas; authenticated routes.
- SQLite notes with explicit save consent, literal search and deletion.
- Local Ollama chat through a LangGraph node. Session retention is opt-in and limited to the latest 20 messages; session deletion supported.
- Model request timing, no silent cloud fallback, generic errors that do not expose provider bodies.
- CALL-E local call preparation, exact-payload approval, expiry after 10 minutes, idempotency keys, durable submission states, status/transcript retrieval and pre-submission cancellation.
- CALL-E skill CLI adapter, shell-free JSON invocation through the copied trusted launcher.
- Outgoing-call instructions require AI disclosure and include only supplied context and boundaries. Transcript/results are marked untrusted and never automatically executed as instructions.

## CALL-E safety and flow

`POST /v1/calls/prepare` creates a LOCAL proposal. It does not invoke the provider, contact anyone or use credits. Supply an explicit E.164 number, language, region, caller identity, objective, approved context, boundaries and a unique request key. Contact-name resolution is not implemented; numbers must not be guessed.

The response includes the exact payload and its SHA256 fingerprint. A human reviews both the context disclosure and the credit warning. `POST /v1/calls/{id}/approve` accepts the exact phrase `PLACE THIS CALL` and that fingerprint. Changed arguments require a new proposal and approval. The model chat endpoint has no permission to invoke this route.

Calls are disabled unless the operator deliberately starts the server with `GIG_ENABLE_LIVE_CALLS=1`. This switch alone is not per-call consent. The adapter checks authentication again, atomically claims the proposal and submits once. A network/CLI failure becomes `unknown`, never an automatic redial. A crash during submission becomes `unknown` on restart. Use the trusted CLI's private recovery mechanism for manual reconciliation; this backend does not automate recovery yet.

`POST /v1/calls/{id}/refresh` polls only an existing provider run ID and returns status, summary and transcript when available. Poll at most every 10 seconds. `finished` means the provider is terminal, NOT that the user's objective succeeded: inspect the provider status and evidence. No autonomous polling worker is implemented yet.

`POST /v1/calls/{id}/cancel` cancels only an unsubmitted proposal. It cannot hang up an active call. No hard provider-enforced time/credit ceiling is implemented; review this limitation before enabling live calls. Prompt boundaries are guidance, not a financial/legal enforcement mechanism. The caller must not be used for emergencies, undisclosed impersonation or unauthorised commitments.

`uv run python check_calle.py` verifies the trusted CLI/auth and required tools without calling anybody. It does not display tokens. The adapter currently defaults to this Mac's trusted CLI and Node paths; override `CALLE_PACKAGE_DIR` and `GIG_NODE` for another machine. Do not substitute arbitrary workspace packages. The vendored launcher was copied unchanged from the installed CALL-E skill.

## Main routes

| Route | Purpose |
| --- | --- |
| GET /health | Liveness and live-call switch state; not model readiness |
| POST /v1/sessions/{id}/chat | Local model conversation; optional explicit retention |
| DELETE /v1/sessions/{id} | Delete retained conversation |
| POST /v1/notes | Save with consent=true |
| GET /v1/notes?q= | Search notes |
| DELETE /v1/notes/{id} | Delete note |
| POST /v1/calls/prepare | Preview immutable call details locally |
| POST /v1/calls/{id}/approve | Human approval and gated one-time submission |
| GET /v1/calls/{id} | Read local call record |
| POST /v1/calls/{id}/refresh | Fetch known provider call state |
| POST /v1/calls/{id}/cancel | Cancel an unsubmitted proposal |

## Local model

Model installation is not verified. Set `GIG_MODEL` to an installed Ollama model before starting the server. `GIG_MODEL_URL` defaults to `http://127.0.0.1:11434`; it can point to an operator-configured HTTPS model gateway, or a loopback port forwarded through a private authenticated tunnel. Remote plain HTTP and URLs containing credentials are rejected. The model gateway must be private/access-controlled; this adapter does not add gateway authentication. Never expose raw Ollama publicly. Endpoint configuration is operator-only, not request input.

`GET /v1/readiness` requires the bearer token and checks model inventory without inference or downloads. Ready means installed, not GPU execution verified. This version does not yet stream tokens, ingest live audio/video or let the model automatically create tool proposals. HTTP tests use fixtures; real model execution needs a separate acceptance run. Use `.venv/bin/python -m pytest -q` if moving the folder broke executable shebang paths.

See [THREE_STAGE_DELIVERY.md](THREE_STAGE_DELIVERY.md) for scope and acceptance gates. [pc-preflight.ps1](pc-preflight.ps1) is a read-only inventory script for the remote Windows terminal, not an installer.

## Privacy and production boundaries

Single-user development backend: bearer authentication is not multi-user OAuth. Possession of the token permits approvals; keep it out of model context. CORS is not opened. Use OS disk encryption: the SQLite database is not application-encrypted. Call proposals, supplied context and provider results are retained locally in the action ledger. Live calls also disclose approved context to CALL-E and the recipient; the screenshot balance is not re-verified by this code. Notes/session deletion removes logical records, not forensic backups. Add configurable retention, call-record deletion, encryption/key management, credential revocation and rate limits before deployment. Avoid sensitive records in development.

LangGraph is presently used for the model node, NOT durable autonomous multi-step planning. The call ledger is the implemented durable state machine. Google APIs, PDF/OCR pipeline, research, audio, media privacy-switch ingestion and display output remain next work. This is an executable first backend slice, not the whole project.

## Next implementation slice

1. Model proposes typed tools -> policy layer -> human approval -> execution -> verification, without model access to approval credentials.
2. Document/PDF workflow and Drive/Calendar/email adapters with test accounts.
3. Audio/visual input, capture epochs, interruption and real latency testing.
4. Phone/glasses and later frontend adapters.

No calls were placed during development. Tests use a fake CALL-E provider. No GitHub push was performed.
