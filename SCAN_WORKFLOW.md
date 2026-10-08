# GIG: identify, scan, save — implementation checkpoint

## Phone app

Existing lightweight HTML/CSS/JavaScript app, served by the same FastAPI backend.
Camera preview; Identify & tell; scan review; editable extracted text; format and
destination controls; saved-file downloads and local deletion; voice/text input;
model choice; software privacy button. No separate frontend build/runtime is needed.
Browser speech recognition is a temporary dependency that may use an online service;
it is not guaranteed offline or always listening. Speech output uses browser TTS.

## Connection target

Phone Chrome -> private HTTPS on the RTX PC -> FastAPI document tools/local Ollama.
Use Tailscale on both devices and Tailscale Serve, NOT public Funnel. Devices must
be authorized in the same tailnet with access limited to this app. Tailscale can
use a direct encrypted peer connection or an encrypted relay when NAT blocks it;
measure the actual route/latency. The VS Code tunnel is for development, not the
phone's permanent camera transport. No raw Ollama port should be public.

On the Windows PC after transferring code (excluding .venv, data, caches and credentials),
install Python/uv if missing, then from the project directory:

```powershell
uv sync --frozen
$env:GIG_MODEL = 'qwen3:4b'
$env:GIG_VISION_MODEL = 'qwen2.5vl:3b'
uv run python -m uvicorn gig_backend.phone:create_phone_app --factory --host 127.0.0.1 --port 8767 --no-access-log
```

These are the installed Mac smoke-test models, not a final RTX quality selection.
The PC must have the selected models installed separately. In a second PC terminal,
after Tailscale is installed/authorized and HTTPS enabled:

```powershell
tailscale serve --bg http://127.0.0.1:8767
```

Open the HTTPS URL printed by Tailscale on the phone, with Tailscale connected.
Pair using the local `data/phone-pair-code` file. Do not paste it into chat. The
six-digit pairing code expires after 15 minutes; sessions expire after eight hours.
Each paired device is treated as the same operator: this is not a multi-user service.
No Mac hop is needed once deployed. RTX deployment is pending PC inventory/access.

## Current local test

Port 8767 on the Mac, forwarded over USB using ADB reverse. Phone opens
http://localhost:8767. This is a development-only localhost connection, not the
intended wireless PC route. Existing port 8766 service was left running.

## User flow and boundaries

1. Turn on camera and point it at the object/page.
2. Identify & tell sends one frame to the selected vision model and speaks its answer.
3. Scan a page freezes a browser-local frame. No save has happened yet.
4. Extract text optionally runs vision transcription. Review/edit it for errors.
5. Choose PDF/JPEG (original page image) or TXT/Markdown (reviewed text).
6. Choose private GIG files or Google Drive; tap Save as the explicit approval.
7. Download link comes from a successfully stored file, not model-generated text.

Voice/text commands starting with “scan” or “save it/this/that” open the review
screen and recognize these format names and Drive. This is a narrow deterministic
command path, NOT general autonomous tool planning. Arbitrary formats, multi-page
scans, perspective correction and searchable-text PDFs are not implemented.
Image PDFs preserve the photographed page; the edited transcription is exported
only in TXT/Markdown. Do not describe visual transcription as infallible OCR.

Local links require pairing and a running server; they are not public share links.
Files persist in `data/documents.sqlite3` (200 MB quota). Session Forget does not
delete saved files; use Delete local copy. Deletion is logical, not forensic erasure.
Drive copies need deletion in Drive. User camera files are never sent to arbitrary
file-hosting websites. A public sharing provider requires a separate explicit decision.

## Google Drive

Implemented multipart upload adapter; live authorization/upload not tested yet.
Enable Drive API in your Google Cloud project, create an OAuth Desktop app client,
and add your account as a test user if required. Keep downloaded JSON private.
Run `uv run python connect_drive.py <client-json-path>` on the server and approve
the browser consent. Set GIG_GOOGLE_CREDENTIALS_FILE to its private output path.
Uses `drive.file` scope. Never commit credential files or expose them to models.

The Save & upload button explicitly discloses both the private local copy and the
Drive upload. The backend binds approval to the stored file hash. No public Drive
permissions are created. Missing authorization gives a truthful error and retains
the local file. Ambiguous upload failures are recorded as unknown and blocked
from automatic retries to avoid duplicates. Manual reconciliation is currently
required; this is intentionally not an unattended upload/retry service.

## Privacy and harness boundary

Auto chooses local only; cloud requires explicit model selection. Camera content
is untrusted input, never authorization. Capture stop disables browser streams
and clears the unsaved scan; it cannot retract an already transmitted frame or
roll back a save/upload already started. Backend cancellation remains future work.
The document tools can become allowlisted OpenClaw tools behind a separate human
approval interface. OpenClaw itself has NOT been installed/integrated in this slice.

## Evidence, 2026-10-08

- 43 pytest tests passed, including authentication, file formats, repeat saves,
  malformed images, consent, Drive unavailable, mock upload and no-retry behavior.
- Real local qwen2.5vl:3b transcription of a synthetic four-line page matched its
  content including reference 4821. One request: 23,587.7 ms; scan/save/download
  23,676 ms. Valid PDF: 45,616 bytes. NOT phone/RTX/network/speech latency.
- Reproduce local model smoke test: GIG_VISION_MODEL=qwen2.5vl:3b followed by
  `.venv/bin/python tests/live_scan_smoke.py` (shell syntax differs on Windows).
- Remaining acceptance: real phone capture/speech, direct RTX deployment, Drive
  OAuth/live upload and latency across repeated representative pages.

References: https://developers.google.com/workspace/drive/api/guides/manage-uploads
and https://tailscale.com/docs/features/tailscale-serve .
