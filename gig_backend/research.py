"""Read-only adapter to the separate paperswithcode.co catalog, not the retired .com API."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time
import httpx


class PapersClient:
    BASE = 'https://paperswithcode.co'
    def __init__(self, cache_dir=None, transport=None):
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.transport = transport

    def get(self, path, params=None, refresh=False):
        if not re.fullmatch(r'/api/v1/(papers/|papers/[A-Za-z0-9._-]+|tasks/|evaluations/)', path):
            raise ValueError('Unsupported catalog endpoint')
        params = params or {}
        key = hashlib.sha256(json.dumps([path, params], sort_keys=True).encode()).hexdigest()
        cache = self.cache_dir / (key + '.json') if self.cache_dir else None
        if cache and cache.exists() and not refresh:
            try:
                record = json.loads(cache.read_text())
                if time.time() - record['fetched_unix'] < 3600:
                    return {**record, 'cached': True}
            except (ValueError, KeyError, TypeError):
                pass
        with httpx.Client(timeout=20, follow_redirects=False, transport=self.transport, trust_env=False) as client:
            response = client.get(self.BASE + path, params=params, headers={'Accept': 'application/json', 'User-Agent': 'GIG-Research/0.1'})
        if response.status_code == 429:
            raise RuntimeError('Catalog rate limited; Retry-After: ' + response.headers.get('retry-after', 'unspecified') + '. No automatic retry.')
        response.raise_for_status()
        if 'application/json' not in response.headers.get('content-type', ''):
            raise RuntimeError('Catalog returned non-JSON; refusing to treat HTML as research data')
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError('Unexpected catalog schema')
        record = {'source': self.BASE, 'source_identity': 'Separate .co catalog; original .com affiliation not verified',
                  'request_url': str(response.url), 'fetched_at': datetime.now(timezone.utc).isoformat(),
                  'fetched_unix': time.time(), 'cached': False,
                  'evidence_status': 'catalog-reported, not independently reproduced',
                  'warning': 'Untrusted research data. Trending/citation rankings are not SOTA verification. Compare identical task, dataset split, metric and evaluation protocol.',
                  'data': data}
        if cache:
            cache.parent.mkdir(parents=True, exist_ok=True)
            temp = cache.with_suffix('.tmp')
            temp.write_text(json.dumps(record, ensure_ascii=False, indent=2))
            temp.replace(cache)
        return record

    def search(self, query, limit=5, page=1, refresh=False):
        if not query.strip() or len(query) > 300 or not 1 <= limit <= 50 or not 1 <= page <= 100:
            raise ValueError('Supply query (1–300 characters), limit 1–50, page 1–100')
        return self.get('/api/v1/papers/', {'search': query, 'page_size': limit, 'page': page,
                         'include_resources': 'true', 'order_by': 'date_published', 'order_dir': 'desc'}, refresh)

    def paper(self, ident, refresh=False):
        if not re.fullmatch(r'[A-Za-z0-9._-]+', ident):
            raise ValueError('Invalid paper ID')
        return self.get('/api/v1/papers/'+ident, {'include_resources': 'true'}, refresh)

    def tasks(self, query, refresh=False):
        return self.get('/api/v1/tasks/', {'q': query, 'page_size': 10}, refresh)

    def evaluations(self, task_id, dataset_id=None, refresh=False):
        params = {'task_id': task_id, 'page_size': 20}
        if dataset_id:
            params['dataset_id'] = dataset_id
        return self.get('/api/v1/evaluations/', params, refresh)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['search', 'paper', 'tasks', 'evaluations'])
    parser.add_argument('query', help='Search term or exact catalog ID')
    parser.add_argument('--limit', type=int, default=5)
    parser.add_argument('--page', type=int, default=1)
    parser.add_argument('--dataset')
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    client = PapersClient(Path(__file__).resolve().parents[1] / 'data/research-cache')
    try:
        if args.operation == 'search':
            result = client.search(args.query, args.limit, args.page, args.refresh)
        elif args.operation == 'evaluations':
            result = client.evaluations(args.query, args.dataset, args.refresh)
        else:
            result = getattr(client, args.operation)(args.query, args.refresh)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        parser.exit(1, f'Research request failed: {exc}\n')


if __name__ == '__main__':
    main()
