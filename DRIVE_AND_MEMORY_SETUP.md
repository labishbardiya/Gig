# Drive and semantic memory: PC setup

These two features run on the RTX PC. Do not place Google credentials, Drive
tokens, pairing codes, or model endpoints on GitHub or inside the public QR URL.

## 1. Google Drive, Gmail drafts, and Calendar events: one-time owner authorization

1. In Google Cloud Console, create or select a project, enable **Google Drive API**,
   and create an **OAuth client ID → Desktop app**.
2. Download its client JSON to a private location on the PC, for example
   `C:\Users\lab\gig-private\google-client.json`. Keep this outside the Git repo.
3. From `C:\Users\lab\Desktop\gig`, run:

```powershell
uv run python connect_drive.py C:\Users\lab\gig-private\google-client.json --workspace --output C:\Users\lab\gig-private\google-authorized-user.json
```

4. Complete Google sign-in in the browser. GIG requests only these scopes:
   `drive.file` for files created/opened through GIG, `gmail.compose` for drafts
   only (not sending), and `calendar.events` for explicitly approved events.
5. Before starting GIG in that same terminal, set:

```powershell
$env:GIG_GOOGLE_CREDENTIALS_FILE = 'C:\Users\lab\gig-private\google-authorized-user.json'
```

6. Start GIG. On the phone: scan → review → save locally → select Drive → compare
   the displayed SHA-256 → approve upload. The returned Drive link is private; GIG
   never changes it to "anyone with link". Gmail and Calendar actions use the same
   prepare → exact-payload review → explicit `CREATE GOOGLE ACTION` approval flow.
   Gmail creates a draft only; it never sends the mail.

Use `GET /google/status` after pairing to check the Gmail and Calendar provider
connections. A successful health check proves account connectivity only; it does
not verify a specific recipient, email, calendar, or event invitation.

## 2. Semantic memory: local only

```powershell
ollama pull qwen3-embedding:0.6b
$env:GIG_SEMANTIC_MEMORY = '1'
$env:GIG_EMBED_MODEL = 'qwen3-embedding:0.6b'
```

Then start GIG normally. New and edited explicit memories receive a local vector
embedding. A request such as "What computer does my project use?" retrieves a
semantically related saved note even when it uses different words. If Ollama or
the embedding model is unavailable, GIG keeps the note and safely falls back to
its existing lexical/recent-note retrieval; it never sends memory content to a
cloud embedding provider.

## 3. Verification

```powershell
ollama list
curl.exe http://127.0.0.1:8767/health
```

In the phone interface, save an explicit memory, ask a paraphrased question, then
use the Drive workflow with a non-sensitive test document. Do not upload private
documents during a live demo.
