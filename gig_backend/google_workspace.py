"""Approval-gated Google Workspace actions for the single GIG owner.

This module can create Gmail *drafts* and Calendar *events*. It never sends mail,
and it never runs an action merely because a model proposed it.
"""
import base64
import hashlib
import json
import os
import re
import time
import uuid
from email.message import EmailMessage

import httpx
from fastapi import HTTPException, Request
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from pydantic import BaseModel, Field, model_validator


GMAIL_SCOPE = 'https://www.googleapis.com/auth/gmail.compose'
CALENDAR_SCOPE = 'https://www.googleapis.com/auth/calendar.events'
EMAIL = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')


class GoogleAction(BaseModel):
    kind: str = Field(pattern=r'^(gmail_draft|calendar_event)$')
    to: list[str] = Field(default_factory=list, max_length=20)
    subject: str = Field(default='', max_length=200)
    body: str = Field(default='', max_length=20_000)
    title: str = Field(default='', max_length=200)
    start: str = Field(default='', max_length=64)
    end: str = Field(default='', max_length=64)
    timezone: str = Field(default='Asia/Kolkata', max_length=64)
    attendees: list[str] = Field(default_factory=list, max_length=20)
    description: str = Field(default='', max_length=20_000)

    @model_validator(mode='after')
    def check_kind(self):
        if self.kind == 'gmail_draft':
            if not self.to or not self.subject.strip() or not self.body.strip() or not all(EMAIL.fullmatch(x) for x in self.to):
                raise ValueError('Gmail draft needs valid recipients, subject, and body')
        else:
            if not self.title.strip() or not self.start or not self.end or not all(EMAIL.fullmatch(x) for x in self.attendees):
                raise ValueError('Calendar event needs title, start, end, and valid attendee emails')
            if self.end <= self.start:
                raise ValueError('Calendar event end must be after start')
        return self


class Approval(BaseModel):
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    confirm: str = Field(pattern=r'^CREATE GOOGLE ACTION$')


class GoogleWorkspace:
    def __init__(self, store):
        self.store = store

    @staticmethod
    def credential_path():
        value = os.getenv('GIG_GOOGLE_CREDENTIALS_FILE', '')
        return value if value and os.path.isfile(value) else ''

    def credentials(self, required_scopes):
        path = self.credential_path()
        if not path:
            raise HTTPException(503, 'Google Workspace is not connected on this server')
        try:
            credentials = Credentials.from_authorized_user_file(path)
            if not credentials.has_scopes(required_scopes):
                raise ValueError('Missing required Google scope')
            if not credentials.valid:
                credentials.refresh(GoogleRequest())
                with open(path, 'w', encoding='utf-8') as output:
                    output.write(credentials.to_json())
            return credentials
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, 'Google authorization failed. Reconnect this PC with the required scopes.')

    def status(self):
        result = {'configured': bool(self.credential_path()), 'gmail': False, 'calendar': False,
                  'detail': 'Google Workspace is not connected on this server'}
        if not result['configured']:
            return result
        try:
            gmail = self.credentials([GMAIL_SCOPE])
            with httpx.Client(timeout=8, trust_env=False) as client:
                response = client.get('https://gmail.googleapis.com/gmail/v1/users/me/profile',
                                      headers={'Authorization': 'Bearer ' + gmail.token})
                result['gmail'] = response.status_code == 200
            calendar = self.credentials([CALENDAR_SCOPE])
            with httpx.Client(timeout=8, trust_env=False) as client:
                response = client.get('https://www.googleapis.com/calendar/v3/users/me/calendarList',
                                      params={'maxResults': 1}, headers={'Authorization': 'Bearer ' + calendar.token})
                result['calendar'] = response.status_code == 200
            result['detail'] = 'Provider checks completed; no email was sent and no event was created.'
        except HTTPException as error:
            result['detail'] = str(error.detail)
        return result

    @staticmethod
    def canonical(body):
        return json.dumps(body.model_dump(), sort_keys=True, separators=(',', ':'))

    def prepare(self, body):
        payload = self.canonical(body)
        digest = hashlib.sha256(payload.encode()).hexdigest()
        ident = str(uuid.uuid4())
        now = time.time()
        self.store.execute('INSERT INTO google_actions VALUES(?,?,?,?,?,?,?,?)',
                           (ident, body.kind, payload, digest, 'awaiting_approval', '', '', now))
        return {'id': ident, 'kind': body.kind, 'payload': body.model_dump(), 'sha256': digest,
                'state': 'awaiting_approval', 'expires_in_seconds': 600,
                'notice': 'Review this exact payload. GIG will not send email; Gmail action creates a draft only.'}

    def approve(self, ident, approval):
        rows = self.store.rows('SELECT * FROM google_actions WHERE id=?', (ident,))
        if not rows:
            raise HTTPException(404, 'Google action not found')
        action = rows[0]
        if action['state'] != 'awaiting_approval' or action['created'] < time.time() - 600:
            raise HTTPException(409, 'Action is already handled or approval expired')
        if action['sha'] != approval.sha256:
            raise HTTPException(409, 'The reviewed Google action does not match this approval')
        changed = self.store.execute("UPDATE google_actions SET state='creating' WHERE id=? AND state='awaiting_approval'", (ident,))
        if not changed:
            raise HTTPException(409, 'Action is already being handled')
        payload = json.loads(action['payload'])
        try:
            if action['kind'] == 'gmail_draft':
                result = self._create_draft(payload)
            else:
                result = self._create_event(payload)
            self.store.execute("UPDATE google_actions SET state='complete',provider_id=?,provider_url=? WHERE id=?",
                               (result['id'], result.get('url', ''), ident))
        except HTTPException:
            self.store.execute("UPDATE google_actions SET state='unknown' WHERE id=?", (ident,))
            raise
        except Exception:
            self.store.execute("UPDATE google_actions SET state='unknown' WHERE id=?", (ident,))
            raise HTTPException(502, 'Google action outcome is unknown. Check Gmail or Calendar before retrying.')
        return {'id': ident, 'state': 'complete', **result}

    def _create_draft(self, payload):
        credentials = self.credentials([GMAIL_SCOPE])
        message = EmailMessage()
        message['To'] = ', '.join(payload['to'])
        message['Subject'] = payload['subject']
        message.set_content(payload['body'])
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode().rstrip('=')
        with httpx.Client(timeout=30, trust_env=False) as client:
            response = client.post('https://gmail.googleapis.com/gmail/v1/users/me/drafts',
                                   headers={'Authorization': 'Bearer ' + credentials.token}, json={'message': {'raw': raw}})
            response.raise_for_status()
            ident = response.json().get('id')
        if not isinstance(ident, str):
            raise ValueError('Missing Gmail draft id')
        return {'id': ident, 'url': 'https://mail.google.com/mail/u/0/#drafts'}

    def _create_event(self, payload):
        credentials = self.credentials([CALENDAR_SCOPE])
        body = {'summary': payload['title'], 'description': payload['description'],
                'start': {'dateTime': payload['start'], 'timeZone': payload['timezone']},
                'end': {'dateTime': payload['end'], 'timeZone': payload['timezone']},
                'attendees': [{'email': item} for item in payload['attendees']]}
        with httpx.Client(timeout=30, trust_env=False) as client:
            response = client.post('https://www.googleapis.com/calendar/v3/calendars/primary/events',
                                   headers={'Authorization': 'Bearer ' + credentials.token}, json=body)
            response.raise_for_status()
            result = response.json()
        ident = result.get('id')
        if not isinstance(ident, str):
            raise ValueError('Missing Calendar event id')
        return {'id': ident, 'url': result.get('htmlLink', '')}


def install_google_workspace(app, authenticate, store):
    gateway = GoogleWorkspace(store)

    @app.get('/google/status')
    def google_status(request: Request):
        authenticate(request)
        return gateway.status()

    @app.post('/google/actions')
    def google_prepare(body: GoogleAction, request: Request):
        authenticate(request)
        return gateway.prepare(body)

    @app.post('/google/actions/{ident}/approve')
    def google_approve(ident: str, approval: Approval, request: Request):
        authenticate(request)
        return gateway.approve(ident, approval)
