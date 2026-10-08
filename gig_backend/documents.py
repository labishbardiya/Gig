"""Single-owner, authenticated document tools; independent of the agent harness.

No model can approve uploads. Files are private, never public-by-link.
"""
import base64
import hashlib
import io
import json
import os
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Literal

import httpx
from fastapi import HTTPException
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field


class SaveDocument(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    format: Literal['pdf', 'jpg', 'txt', 'md']
    image: str | None = Field(default=None, max_length=2_800_000)
    text: str = Field(default='', max_length=50_000)
    consent: Literal[True]


class DriveApproval(BaseModel):
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    confirm_upload: Literal[True]


def camera_image(value):
    """Decode bounded JPEG, remove metadata and reject decompression bombs."""
    try:
        if not value or not value.startswith('data:image/jpeg;base64,'):
            raise ValueError()
        raw = base64.b64decode(value.split(',', 1)[1], validate=True)
        if len(raw) > 2_000_000:
            raise ValueError()
        with Image.open(io.BytesIO(raw)) as image:
            if image.format != 'JPEG' or image.width * image.height > 12_000_000:
                raise ValueError()
            image.load()
            return ImageOps.exif_transpose(image).convert('RGB')
    except (ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombError):
        raise HTTPException(400, 'Use a JPEG camera frame below 2 MB and 12 megapixels')


def render_document(body):
    title = re.sub(r'[^\w .-]', '', body.title, flags=re.UNICODE).strip(' .')[:90] or 'Scan'
    if body.format in ('pdf', 'jpg'):
        image = camera_image(body.image)
        output = io.BytesIO()
        # Image PDF preserves the actual scan. No invented OCR layer.
        image.save(output, 'PDF' if body.format == 'pdf' else 'JPEG', resolution=150, quality=92,
                   creationDate=time.gmtime(0), modDate=time.gmtime(0))
        data = output.getvalue()
    else:
        if not body.text.strip():
            raise HTTPException(400, 'Review or enter the extracted text before saving a text file')
        data = body.text.encode('utf-8')
    mime = {'pdf': 'application/pdf', 'jpg': 'image/jpeg',
            'txt': 'text/plain; charset=utf-8', 'md': 'text/markdown; charset=utf-8'}[body.format]
    return title + '.' + body.format, mime, data


class Documents:
    def __init__(self, root):
        self.path = Path(root) / 'documents.sqlite3'
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(fd)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY, filename TEXT, '
                       'mime TEXT, content BLOB, sha TEXT, created REAL, dedup TEXT UNIQUE, '
                       'drive_state TEXT DEFAULT "none", drive_url TEXT)')
            db.execute('UPDATE documents SET drive_state="unknown" WHERE drive_state="uploading"')

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def metadata(row):
        return {'id': row['id'], 'filename': row['filename'], 'sha256': row['sha'],
                'created': row['created'], 'url': '/documents/' + row['id'] + '/download',
                'drive_state': row['drive_state'], 'drive_url': row['drive_url'],
                'access': 'private; paired devices belonging to this operator only'}

    def save(self, body):
        filename, mime, data = render_document(body)
        sha = hashlib.sha256(data).hexdigest()
        dedup = hashlib.sha256(filename.encode() + b'\0' + data).hexdigest()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM documents WHERE dedup=?', (dedup,)).fetchone()
            if row:
                return self.metadata(row)
            total = db.execute('SELECT coalesce(sum(length(content)),0) FROM documents').fetchone()[0]
            if total + len(data) > 200_000_000:
                raise HTTPException(507, 'Private document storage is full; delete unneeded files first')
            ident = uuid.uuid4().hex
            db.execute('INSERT INTO documents (id,filename,mime,content,sha,created,dedup) '
                       'VALUES (?,?,?,?,?,?,?)', (ident, filename, mime, data, sha, time.time(), dedup))
            return self.metadata(db.execute('SELECT * FROM documents WHERE id=?', (ident,)).fetchone())

    def get(self, ident):
        with self.connect() as db:
            row = db.execute('SELECT * FROM documents WHERE id=?', (ident,)).fetchone()
        if row is None:
            raise HTTPException(404, 'Document not found')
        return row

    def list(self):
        with self.connect() as db:
            return [self.metadata(row) for row in db.execute('SELECT * FROM documents ORDER BY created DESC LIMIT 100')]

    def delete(self, ident):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT drive_state FROM documents WHERE id=?', (ident,)).fetchone()
            if row and row['drive_state'] in ('uploading', 'unknown'):
                raise HTTPException(409, 'Resolve the pending Drive upload before deleting its record')
            db.execute('DELETE FROM documents WHERE id=?', (ident,))
        return {'deleted': True, 'scope': 'local file only; existing Drive copies are unchanged'}

    def upload_drive(self, ident, approval):
        row = self.get(ident)
        if row['sha'] != approval.sha256:
            raise HTTPException(409, 'The reviewed file does not match this upload')
        if row['drive_state'] == 'complete':
            return self.metadata(row)
        credentials_file = os.getenv('GIG_GOOGLE_CREDENTIALS_FILE')
        if not credentials_file:
            raise HTTPException(503, 'Connect Google Drive on the server first. Your local file is safe; nothing was uploaded.')
        try:
            credentials = Credentials.from_authorized_user_file(credentials_file)
            if not credentials.valid:
                credentials.refresh(GoogleRequest())
        except Exception:
            raise HTTPException(503, 'Google authorization failed. Reconnect Drive on the server.')
        with self.connect() as db:
            claimed = db.execute('UPDATE documents SET drive_state="uploading" WHERE id=? AND drive_state="none"', (ident,))
            if claimed.rowcount != 1:
                raise HTTPException(409, 'Upload pending or outcome unknown. Check Drive before retrying; automatic duplicate uploads are blocked.')
        boundary = 'gig_' + uuid.uuid4().hex
        metadata = json.dumps({'name': row['filename'], 'appProperties': {'gig_document_id': ident}}).encode()
        body = (f'--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n'.encode()
                + metadata + f'\r\n--{boundary}\r\nContent-Type: {row["mime"]}\r\n\r\n'.encode()
                + row['content'] + f'\r\n--{boundary}--\r\n'.encode())
        try:
            with httpx.Client(timeout=45, trust_env=False) as client:
                response = client.post('https://www.googleapis.com/upload/drive/v3/files',
                    params={'uploadType': 'multipart', 'fields': 'id,webViewLink'}, content=body,
                    headers={'Authorization': 'Bearer ' + credentials.token,
                             'Content-Type': 'multipart/related; boundary=' + boundary})
                response.raise_for_status()
                file_id = response.json()['id']
                if not isinstance(file_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', file_id):
                    raise ValueError()
                url = 'https://drive.google.com/file/d/' + file_id + '/view'
        except Exception:
            with self.connect() as db:
                db.execute('UPDATE documents SET drive_state="unknown" WHERE id=?', (ident,))
            raise HTTPException(502, 'Drive upload outcome is unknown. Check Drive; this request will not be automatically repeated.')
        with self.connect() as db:
            db.execute('UPDATE documents SET drive_state="complete",drive_url=? WHERE id=?', (url, ident))
        return self.metadata(self.get(ident))
