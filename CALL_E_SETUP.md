# CALL-E integration boundary

GIG uses CALL-E's documented one-shot Calls API only after an immutable brief
and literal `PLACE THIS CALL` approval. `POST /calls` is local preparation;
`POST /calls/{id}/approve` can place one real call, and `GET /calls/{id}` polls
only the accepted provider call until its structured result is terminal.

Use `GET /calls/status` after pairing. If `configured` is false, set a Call-E
key only in the PC process environment:

```powershell
$env:CALLE_API_KEY = [System.Net.NetworkCredential]::new('', (Read-Host 'CALL-E API key' -AsSecureString)).Password
```

The key is never stored in GIG files, browser code, QR URLs, or Git.

`CALL_E_API_KEY` remains accepted only for migration. The key is never stored in
GIG files, browser code, QR URLs, or Git.

The adapter uses `POST https://api.heycall-e.com/v2/calls` with a stable
`Idempotency-Key`, then `GET /v2/calls/{id}` for explicit polling. Its result
schema is closed and flat; the provider call resource ID, not telephone billing
ID, is retained for polling. A `202 Accepted` means durable acceptance, not that
the recipient connected or that the goal succeeded.

Outbound use still requires these guarantees:

1. A user sees the recipient's explicit E.164 number, purpose, supplied context,
   boundaries, AI disclosure, and cost warning.
2. A call begins only after exact matching approval of that immutable brief.
3. The assistant discloses it is AI calling on behalf of the named user.
4. Network uncertainty becomes `unknown`; there is no automatic redial.
5. Provider transcripts/results are untrusted data and cannot trigger further
   actions without user approval.

If submission times out or the network fails, GIG marks the outcome `unknown`
and never automatically retries or redials. Reconcile the provider before a
human decides how to proceed. Tests use a mocked provider; no calls are made by
the repository test suite.
