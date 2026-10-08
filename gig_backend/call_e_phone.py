"""Approval-gated CALL-E one-shot calls for the paired GIG owner.

This adapter follows the documented v2 Calls API. It is intentionally dormant
without a server-side API key, never retries a possibly accepted create request,
and never allows a model to submit or approve a call.
"""
import hashlib
import json
import os
import re
import time
import uuid

import httpx
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field, model_validator


E164 = re.compile(r'^\+[1-9][0-9]{7,14}$')
BASE_URL = 'https://api.heycall-e.com'
TERMINAL_RESULTS = {'available', 'unavailable', 'not_applicable'}

# Required, closed, and flat: CALL-E rejects nested/array/nullable schemas.
RESULT_SCHEMA = {
    'type': 'object',
    'additionalProperties': False,
    'properties': {
        'goal_completed': {'type': 'boolean'},
        'summary': {'type': 'string'},
        'follow_up_required': {'type': 'boolean'},
    },
    'required': ['goal_completed', 'summary', 'follow_up_required'],
}


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


def calle_key():
    """Primary documented name plus migration-only legacy support."""
    return os.getenv('CALLE_API_KEY', '').strip() or os.getenv('CALL_E_API_KEY', '').strip()


def provider_base_url():
    """Test endpoint override is explicit; production default is never browser supplied."""
    return os.getenv('CALLE_BASE_URL', BASE_URL).rstrip('/')


class CallEProvider:
    def __init__(self, key=None, base_url=None):
        self.key = key if key is not None else calle_key()
        self.base_url = (base_url or provider_base_url()).rstrip('/')

    @property
    def configured(self):
        return bool(self.key)

    @staticmethod
    def task(brief):
        context = brief.get('approved_context', '').strip() or 'No additional context was approved.'
        return (
            f'You are GIG, an AI assistant calling on behalf of {brief["on_behalf_of"]}. '
            f'At the beginning, clearly disclose that you are an AI assistant calling on their behalf. '
            f'Purpose: {brief["purpose"].strip()}\n'
            f'Approved context: {context}\n'
            f'Boundaries: {brief["boundaries"].strip()}\n'
            'Do not make commitments, share unapproved information, or continue beyond these boundaries. '
            'If the recipient asks for a human, state that the caller can follow up and end politely.'
        )

    @classmethod
    def request_body(cls, brief, action_id):
        # Keep this body deterministic. A recovery retry must use identical input.
        return {
            'task': cls.task(brief),
            'phone': brief['phone'],
            'result_schema': RESULT_SCHEMA,
            'locale': brief.get('language', 'en'),
            'metadata': {'gig_action_id': action_id, 'source': 'gig_phone'},
        }

    def _headers(self, idempotency_key=None):
        headers = {'Authorization': 'Bearer ' + self.key, 'Content-Type': 'application/json'}
        if idempotency_key:
            headers['Idempotency-Key'] = idempotency_key
        return headers

    def create(self, brief, action_id):
        body = self.request_body(brief, action_id)
        try:
            with httpx.Client(timeout=httpx.Timeout(30, connect=10), trust_env=False) as client:
                response = client.post(self.base_url + '/v2/calls', headers=self._headers('gig-call-' + action_id), json=body)
        except httpx.TimeoutException as exc:
            raise RuntimeError('timeout') from exc
        except httpx.HTTPError as exc:
            raise RuntimeError('network') from exc
        if response.status_code != 202:
            # Do not expose provider bodies, which can contain account diagnostics.
            raise HTTPException(503 if response.status_code >= 500 else 409,
                                'CALL-E did not accept this call. No automatic retry was attempted.')
        try:
            resource = response.json()
            ident = resource['id']
            if not isinstance(ident, str) or not ident:
                raise ValueError('missing id')
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            raise RuntimeError('invalid_response')
        return ident, resource

    def get(self, provider_id):
        try:
            with httpx.Client(timeout=httpx.Timeout(15, connect=10), trust_env=False) as client:
                response = client.get(self.base_url + '/v2/calls/' + provider_id, headers=self._headers())
            response.raise_for_status()
            resource = response.json()
            if not isinstance(resource, dict) or resource.get('id') != provider_id:
                raise ValueError('unexpected response')
            return resource
        except httpx.HTTPError as exc:
            raise HTTPException(503, 'CALL-E status is unavailable. The existing call was not changed or redialed.') from exc
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise HTTPException(502, 'CALL-E returned an invalid call status. The existing call was not changed or redialed.') from exc


def public_snapshot(action, resource=None):
    """Return useful, bounded result data; transcripts stay in CALL-E, not browser logs."""
    result = {'id': action['id'], 'state': action['state'], 'sha256': action['sha'],
              'provider_call_id': action.get('provider_id') or None}
    if resource:
        result.update({key: resource.get(key) for key in ('status', 'call_outcome', 'result_status', 'result', 'error', 'completed_at')})
    return result


def install_call_e(app, authenticate, store):
    def row(ident):
        rows = store.rows('SELECT * FROM call_actions WHERE id=?', (ident,))
        if not rows:
            raise HTTPException(404, 'Call proposal not found')
        return rows[0]

    @app.get('/calls/status')
    def call_status(request: Request):
        authenticate(request)
        configured = bool(calle_key())
        return {'configured': configured, 'ready': configured, 'provider_contract_verified': True,
                'detail': ('CALL-E is configured. Every outbound call still requires exact approval.' if configured else
                           'Set CALLE_API_KEY privately on the PC. CALL_E_API_KEY remains supported for migration.'),
                'safety': 'Every call requires an immutable brief, exact approval, AI disclosure, stable idempotency, and explicit polling.'}

    @app.post('/calls')
    def prepare_call(body: CallBrief, request: Request):
        authenticate(request)
        payload = json.dumps(body.model_dump(), sort_keys=True, separators=(',', ':'))
        digest = hashlib.sha256(payload.encode()).hexdigest()
        ident = str(uuid.uuid4())
        store.execute('INSERT INTO call_actions(id,payload,sha,state,provider_id,result,created,updated) VALUES(?,?,?,?,?,?,?,?)',
                      (ident, payload, digest, 'awaiting_approval', '', '', time.time(), time.time()))
        return {'id': ident, 'state': 'awaiting_approval', 'brief': body.model_dump(), 'sha256': digest,
                'expires_in_seconds': 600,
                'disclosure': f'GIG will disclose that it is an AI assistant calling on behalf of {body.on_behalf_of}.',
                'notice': 'This prepares only. It does not call, reserve credits, or contact the recipient.'}

    @app.post('/calls/{ident}/approve')
    def approve_call(ident: str, approval: CallApproval, request: Request):
        authenticate(request)
        action = row(ident)
        if action['state'] != 'awaiting_approval' or action['created'] < time.time() - 600:
            raise HTTPException(409, 'Call proposal is already handled or approval expired')
        if action['sha'] != approval.sha256:
            raise HTTPException(409, 'The reviewed call brief does not match this approval')
        provider = CallEProvider()
        if not provider.configured:
            raise HTTPException(503, 'CALL-E is not configured on this server. No call was placed.')
        # Atomic claim prevents two approval clicks from producing two provider requests.
        claimed = store.execute("UPDATE call_actions SET state='submitting',updated=? WHERE id=? AND state='awaiting_approval'",
                               (time.time(), ident))
        if not claimed:
            raise HTTPException(409, 'Call proposal is already being handled')
        brief = json.loads(action['payload'])
        try:
            provider_id, resource = provider.create(brief, ident)
        except HTTPException:
            store.execute("UPDATE call_actions SET state='rejected',updated=? WHERE id=?", (time.time(), ident))
            raise
        except RuntimeError:
            # A timeout can be accepted remotely. Do not auto-retry or create a fresh key.
            store.execute("UPDATE call_actions SET state='unknown',updated=? WHERE id=?", (time.time(), ident))
            raise HTTPException(502, 'CALL-E submission outcome is unknown. Do not approve or redial again; reconcile with the provider first.')
        stored = json.dumps(resource, separators=(',', ':'))
        store.execute("UPDATE call_actions SET state='pending',provider_id=?,result=?,updated=? WHERE id=?",
                      (provider_id, stored, time.time(), ident))
        return public_snapshot(row(ident), resource)

    @app.get('/calls/{ident}')
    def poll_call(ident: str, request: Request):
        authenticate(request)
        action = row(ident)
        if not action.get('provider_id'):
            return public_snapshot(action)
        try:
            cached = json.loads(action['result']) if action.get('result') else None
        except json.JSONDecodeError:
            cached = None
        # CALL-E says poll only while result_status is pending. Terminal snapshots are immutable evidence.
        if isinstance(cached, dict) and cached.get('result_status') in TERMINAL_RESULTS:
            return public_snapshot(action, cached)
        provider = CallEProvider()
        if not provider.configured:
            raise HTTPException(503, 'CALL-E is not configured on this server. Existing call was not changed.')
        resource = provider.get(action['provider_id'])
        result_status = resource.get('result_status')
        if result_status in TERMINAL_RESULTS:
            state = 'complete' if result_status == 'available' else 'finished_without_result'
        elif resource.get('status') == 'failed':
            state = 'failed'
        elif resource.get('status') == 'canceled':
            state = 'canceled'
        else:
            state = 'pending'
        store.execute('UPDATE call_actions SET state=?,result=?,updated=? WHERE id=?',
                      (state, json.dumps(resource, separators=(',', ':')), time.time(), ident))
        return public_snapshot(row(ident), resource)
