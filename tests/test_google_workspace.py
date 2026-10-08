from fastapi.testclient import TestClient

from gig_backend.phone import create_phone_app
from gig_backend.google_workspace import GoogleWorkspace


def paired(root):
    client = TestClient(create_phone_app(root), base_url='https://testserver')
    assert client.post('/pair', json={'code': (root / 'phone-pair-code').read_text().strip()}).status_code == 200
    return client


def test_google_actions_are_paired_and_approval_gated(tmp_path):
    raw = TestClient(create_phone_app(tmp_path), base_url='https://testserver')
    assert raw.get('/google/status').status_code == 401
    client = paired(tmp_path)
    assert client.get('/google/status').json()['configured'] is False
    body = {'kind': 'gmail_draft', 'to': ['demo@example.com'], 'subject': 'GIG demo', 'body': 'Draft only'}
    proposal = client.post('/google/actions', json=body).json()
    assert proposal['state'] == 'awaiting_approval'
    assert client.post('/google/actions/' + proposal['id'] + '/approve',
                       json={'sha256': proposal['sha256'], 'confirm': 'wrong'}).status_code == 422
    result = client.post('/google/actions/' + proposal['id'] + '/approve',
                         json={'sha256': proposal['sha256'], 'confirm': 'CREATE GOOGLE ACTION'})
    assert result.status_code == 503


def test_google_prepare_validates_action_shape(tmp_path):
    client = paired(tmp_path)
    assert client.post('/google/actions', json={'kind': 'gmail_draft', 'to': ['not-an-email'], 'subject': '', 'body': ''}).status_code == 422
    assert client.post('/google/actions', json={'kind': 'calendar_event', 'title': 'Demo',
                                                  'start': '2026-10-08T12:00:00+05:30',
                                                  'end': '2026-10-08T11:00:00+05:30'}).status_code == 422


def test_google_approval_runs_only_exact_prepared_payload(tmp_path, monkeypatch):
    client = paired(tmp_path)
    prepared = client.post('/google/actions', json={'kind': 'calendar_event', 'title': 'GIG review',
                                                     'start': '2026-10-08T12:00:00+05:30',
                                                     'end': '2026-10-08T12:30:00+05:30'}).json()
    called = []
    monkeypatch.setattr(GoogleWorkspace, '_create_event', lambda self, payload: called.append(payload) or {'id': 'event-1', 'url': 'https://calendar.example/event-1'})
    result = client.post('/google/actions/' + prepared['id'] + '/approve',
                         json={'sha256': prepared['sha256'], 'confirm': 'CREATE GOOGLE ACTION'})
    assert result.status_code == 200
    assert result.json()['state'] == 'complete'
    assert called[0]['title'] == 'GIG review'
    assert client.post('/google/actions/' + prepared['id'] + '/approve',
                       json={'sha256': prepared['sha256'], 'confirm': 'CREATE GOOGLE ACTION'}).status_code == 409
