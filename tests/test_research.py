import httpx
import pytest
from gig_backend.research import PapersClient


def test_search_and_cache(tmp_path):
    requests = []
    def respond(request):
        requests.append(request)
        assert request.url.params['search'] == 'tool calling'
        return httpx.Response(200, json={'results': [{'title': 'Fixture'}], 'count': 1})
    client = PapersClient(tmp_path, httpx.MockTransport(respond))
    first = client.search('tool calling')
    assert first['evidence_status'].startswith('catalog-reported')
    assert client.search('tool calling')['cached']
    assert len(requests) == 1
    client.search('tool calling', refresh=True)
    assert len(requests) == 2


def test_html_rejected():
    client = PapersClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, text='<html>')))
    with pytest.raises(RuntimeError, match='non-JSON'):
        client.search('test')


def test_redirect_not_followed():
    client = PapersClient(transport=httpx.MockTransport(lambda r: httpx.Response(302, headers={'location': 'https://example.com'})))
    with pytest.raises(httpx.HTTPStatusError):
        client.search('test')


def test_rate_limit():
    client = PapersClient(transport=httpx.MockTransport(lambda r: httpx.Response(429, headers={'retry-after': '60'})))
    with pytest.raises(RuntimeError, match='60'):
        client.search('test')


def test_no_arbitrary_urls_or_paths():
    client = PapersClient()
    with pytest.raises(ValueError):
        client.get('http://localhost/private')
    with pytest.raises(ValueError):
        client.paper('../secret')
    with pytest.raises(ValueError):
        client.search('test', limit=999)
