from fastapi.testclient import TestClient
from gig_backend.phone import create_phone_app
from gig_backend.speech import SynthesisResult


def test_pairing_and_no_model(tmp_path, monkeypatch):
    monkeypatch.delenv('GIG_MODEL', raising=False)
    monkeypatch.delenv('GIG_VISION_MODEL', raising=False)
    monkeypatch.delenv('GIG_NVIDIA_API_KEY', raising=False)
    client = TestClient(create_phone_app(tmp_path), base_url='https://testserver')
    assert client.get('/').status_code == 200
    assert client.get('/status').status_code == 401
    assert client.post('/pair', json={'code': 'wrong'}).status_code == 422
    wrong = '999999' if (tmp_path / 'phone-pair-code').read_text().strip() != '999999' else '000000'
    assert client.post('/pair', json={'code': wrong}).status_code == 401
    code = (tmp_path / 'phone-pair-code').read_text().strip()
    assert client.post('/pair', json={'code': code}).json() == {'paired': True}
    assert client.get('/status').json()['paired'] is True
    response = client.post('/ask', json={'text': 'Explain gravity', 'model': 'auto'})
    assert response.status_code == 503
    assert 'No model configured' in response.json()['detail']


def test_public_demo_mints_anonymous_session_but_blocks_operator_data(tmp_path, monkeypatch):
    monkeypatch.setenv('GIG_PUBLIC_DEMO', '1')
    client = TestClient(create_phone_app(tmp_path), base_url='https://demo.example')
    status = client.get('/status')
    assert status.status_code == 200
    assert status.json()['paired'] is True and status.json()['public_demo'] is True
    assert client.cookies.get('gig_phone')
    assert client.get('/chats').status_code == 403
    assert client.get('/documents').status_code == 403
    assert client.get('/google/status').status_code == 403
    assert client.get('/calls/status').status_code == 403
    # Anonymous visitors can still ask a non-persistent question. The built-in
    # greeting is intentionally available without loading a model.
    assert client.post('/ask', json={'text': 'hello', 'model': 'auto'}).status_code == 200
    assert client.post('/ask', json={'text': 'hello', 'model': 'kimi'}).status_code == 403
    assert client.post('/forget').json() == {'forgotten': True}
    # A subsequent request receives a fresh anonymous demo session rather than
    # ever exposing the operator workspace.
    assert client.get('/status').json()['public_demo'] is True


def test_rejects_invalid_frame(tmp_path, monkeypatch):
    monkeypatch.setenv('GIG_MODEL', 'test')
    client = TestClient(create_phone_app(tmp_path), base_url='https://testserver')
    code = (tmp_path / 'phone-pair-code').read_text().strip()
    client.post('/pair', json={'code': code})
    result = client.post('/ask', json={'text': 'Look', 'model': 'auto', 'image': 'data:image/jpeg;base64,not-base64'})
    assert result.status_code == 400


def test_speech_reports_backend_timing_only(tmp_path, monkeypatch):
    monkeypatch.setattr('gig_backend.phone.synthesize_with_metrics',
                        lambda text, root: SynthesisResult(b'RIFF0000WAVEdata', 12.5, 'test-tts'))
    client = TestClient(create_phone_app(tmp_path), base_url='https://testserver')
    client.post('/pair', json={'code': (tmp_path / 'phone-pair-code').read_text().strip()})
    result = client.post('/speech', json={'text': 'Hello'})
    assert result.status_code == 200
    assert result.headers['x-gig-tts-ms'] == '12.5'
    assert result.headers['x-gig-tts-provider'] == 'test-tts'
    assert result.headers['server-timing'] == 'gig-tts;dur=12.5'
