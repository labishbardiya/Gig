from fastapi.testclient import TestClient

from gig_backend.phone import create_phone_app


def paired(root):
    client = TestClient(create_phone_app(root), base_url='https://testserver')
    assert client.post('/pair', json={'code': (root / 'phone-pair-code').read_text().strip()}).status_code == 200
    return client


def test_calle_brief_is_gated_and_never_fakes_a_call(tmp_path, monkeypatch):
    client = paired(tmp_path)
    status = client.get('/calls/status').json()
    assert status['configured'] is False and status['ready'] is False
    brief = {'phone': '+919876543210', 'on_behalf_of': 'Labish', 'purpose': 'Confirm meeting time',
             'approved_context': 'Project meeting only', 'boundaries': 'Do not make commitments.'}
    proposal = client.post('/calls', json=brief).json()
    assert proposal['state'] == 'awaiting_approval'
    assert client.post('/calls/' + proposal['id'] + '/approve',
                       json={'sha256': '0' * 64, 'confirm': 'PLACE THIS CALL'}).status_code == 409
    result = client.post('/calls/' + proposal['id'] + '/approve',
                         json={'sha256': proposal['sha256'], 'confirm': 'PLACE THIS CALL'})
    assert result.status_code == 503
    monkeypatch.setenv('CALL_E_API_KEY', 'not-a-real-key')
    assert paired(tmp_path / 'second').get('/calls/status').json()['configured'] is True


def test_calle_requires_pairing_and_valid_number(tmp_path):
    raw = TestClient(create_phone_app(tmp_path), base_url='https://testserver')
    assert raw.get('/calls/status').status_code == 401
    client = paired(tmp_path)
    assert client.post('/calls', json={'phone': '98765', 'on_behalf_of': 'A', 'purpose': 'x', 'boundaries': 'x'}).status_code == 422
