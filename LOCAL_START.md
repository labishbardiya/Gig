# Mac startup

From the project directory, activate `.venv/bin/activate`.

1. `python gig.py doctor` reports the gateway, discoverable local tunnel, and Google credential-file configuration without printing secrets.
2. `GIG_PUBLIC_DEMO=1 python gig.py start` starts the backend or reuses the running gateway. Keep a newly started backend terminal open. To apply source changes, stop the original backend terminal with Ctrl+C and start again.
3. In another terminal, `python gig.py share` reuses a discoverable HTTPS tunnel or starts ngrok pointing explicitly to IPv4 localhost.

An ngrok ERR_NGROK_334 means another session owns the endpoint. Check the ngrok dashboard agent list and stop the identified old session or reuse it if its upstream is this Mac. Do not use broad process kills or pooling as a repair. Local inspection may be disabled, so absence on port 4040 does not prove there is no tunnel.

Google is optional for the interface, voice, and chat. Adding a test user only permits consent; the user must still finish the browser authorization flow. Cancelling connect_drive.py does not save credentials. Once consent succeeds, configure GIG_GOOGLE_CREDENTIALS_FILE with the output path and restart the backend. Public guests do not inherit the operator's Google account.

Automated tests verify code paths. They do not establish live Google consent, provider credentials, successful phone playback, or public network reachability.
