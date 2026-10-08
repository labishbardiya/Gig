import time

from fastapi.testclient import TestClient

from gig_backend.phone import create_phone_app
from gig_backend.workspace import Workspace, OpenClaw


def paired(root):
    client = TestClient(create_phone_app(root), base_url='https://testserver')
    code = (root / 'phone-pair-code').read_text().strip()
    assert client.post('/pair', json={'code': code}).status_code == 200
    return client


def test_persistent_chats_and_explicit_memory(tmp_path):
    client = paired(tmp_path)
    assert client.get('/chats').json() == []
    chat = client.post('/chats').json()
    ident = chat['id']
    assert client.post('/ask', json={'chat_id': ident, 'text': 'hello', 'model': 'auto'}).status_code == 200
    assert [x['role'] for x in client.get('/chats/' + ident).json()['messages']] == ['user', 'assistant']
    assert client.get('/chats').json()[0]['title'] == 'hello'
    assert client.patch('/chats/' + ident, json={'title': 'My project'}).status_code == 200
    memory = client.post('/memories', json={'text': 'Call me Labish'}).json()
    assert client.get('/memories').json()[0]['text'] == 'Call me Labish'
    assert client.patch('/memories/' + memory['id'], json={'text': 'Call me Labish Bardiya'}).status_code == 200
    assert len(client.get('/memories?q=Bardiya').json()) == 1
    assert client.get('/memories?q=unrelated').json() == []

    # A restart changes the pairing code and session, but does not erase the workspace.
    reopened = paired(tmp_path)
    assert reopened.get('/chats/' + ident).json()['title'] == 'My project'
    assert reopened.get('/memories').json()[0]['id'] == memory['id']
    assert reopened.delete('/memories/' + memory['id']).json()['deleted'] is True
    assert reopened.delete('/chats/' + ident).json()['deleted'] is True
    assert reopened.get('/chats/' + ident).status_code == 404


def test_runs_are_gated_and_not_duplicated(tmp_path, monkeypatch):
    monkeypatch.delenv('GIG_OPENCLAW_ENABLE', raising=False)
    monkeypatch.delenv('GIG_OPENCLAW_TOKEN', raising=False)
    client = paired(tmp_path)
    ident = client.post('/chats').json()['id']
    assert client.post('/chats/' + ident + '/runs', json={'text': 'find sources'}).status_code == 503
    monkeypatch.setenv('GIG_OPENCLAW_ENABLE', '1')
    monkeypatch.setenv('GIG_OPENCLAW_TOKEN', 'test-secret')
    monkeypatch.setattr(OpenClaw, 'healthy', lambda self: True)
    task = client.post('/chats/' + ident + '/runs', json={'text': 'find sources'}).json()
    assert task['state'] == 'awaiting_approval'
    assert client.post('/runs/' + task['id'] + '/reject').json()['rejected'] is True
    assert [event['phase'] for event in client.get('/runs/' + task['id'] + '/events').json()] == ['prepared', 'rejected']
    assert client.post('/runs/' + task['id'] + '/approve').status_code == 409
    assert client.get('/runs').json()[0]['state'] == 'rejected'


def test_unauthenticated_workspace_and_interrupted_run(tmp_path):
    raw = TestClient(create_phone_app(tmp_path), base_url='https://testserver')
    for route in ('/chats', '/memories', '/runs', '/harness/status'):
        assert raw.get(route).status_code == 401
    store = Workspace(tmp_path)
    chat = store.create()
    store.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?)',
                  ('run', chat['id'], 'running', 'a task', '', time.time()-100, time.time()-100))
    reopened = Workspace(tmp_path)
    assert reopened.rows('SELECT state FROM runs WHERE id=?', ('run',))[0]['state'] == 'interrupted'


def test_local_browser_pair_cookie_works_without_https(tmp_path):
    client = TestClient(create_phone_app(tmp_path), base_url='http://127.0.0.1')
    code = (tmp_path / 'phone-pair-code').read_text().strip()
    assert client.post('/pair', json={'code': code}).status_code == 200
    assert client.get('/chats').status_code == 200


def test_semantic_memory_prefers_local_embedding_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv('GIG_SEMANTIC_MEMORY', '1')
    store = Workspace(tmp_path)
    def fake_embed(text):
        return ('qwen3-embedding:0.6b', [1, 0, 0] if 'project' in text else [0, 1, 0])
    monkeypatch.setattr(Workspace, '_embed', lambda self, text: fake_embed(text))
    chat = store.create()
    client = paired(tmp_path)
    first = client.post('/memories', json={'text':'My GIG project uses an RTX PC'}).json()
    second = client.post('/memories', json={'text':'I prefer concise responses'}).json()
    # Directly prove the retrieval/index invariants on the same persistent database.
    store.execute('INSERT INTO memories VALUES(?,?,?)', ('a', 'My GIG project uses an RTX PC', time.time()))
    store.execute('INSERT INTO memories VALUES(?,?,?)', ('b', 'I prefer concise responses', time.time()))
    assert store.index_memory('a', 'My GIG project uses an RTX PC') is True
    assert store.index_memory('b', 'I prefer concise responses') is True
    assert store.memory_context('Tell me about my project').split('\n')[0] == 'My GIG project uses an RTX PC'
    assert first['semantic_indexed'] is True and second['semantic_indexed'] is True
    assert chat['id']
