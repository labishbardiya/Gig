from types import SimpleNamespace
import httpx
import pytest
from fastapi.testclient import TestClient
from gig_backend.agent import LocalAgent
from gig_backend.api import create_app


@pytest.mark.parametrize('url', ['http://pc:11434', 'https://user:secret@pc', 'file:///tmp/model', 'https://pc/path', 'https://pc?key=secret'])
def test_unsafe_model_origin_rejected(url):
    with pytest.raises(ValueError):
        LocalAgent('test', url)


def test_remote_model_and_inventory(monkeypatch):
    class Client:
        def __init__(self, **kwargs):
            assert kwargs['trust_env'] is False
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def get(self, url):
            assert url == 'https://inference.example/api/tags'
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {'models': [{'name': 'fixture:latest'}]})
        def post(self, url, json):
            assert url == 'https://inference.example/api/chat'
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {'message': {'content': 'Fixture only'}})
    monkeypatch.setattr('gig_backend.agent.httpx.Client', Client)
    agent = LocalAgent('fixture', 'https://inference.example')
    assert agent.readiness()['ready']
    assert agent.run([{'role': 'user', 'content': 'test'}])['answer'] == 'Fixture only'


def test_readiness_requires_auth_and_does_not_infer(tmp_path):
    app = create_app(tmp_path, 'test-token', agent=LocalAgent('', 'http://127.0.0.1:11434'))
    with TestClient(app) as client:
        assert client.get('/v1/readiness').status_code == 401
        result = client.get('/v1/readiness', headers={'Authorization': 'Bearer test-token'})
        assert result.json()['model'] == {'ready': False, 'reason': 'model_not_configured'}
    app.state.store.db.close()


def test_timeout_is_not_ready(monkeypatch):
    def fail(*args, **kwargs):
        raise httpx.ConnectError('private details')
    monkeypatch.setattr(httpx.Client, 'get', fail)
    assert LocalAgent('fixture').readiness() == {'ready': False, 'reason': 'model_service_unavailable'}
