"""Narrow, auditable computer-action demonstration boundary.

This is intentionally *not* a remote-shell or desktop automation service.  The
only runnable action is a read-only server identity/status check.  It exists to
exercise the same propose -> exact approval -> execute -> verify -> audit shape
that a future, per-tool computer-use worker must keep.
"""
import hashlib
import json
import platform
import socket
import time
import uuid
from typing import Literal

from fastapi import HTTPException, Request
from pydantic import BaseModel, Field


class ComputerProposal(BaseModel):
    chat_id: str
    action: Literal['system_status']
    reason: str = Field(min_length=3, max_length=500)


class ComputerApproval(BaseModel):
    confirmation: Literal['RUN READ-ONLY COMPUTER CHECK']
    payload_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')


def _canonical_payload(chat_id: str, action: str, reason: str) -> str:
    """Stable review payload; changes require a fresh proposal and approval."""
    return json.dumps(
        {'action': action, 'chat_id': chat_id, 'reason': reason.strip()},
        separators=(',', ':'), sort_keys=True,
    )


def _fingerprint(payload: str) -> str:
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def _verified_system_status() -> dict:
    """Read-only execution proof.  No subprocess, shell, app, or file access."""
    return {
        'verified_at_unix': round(time.time(), 3),
        'hostname': socket.gethostname(),
        'operating_system': platform.system(),
        'machine': platform.machine(),
        'action_scope': 'read_only_server_identity',
    }


def install_computer_actions(app, authenticate, store):
    """Install demo-safe action routes onto the paired phone app."""

    @app.get('/computer/actions')
    def list_actions(request: Request):
        authenticate(request)
        return store.rows('SELECT * FROM computer_actions ORDER BY created DESC LIMIT 100')

    @app.get('/computer/actions/{ident}/events')
    def action_events(ident: str, request: Request):
        authenticate(request)
        if not store.rows('SELECT id FROM computer_actions WHERE id=?', (ident,)):
            raise HTTPException(404, 'Computer action not found')
        return store.rows(
            'SELECT phase,detail,created FROM computer_action_events WHERE action_id=? ORDER BY id',
            (ident,),
        )

    @app.post('/computer/actions')
    def prepare_action(body: ComputerProposal, request: Request):
        authenticate(request)
        store.chat(body.chat_id)
        reason = body.reason.strip()
        payload = _canonical_payload(body.chat_id, body.action, reason)
        digest = _fingerprint(payload)
        # Identical active proposal is idempotent rather than creating a stack of
        # indistinguishable approvals.
        existing = store.rows(
            "SELECT * FROM computer_actions WHERE payload_sha256=? AND state='awaiting_approval' "
            'AND created>? ORDER BY created DESC LIMIT 1',
            (digest, time.time() - 600),
        )
        if existing:
            return {**existing[0], 'idempotent': True}
        ident = str(uuid.uuid4())
        now = time.time()
        store.execute(
            'INSERT INTO computer_actions VALUES(?,?,?,?,?,?,?,?,?,?)',
            (ident, body.chat_id, body.action, reason, payload, digest,
             'awaiting_approval', '', now, now),
        )
        store.execute(
            'INSERT INTO computer_action_events(action_id,phase,detail,created) VALUES(?,?,?,?)',
            (ident, 'prepared', 'Read-only computer check proposed; no computer action has run.', now),
        )
        return {
            'id': ident, 'chat_id': body.chat_id, 'action': body.action,
            'reason': reason, 'payload': json.loads(payload),
            'payload_sha256': digest, 'state': 'awaiting_approval',
            'expires_in_seconds': 600,
        }

    @app.post('/computer/actions/{ident}/approve')
    def approve_action(ident: str, body: ComputerApproval, request: Request):
        authenticate(request)
        now = time.time()
        with store.lock:
            rows = store.rows('SELECT * FROM computer_actions WHERE id=?', (ident,))
            if not rows:
                raise HTTPException(404, 'Computer action not found')
            row = rows[0]
            if row['state'] != 'awaiting_approval':
                return {'id': ident, 'state': row['state'], 'idempotent': True}
            if row['created'] < now - 600:
                store.execute("UPDATE computer_actions SET state='expired',updated=? WHERE id=?", (now, ident))
                store.execute('INSERT INTO computer_action_events(action_id,phase,detail,created) VALUES(?,?,?,?)',
                              (ident, 'expired', 'Approval window elapsed; nothing was executed.', now))
                return {'id': ident, 'state': 'expired'}
            if body.payload_sha256 != row['payload_sha256']:
                raise HTTPException(409, 'Approval fingerprint does not match the reviewed proposal')
            # The action allowlist remains deliberately one item.  New actions
            # must have their own schemas, policy checks, tests and verifier.
            if row['action'] != 'system_status':
                raise HTTPException(409, 'This server does not permit that computer action')
            store.execute("UPDATE computer_actions SET state='running',updated=? WHERE id=?", (now, ident))
            store.execute('INSERT INTO computer_action_events(action_id,phase,detail,created) VALUES(?,?,?,?)',
                          (ident, 'approved', 'Exact reviewed payload approved by paired user.', now))
        try:
            evidence = _verified_system_status()
            result = json.dumps(evidence, sort_keys=True)
            state = 'verified'
            detail = 'Read-only server identity returned and recorded.'
        except Exception:  # defensive state: no retry of an unknown side effect
            result = 'Computer check failed; no automatic retry was attempted.'
            state = 'unknown'
            detail = 'Outcome could not be verified; no automatic retry.'
        finished = time.time()
        store.execute('UPDATE computer_actions SET state=?,result=?,updated=? WHERE id=? AND state=\'running\'',
                      (state, result, finished, ident))
        store.execute('INSERT INTO computer_action_events(action_id,phase,detail,created) VALUES(?,?,?,?)',
                      (ident, state, detail, finished))
        return {'id': ident, 'state': state, 'result': json.loads(result) if state == 'verified' else result}

    @app.post('/computer/actions/{ident}/reject')
    def reject_action(ident: str, request: Request):
        authenticate(request)
        now = time.time()
        changed = store.execute(
            "UPDATE computer_actions SET state='rejected',updated=? WHERE id=? AND state='awaiting_approval'",
            (now, ident),
        )
        if changed:
            store.execute('INSERT INTO computer_action_events(action_id,phase,detail,created) VALUES(?,?,?,?)',
                          (ident, 'rejected', 'User rejected proposal; no computer action ran.', now))
        return {'id': ident, 'rejected': bool(changed)}
