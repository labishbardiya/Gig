import httpx
from gig import gateway_ready, local_tunnel


def client_for(payload, status=200):
    return httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(status, json=payload)))


def test_other_service_is_not_gig():
    with client_for({'status': 'ok'}) as client:
        assert not gateway_ready(client, 'http://127.0.0.1:8767')


def test_only_matching_https_tunnel_is_reused():
    with client_for({'tunnels': [
        {'public_url': 'https://wrong.example', 'config': {'addr': 'http://localhost:8000'}},
        {'public_url': 'https://right.example', 'config': {'addr': 'http://127.0.0.1:8767'}},
    ]}) as client:
        assert local_tunnel(client, 8767) == 'https://right.example'


def test_unavailable_inspection_does_not_crash():
    with client_for({}, 503) as client:
        assert local_tunnel(client, 8767) is None
