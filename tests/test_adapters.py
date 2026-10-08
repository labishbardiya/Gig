import json
from types import SimpleNamespace
from gig_backend.calle import Calle
from gig_backend.agent import LocalAgent


def test_calle_invocation_is_json_not_shell(tmp_path, monkeypatch):
    (tmp_path/'package.json').write_text(json.dumps({'name': '@call-e/cli', 'bin': {'calle': 'bin/calle.js'}}))
    def run(argv, **kwargs):
        assert kwargs['shell'] is False
        assert argv == ['/trusted/node', '/trusted/launcher.mjs']
        body = json.loads(kwargs['input'])
        assert body['argv'] == ['auth', 'status']
        assert body['integration']['source'] == 'skills_sh'
        return SimpleNamespace(returncode=0, stdout='{"usable":true}')
    monkeypatch.setattr('gig_backend.calle.subprocess.run', run)
    assert Calle(str(tmp_path), '/trusted/launcher.mjs', '/trusted/node').ready()


def test_call_instructions_and_result_shape(monkeypatch):
    cli = Calle('', '', '')
    def invoke(argv):
        assert argv[:2] == ['call', 'start']
        goal = argv[argv.index('--goal')+1]
        assert 'AI assistant' in goal and 'Disclose' in goal
        assert 'Only ask opening hours' in goal
        return {'run_id': 'known', 'status_result': {'structuredContent': {'status': 'RUNNING'}}}
    monkeypatch.setattr(cli, 'invoke', invoke)
    ident, result = cli.start({'phone': '+12025550123', 'on_behalf_of': 'Tester', 'goal': 'Opening hours', 'context': '', 'boundaries': 'Only ask opening hours', 'language': 'English', 'region': 'US'})
    assert ident == 'known' and result['untrusted_call_data']


def test_actual_graph_with_mocked_http(monkeypatch):
    class Client:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def post(self, url, json):
            assert json['model'] == 'fixture-model'
            assert 'no action tools' in json['messages'][0]['content']
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {'message': {'content': 'Hello'}})
    monkeypatch.setattr('gig_backend.agent.httpx.Client', Client)
    result = LocalAgent('fixture-model').run([{'role': 'user', 'content': 'Hi'}])
    assert result['answer'] == 'Hello'
    assert result['elapsed_ms'] >= 0
