from unittest.mock import Mock

from gig_backend.google_verify import private_drive_probe


def test_drive_probe_is_private_and_small(monkeypatch):
    transport = Mock()
    transport.__enter__ = Mock(return_value=transport)
    transport.__exit__ = Mock(return_value=False)
    transport.post.return_value.json.return_value = {'id': 'private-test-id', 'name': 'GIG-private-verification-test.txt'}
    monkeypatch.setattr('gig_backend.google_verify.httpx.Client', lambda **kwargs: transport)
    credentials = Mock(token='token')
    result = private_drive_probe(credentials, now=1)
    assert result['private'] is True and result['id'] == 'private-test-id'
    request = transport.post.call_args
    assert b'Safe to delete' in request.kwargs['content']
    assert b'permissions' not in request.kwargs['content']
    assert request.kwargs['params']['fields'] == 'id,name,webViewLink'
