import httpx
from fastapi.testclient import TestClient

from gig_backend.call_e_phone import CallEProvider, RESULT_SCHEMA
from gig_backend.phone import create_phone_app


BRIEF = {'phone': '+919876543210', 'on_behalf_of': 'Labish', 'purpose': 'Confirm meeting time',
         'approved_context': 'Project meeting only', 'boundaries': 'Do not make commitments.'}


def paired(root):
    client = TestClient(create_phone_app(root), base_url='https://testserver')
    assert client.post('/pair', json={'code': (root / 'phone-pair-code').read_text().strip()}).status_code == 200
    return client


def test_calle_provider_uses_official_v2_contract(monkeypatch):
    captured = []

    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs['trust_env'] is False
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def post(self, url, *, headers, json):
            captured.append(('post', url, headers, json))
            return httpx.Response(202, json={'id': 'call_123', 'status': 'queued', 'result_status': 'pending'})
        def get(self, url, *, headers):
            captured.append(('get', url, headers, None))
            request = httpx.Request('GET', url)
            return httpx.Response(200, request=request, json={'id': 'call_123', 'status': 'completed',
                'call_outcome': 'completed', 'result_status': 'available',
                'result': {'goal_completed': True, 'summary': 'Confirmed', 'follow_up_required': False}})

    monkeypatch.setattr('gig_backend.call_e_phone.httpx.Client', FakeClient)
    provider = CallEProvider(key='test-key', base_url='https://test-api.heycall-e.com')
    ident, _ = provider.create(BRIEF, 'action-1')
    resource = provider.get(ident)
    method, url, headers, body = captured[0]
    assert method == 'post' and url == 'https://test-api.heycall-e.com/v2/calls'
    assert headers['Authorization'] == 'Bearer test-key'
    assert headers['Idempotency-Key'] == 'gig-call-action-1'
    assert body['phone'] == BRIEF['phone'] and body['locale'] == 'en'
    assert body['result_schema'] == RESULT_SCHEMA
    assert body['result_schema']['additionalProperties'] is False
    assert 'AI assistant calling on behalf of Labish' in body['task']
    assert 'Do not make commitments.' in body['task']
    assert captured[1][0] == 'get' and captured[1][1].endswith('/v2/calls/call_123')
    assert resource['result']['summary'] == 'Confirmed'


def test_calle_brief_is_approval_gated_and_polls_only_after_submission(tmp_path, monkeypatch):
    client = paired(tmp_path)
    status = client.get('/calls/status').json()
    assert status['configured'] is False and status['ready'] is False
    proposal = client.post('/calls', json=BRIEF).json()
    assert proposal['state'] == 'awaiting_approval'
    assert client.post('/calls/' + proposal['id'] + '/approve',
                       json={'sha256': '0' * 64, 'confirm': 'PLACE THIS CALL'}).status_code == 409
    assert client.post('/calls/' + proposal['id'] + '/approve',
                       json={'sha256': proposal['sha256'], 'confirm': 'PLACE THIS CALL'}).status_code == 503
    # No configured provider means this remains a proposal, not an unknown attempt.
    assert client.get('/calls/' + proposal['id']).json()['state'] == 'awaiting_approval'

    monkeypatch.setenv('CALLE_API_KEY', 'test-key')
    monkeypatch.setattr(CallEProvider, 'create', lambda self, brief, action_id: ('call_123', {
        'id': 'call_123', 'status': 'queued', 'result_status': 'pending'}))
    monkeypatch.setattr(CallEProvider, 'get', lambda self, call_id: {
        'id': call_id, 'status': 'completed', 'call_outcome': 'completed', 'result_status': 'available',
        'result': {'goal_completed': True, 'summary': 'Confirmed', 'follow_up_required': False}})
    result = client.post('/calls/' + proposal['id'] + '/approve',
                         json={'sha256': proposal['sha256'], 'confirm': 'PLACE THIS CALL'})
    assert result.status_code == 200 and result.json()['state'] == 'pending'
    polled = client.get('/calls/' + proposal['id']).json()
    assert polled['state'] == 'complete' and polled['result']['goal_completed'] is True
    # Terminal result is cached; re-reading does not invoke provider polling again.
    assert client.get('/calls/' + proposal['id']).json()['state'] == 'complete'


def test_calle_requires_pairing_and_valid_number_and_legacy_key(tmp_path, monkeypatch):
    raw = TestClient(create_phone_app(tmp_path), base_url='https://testserver')
    assert raw.get('/calls/status').status_code == 401
    client = paired(tmp_path)
    assert client.post('/calls', json={'phone': '98765', 'on_behalf_of': 'A', 'purpose': 'x', 'boundaries': 'x'}).status_code == 422
    monkeypatch.setenv('CALL_E_API_KEY', 'legacy-test-key')
    assert client.get('/calls/status').json()['configured'] is True
