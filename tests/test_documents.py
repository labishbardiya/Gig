import base64
import io
from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from gig_backend.phone import create_phone_app
from gig_backend.documents import Documents


@pytest.fixture
def client(tmp_path):
    client = TestClient(create_phone_app(tmp_path), base_url='https://testserver')
    client.post('/pair', json={'code': (tmp_path/'phone-pair-code').read_text().strip()})
    return client


def jpeg():
    data = io.BytesIO()
    Image.new('RGB', (80, 100), 'white').save(data, 'JPEG')
    return 'data:image/jpeg;base64,' + base64.b64encode(data.getvalue()).decode()


def test_private_downloads_require_pairing(tmp_path):
    client = TestClient(create_phone_app(tmp_path))
    assert client.get('/documents').status_code == 401
    assert client.get('/documents/not-real/download').status_code == 401


@pytest.mark.parametrize('format,magic', [('pdf', b'%PDF'), ('jpg', b'\xff\xd8'), ('txt', 'हैलो'.encode()), ('md', 'हैलो'.encode())])
def test_export_formats_and_repeat(client, format, magic):
    body = {'title': '../My scan', 'format': format, 'image': jpeg(), 'text': 'हैलो', 'consent': True}
    first = client.post('/documents', json=body)
    assert first.status_code == 200, first.text
    file = first.json()
    assert '/' not in file['filename']
    assert client.post('/documents', json=body).json()['id'] == file['id']
    response = client.get(file['url'])
    assert response.content.startswith(magic)
    assert response.headers['cache-control'] == 'no-store'
    assert len(client.get('/documents').json()['documents']) == 1
    assert client.delete('/documents/'+file['id']).status_code == 200
    assert client.get(file['url']).status_code == 404


def test_rejects_corrupt_image_empty_text_and_missing_consent(client):
    body = {'title':'scan', 'format':'pdf', 'image':'data:image/jpeg;base64,YWJj', 'consent':True}
    assert client.post('/documents', json=body).status_code == 400
    body['format']='txt'
    assert client.post('/documents', json=body).status_code == 400
    body['text']='test'
    body['consent']=False
    assert client.post('/documents', json=body).status_code == 422
    body['consent']=True
    body['format']='exe'
    assert client.post('/documents', json=body).status_code == 422


def test_drive_not_configured_does_not_fake_success(client, monkeypatch):
    monkeypatch.delenv('GIG_GOOGLE_CREDENTIALS_FILE', raising=False)
    file = client.post('/documents', json={'title':'test','format':'txt','text':'hello','consent':True}).json()
    result = client.post('/documents/'+file['id']+'/drive', json={'sha256':file['sha256'],'confirm_upload':True})
    assert result.status_code == 503
    assert client.get(file['url']).content == b'hello'


def test_upload_exact_content_and_no_retry_on_unknown(client, monkeypatch):
    monkeypatch.setenv('GIG_GOOGLE_CREDENTIALS_FILE', '/not-read-in-test')
    monkeypatch.setattr('gig_backend.documents.Credentials.from_authorized_user_file', lambda _: Mock(valid=True,token='fake'))
    file = client.post('/documents', json={'title':'test','format':'txt','text':'hello','consent':True}).json()
    path = '/documents/'+file['id']+'/drive'
    assert client.post(path,json={'sha256':'0'*64,'confirm_upload':True}).status_code == 409
    transport = Mock()
    transport.__enter__ = Mock(return_value=transport)
    transport.__exit__ = Mock(return_value=False)
    transport.post.side_effect = httpx.ReadTimeout('simulated timeout')
    monkeypatch.setattr('gig_backend.documents.httpx.Client', lambda **kwargs: transport)
    body = {'sha256':file['sha256'],'confirm_upload':True}
    assert client.post(path,json=body).status_code == 502
    assert client.post(path,json=body).status_code == 409
    assert transport.post.call_count == 1
    assert client.delete('/documents/'+file['id']).status_code == 409


def test_drive_success_is_private_and_idempotent(client, monkeypatch):
    monkeypatch.setenv('GIG_GOOGLE_CREDENTIALS_FILE', '/not-read-in-test')
    monkeypatch.setattr('gig_backend.documents.Credentials.from_authorized_user_file', lambda _: Mock(valid=True,token='fake'))
    transport = Mock()
    transport.__enter__ = Mock(return_value=transport)
    transport.__exit__ = Mock(return_value=False)
    transport.post.return_value.json.return_value = {'id':'test-file'}
    monkeypatch.setattr('gig_backend.documents.httpx.Client', lambda **kwargs: transport)
    file = client.post('/documents',json={'title':'test','format':'txt','text':'hello','consent':True}).json()
    body = {'sha256':file['sha256'],'confirm_upload':True}
    path = '/documents/'+file['id']+'/drive'
    response = client.post(path,json=body)
    assert response.json()['drive_url'] == 'https://drive.google.com/file/d/test-file/view'
    assert client.post(path,json=body).status_code == 200
    assert transport.post.call_count == 1
    assert b'permissions' not in transport.post.call_args.kwargs['content']


def test_auto_never_sends_to_cloud(client, monkeypatch):
    monkeypatch.delenv('GIG_MODEL', raising=False)
    monkeypatch.setenv('GIG_NVIDIA_API_KEY', 'fake-not-used')
    assert client.post('/ask',json={'text':'Explain gravity','model':'auto'}).status_code == 503


def test_scan_requires_frame(client):
    assert client.post('/ask',json={'text':'scan','model':'auto','operation':'scan'}).status_code == 400
