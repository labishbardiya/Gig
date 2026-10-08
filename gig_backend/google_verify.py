"""Explicit, non-destructive Google Workspace verification helpers."""
import json
import time
import uuid
from pathlib import Path

import httpx
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials

DRIVE_SCOPE = 'https://www.googleapis.com/auth/drive.file'
GMAIL_SCOPE = 'https://www.googleapis.com/auth/gmail.compose'
CALENDAR_SCOPE = 'https://www.googleapis.com/auth/calendar.events'


def load_credentials(path: Path, scopes):
    credentials = Credentials.from_authorized_user_file(str(path))
    if not credentials.has_scopes(scopes):
        raise RuntimeError('OAuth file is missing required scope(s); reauthorize with connect_drive.py --workspace')
    if not credentials.valid:
        credentials.refresh(GoogleRequest())
        path.write_text(credentials.to_json(), encoding='utf-8')
    return credentials


def private_drive_probe(credentials, now=None):
    """Create one tiny private file. No permissions endpoint is called."""
    stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime(now or time.time()))
    filename = f'GIG-private-verification-{stamp}-{uuid.uuid4().hex[:8]}.txt'
    boundary = 'gig_verify_' + uuid.uuid4().hex
    metadata = json.dumps({'name': filename, 'mimeType': 'text/plain'}).encode()
    content = b'GIG Google Drive verification file. Safe to delete.\n'
    body = (f'--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n'.encode() + metadata +
            f'\r\n--{boundary}\r\nContent-Type: text/plain\r\n\r\n'.encode() + content +
            f'\r\n--{boundary}--\r\n'.encode())
    with httpx.Client(timeout=30, trust_env=False) as client:
        response = client.post('https://www.googleapis.com/upload/drive/v3/files',
                               params={'uploadType': 'multipart', 'fields': 'id,name,webViewLink'}, content=body,
                               headers={'Authorization': 'Bearer ' + credentials.token,
                                        'Content-Type': 'multipart/related; boundary=' + boundary})
        response.raise_for_status()
        item = response.json()
    if not isinstance(item.get('id'), str) or not isinstance(item.get('name'), str):
        raise RuntimeError('Drive did not return a file identifier')
    return {'id': item['id'], 'name': item['name'],
            'link': item.get('webViewLink') or f"https://drive.google.com/file/d/{item['id']}/view",
            'private': True}


def provider_check(credentials, provider):
    urls = {'gmail': 'https://gmail.googleapis.com/gmail/v1/users/me/profile',
            'calendar': 'https://www.googleapis.com/calendar/v3/users/me/calendarList?maxResults=1'}
    with httpx.Client(timeout=10, trust_env=False) as client:
        response = client.get(urls[provider], headers={'Authorization': 'Bearer ' + credentials.token})
    return response.status_code == 200
