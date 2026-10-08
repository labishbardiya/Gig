# Call-E integration boundary

GIG currently implements a phone-facing call brief and exact-approval ledger.
It does **not** place a call from this gateway yet.

Use `GET /calls/status` after pairing. If `configured` is false, set a Call-E
key only in the PC process environment:

```powershell
$env:CALL_E_API_KEY = [System.Net.NetworkCredential]::new('', (Read-Host 'Call-E API key' -AsSecureString)).Password
```

The key is never stored in GIG files, browser code, QR URLs, or Git.

Before enabling outbound calls, add and test a provider adapter against Call-E's
verified current API documentation. It must implement these guarantees:

1. A user sees the recipient's explicit E.164 number, purpose, supplied context,
   boundaries, AI disclosure, and cost warning.
2. A call begins only after exact matching approval of that immutable brief.
3. The assistant discloses it is AI calling on behalf of the named user.
4. Network uncertainty becomes `unknown`; there is no automatic redial.
5. Provider transcripts/results are untrusted data and cannot trigger further
   actions without user approval.

Until the provider contract is validated, GIG returns an honest `503` after
approval and **does not contact anyone**.
