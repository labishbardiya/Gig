"""Isolated local gateway and model smoke test; keeps the operator token in memory."""
import os
import secrets
import subprocess
import time
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parents[1]


def main():
    secret = secrets.token_urlsafe(32)
    env = dict(os.environ,
               OPENCLAW_CONFIG_PATH=str(ROOT / 'openclaw/openclaw.json'),
               OPENCLAW_STATE_DIR=str(ROOT / 'data/openclaw-state'),
               OPENCLAW_GATEWAY_TOKEN=secret,
               OLLAMA_API_KEY='ollama-local')
    proc = subprocess.Popen(
        ['node', str(ROOT / 'vendor/openclaw-runtime/node_modules/openclaw/openclaw.mjs'), 'gateway', 'run'],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
    try:
        with httpx.Client(trust_env=False) as client:
            for _ in range(40):
                if proc.poll() is not None:
                    raise RuntimeError('Gateway exited before ready')
                try:
                    response = client.get('http://127.0.0.1:18789/v1/models',
                                          headers={'Authorization': 'Bearer ' + secret}, timeout=2)
                    if response.status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(.4)
            else:
                raise RuntimeError('Gateway did not become ready')
            started = time.perf_counter()
            response = client.post('http://127.0.0.1:18789/v1/chat/completions',
                                   headers={'Authorization': 'Bearer ' + secret},
                                   json={'model': 'openclaw:gig', 'stream': False,
                                         'messages': [{'role': 'user', 'content': 'Reply briefly: GIG ready'}]},
                                   timeout=90)
            print('Gateway model request:', response.status_code,
                  'wall seconds:', round(time.perf_counter() - started, 2))
            if response.status_code == 200:
                print('Reply:', str(response.json()['choices'][0]['message'].get('content', ''))[:200])
            else:
                print('Error type:', response.json().get('error', {}).get('type', 'unknown'))
            return 0 if response.status_code == 200 else 1
    finally:
        proc.terminate()
        try:
            output, _ = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            output, _ = proc.communicate()
        lines = [line for line in output.splitlines() if 'error' in line.lower() or 'fail' in line.lower()]
        if lines:
            print('Gateway diagnostic:', '\n'.join(lines[-3:])[-1200:])


if __name__ == '__main__':
    raise SystemExit(main())
