"""Phone-facing Call-E proposal ledger.

The vendor's direct HTTP contract is deliberately not guessed here. A key alone
is insufficient evidence that a call can be safely submitted. This exposes a
transparent prepare/confirm flow and reports provider configuration honestly.
"""
import hashlib
import json
import os
import re
import time
import uuid

from fastapi import HTTPException, Request
from pydantic import BaseModel, Field, model_validator


E164 = re.compile(r'^\+[1-9][0-9]{7,14}$')


class CallBrief(BaseModel):
    phone: str = Field(max_length=16)
    on_behalf_of: str = Field(min_length=1, max_length=100)
    purpose: str = Field(min_length=1, max_length=1000)
    approved_context: str = Field(default='', max_length=4000)
    boundaries: str = Field(min_length=1, max_length=2000)
    language: str = Field(default='en', pattern=r'^[a-z]{2}(-[A-Z]{2})?$')

    @model_validator(mode='after')
    def valid_phone(self):
        if not E164.fullmatch(self.phone):
            raise ValueError('Use an explicit E.164 phone number, for example +919876543210')
        return self


class CallApproval(BaseModel):
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    confirm: str = Field(pattern=r'^PLACE THIS CALL$')


def install_call_e(app, authenticate, store):
    @app.get('/calls/status')
    def call_status(request: Request):
        authenticate(request)
        configured = bool(os.getenv('CALL_E_API_KEY'))
        return {'configured': configured, 'ready': False,
                'provider_contract_verified': False,
                'detail': ('Call-E API key is present, but no verified direct provider contract is configured. '
                           'No calls can be placed from this phone gateway.' if configured else
                           'Set CALL_E_API_KEY privately on the PC after obtaining a verified provider integration. No calls can be placed.'),
                'safety': 'Every call requires an immutable brief, exact approval, AI disclosure, and a verified provider adapter.'}

    @app.post('/calls')
    def prepare_call(body: CallBrief, request: Request):
        authenticate(request)
        payload = json.dumps(body.model_dump(), sort_keys=True, separators=(',', ':'))
        digest = hashlib.sha256(payload.encode()).hexdigest()
        ident = str(uuid.uuid4())
        store.execute('INSERT INTO call_actions VALUES(?,?,?,?,?)', (ident, payload, digest, 'awaiting_approval', time.time()))
        return {'id': ident, 'state': 'awaiting_approval', 'brief': body.model_dump(), 'sha256': digest,
                'expires_in_seconds': 600,
                'disclosure': f'GIG will disclose that it is an AI assistant calling on behalf of {body.on_behalf_of}.',
                'notice': 'This prepares only. It does not call, reserve credits, or contact the recipient.'}

    @app.post('/calls/{ident}/approve')
    def approve_call(ident: str, approval: CallApproval, request: Request):
        authenticate(request)
        rows = store.rows('SELECT * FROM call_actions WHERE id=?', (ident,))
        if not rows:
            raise HTTPException(404, 'Call proposal not found')
        row = rows[0]
        if row['state'] != 'awaiting_approval' or row['created'] < time.time() - 600:
            raise HTTPException(409, 'Call proposal is already handled or approval expired')
        if row['sha'] != approval.sha256:
            raise HTTPException(409, 'The reviewed call brief does not match this approval')
        # No vendor request is made. Do not mark it submitted or consume a proposal.
        raise HTTPException(503, 'Call-E provider adapter is not verified on this PC. No call was placed.')
