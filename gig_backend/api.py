import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import threading
from typing import Literal
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from .agent import LocalAgent
from .calle import Calle, TERMINAL
from .store import Store


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class CallRequest(StrictModel):
    request_key: str = Field(min_length=8, max_length=100)
    phone: str = Field(pattern=r'^\+[1-9][0-9]{7,14}$')
    on_behalf_of: str = Field(min_length=1, max_length=100)
    goal: str = Field(min_length=1, max_length=2000)
    context: str = Field(default='', max_length=8000)
    boundaries: str = Field(min_length=1, max_length=2000)
    language: str = Field(min_length=2, max_length=80)
    region: str = Field(min_length=2, max_length=80)


class Approval(StrictModel):
    confirmation: Literal['PLACE THIS CALL']
    payload_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')


class Note(StrictModel):
    text: str = Field(min_length=1, max_length=10000)
    consent: Literal[True]


class Chat(StrictModel):
    text: str = Field(min_length=1, max_length=8000)
    retain_session: bool = False


def digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def create_app(data_dir=None, token=None, live=None, provider=None, agent=None):
    root = Path(data_dir or os.getenv('GIG_DATA_DIR', Path(__file__).resolve().parents[1] / 'data'))
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    token_file = root / 'api-token'
    if token is None:
        if not token_file.exists():
            fd = os.open(token_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as f:
                f.write(secrets.token_urlsafe(32))
        token = token_file.read_text().strip()
    if not token:
        raise ValueError('API token cannot be empty')
    store = Store(root / 'gig.sqlite3')
    live = os.getenv('GIG_ENABLE_LIVE_CALLS') == '1' if live is None else live
    provider = provider or Calle(os.getenv('CALLE_PACKAGE_DIR', '/opt/homebrew/lib/node_modules/@call-e/cli'),
                                str(Path(__file__).resolve().parents[1] / 'vendor/run-agent-command.mjs'),
                                os.getenv('GIG_NODE', '/opt/homebrew/bin/node'))
    agent = agent or LocalAgent(os.getenv('GIG_MODEL', ''))
    session_lock = threading.Lock()
    app = FastAPI(title='GIG Backend', version='0.1.0', description='Single-user local development backend. Calls disabled by default.')
    app.state.store = store
    security = HTTPBearer(auto_error=False)

    def authorised(credentials: HTTPAuthorizationCredentials = Depends(security)):
        if credentials is None or not hmac.compare_digest(credentials.credentials, token):
            raise HTTPException(401, 'Valid bearer token required')

    def lookup(ident):
        try:
            return store.get_call(ident)
        except KeyError:
            raise HTTPException(404, 'Call not found')

    def public(row):
        return {**row, 'payload_sha256': digest(row['payload']), 'live_enabled': live,
                'warning': 'Approval contacts a real person and can spend CALL-E credits. Context leaves this computer. Caller will disclose AI identity.'}

    @app.get('/health')
    def health():
        return {'status': 'ok', 'live_calls_enabled': live, 'mode': 'single-user-local', 'version': '0.1.0'}

    @app.get('/v1/readiness', dependencies=[Depends(authorised)])
    def readiness():
        return {'model': agent.readiness(), 'scope': 'model inventory, not end-to-end acceptance'}

    @app.post('/v1/calls/prepare', dependencies=[Depends(authorised)])
    def prepare(body: CallRequest):
        payload = body.model_dump(exclude={'request_key'})
        try:
            return public(store.prepare(body.request_key, payload))
        except ValueError as exc:
            raise HTTPException(409, str(exc))

    @app.get('/v1/calls/{ident}', dependencies=[Depends(authorised)])
    def get_call(ident: str):
        return public(lookup(ident))

    @app.post('/v1/calls/{ident}/approve', dependencies=[Depends(authorised)])
    def approve(ident: str, body: Approval):
        row = lookup(ident)
        if not hmac.compare_digest(body.payload_sha256, digest(row['payload'])):
            raise HTTPException(409, 'Call details do not match approval')
        if row['state'] != 'awaiting_approval':
            return public(row)
        if not live:
            raise HTTPException(409, 'Live calls disabled; no call placed')
        try:
            ready = provider.ready()
        except Exception:
            raise HTTPException(503, 'CALL-E readiness failed; no call submitted')
        if not ready:
            raise HTTPException(503, 'CALL-E authentication required; no call submitted')
        if not store.claim(ident):
            return public(lookup(ident))
        try:
            run_id, result = provider.start(row['payload'])
            store.finish(ident, 'finished' if result.get('status') in TERMINAL else 'active', run_id, result)
        except Exception:
            store.finish(ident, 'unknown', result={'message': 'Submission uncertain. Do not redial. Use private CLI recovery/manual reconciliation.', 'untrusted_call_data': True})
        return public(lookup(ident))

    @app.post('/v1/calls/{ident}/refresh', dependencies=[Depends(authorised)])
    def refresh(ident: str):
        row = lookup(ident)
        if row['state'] == 'finished':
            return public(row)
        if not row['run_id']:
            raise HTTPException(409, 'No known provider run ID; do not submit another call')
        try:
            result = provider.status(row['run_id'])
        except Exception:
            raise HTTPException(503, 'Status unavailable; existing call was not resubmitted')
        store.finish(ident, 'finished' if result.get('status') in TERMINAL else 'active', result=result)
        return public(lookup(ident))

    @app.post('/v1/calls/{ident}/cancel', dependencies=[Depends(authorised)])
    def cancel(ident: str):
        lookup(ident)
        if not store.cancel(ident):
            raise HTTPException(409, 'Only unsubmitted calls can be cancelled here; this endpoint cannot hang up an active call')
        return public(lookup(ident))

    @app.post('/v1/notes', dependencies=[Depends(authorised)])
    def save_note(body: Note):
        return {'id': store.save_note(body.text), 'saved': True}

    @app.get('/v1/notes', dependencies=[Depends(authorised)])
    def notes(q: str = ''):
        return {'items': store.notes(q)}

    @app.delete('/v1/notes/{ident}', dependencies=[Depends(authorised)])
    def delete_note(ident: str):
        if not store.forget(ident):
            raise HTTPException(404, 'Note not found')
        return {'deleted': True}

    @app.post('/v1/sessions/{ident}/chat', dependencies=[Depends(authorised)])
    def chat(ident: str, body: Chat):
        with session_lock:
            history = store.conversation(ident) if body.retain_session else []
            messages = history + [{'role': 'user', 'content': body.text}]
            try:
                result = agent.run(messages)
            except Exception:
                raise HTTPException(503, 'Configured model unavailable or failed. Check GIG_MODEL and GIG_MODEL_URL; no fallback used.')
            if body.retain_session:
                store.save_conversation(ident, messages + [{'role': 'assistant', 'content': result['answer']}])
        return {'answer': result['answer'], 'model_request_ms': result['elapsed_ms'], 'retained': body.retain_session, 'timing_scope': 'model request, not full voice latency'}

    @app.delete('/v1/sessions/{ident}', dependencies=[Depends(authorised)])
    def forget_session(ident: str):
        store.delete_conversation(ident)
        return {'deleted': True}

    return app
