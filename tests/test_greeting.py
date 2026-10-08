from fastapi.testclient import TestClient
from gig_backend.phone import create_phone_app

def test_greeting_without_inference(tmp_path, monkeypatch):
    monkeypatch.delenv('GIG_MODEL', raising=False)
    client = TestClient(create_phone_app(tmp_path), base_url='https://testserver')
    client.post('/pair',json={'code':(tmp_path/'phone-pair-code').read_text().strip()})
    reply = client.post('/ask',json={'text':'Hi!', 'model':'auto'})
    assert reply.status_code == 200
    assert reply.json()['model'] == 'local greeting'
    assert reply.json()['model_request_ms'] == 0
