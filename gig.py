"""One entry point for local diagnostics, startup and phone publishing."""
import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx
from gig_backend.config import load_project_env

ROOT = Path(__file__).resolve().parent


def gateway_ready(client, base):
    try:
        response = client.get(base + '/health')
        return response.status_code == 200 and response.json().get('scope') == 'phone gateway only'
    except (httpx.HTTPError, ValueError):
        return False


def local_tunnel(client, port):
    try:
        response = client.get('http://127.0.0.1:4040/api/tunnels')
        response.raise_for_status()
        for item in response.json().get('tunnels', []):
            address = str(item.get('config', {}).get('addr', '')).rstrip('/')
            if address in {str(port), f'http://localhost:{port}', f'http://127.0.0.1:{port}'}:
                if item.get('public_url', '').startswith('https://'):
                    return item['public_url']
    except (httpx.HTTPError, ValueError):
        pass
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['doctor', 'start', 'share'])
    args = parser.parse_args()
    load_project_env()
    port = int(os.environ.get('GIG_PHONE_PORT', '8767'))
    base = f'http://127.0.0.1:{port}'
    with httpx.Client(timeout=3, trust_env=False) as client:
        ready = gateway_ready(client, base)
        if args.command == 'doctor':
            print('Phone gateway: ' + ('reachable' if ready else 'not running'))
            print('Local address: ' + base)
            print('Local tunnel: ' + (local_tunnel(client, port) or 'not discoverable on port 4040'))
            credentials = os.environ.get('GIG_GOOGLE_CREDENTIALS_FILE', '')
            print('Google token: ' + ('file present; live authorization unverified' if credentials and Path(credentials).is_file() else 'not configured (optional)'))
            return 0 if ready else 1
        if args.command == 'start':
            if ready:
                print(f'GIG is already running at {base}. Reusing it; source updates require restarting its existing terminal.')
                return 0
            return subprocess.call([sys.executable, str(ROOT / 'run_harness.py')], cwd=ROOT)
        if not ready:
            print('Start GIG first in another terminal: python gig.py start')
            return 1
        existing = local_tunnel(client, port)
        if existing:
            print('Open on your phone: ' + existing)
            return 0
        binary = shutil.which('ngrok')
        if not binary:
            print('ngrok is not installed or not on PATH.')
            return 1
        # Only manage the child created here; never terminate unrelated tunnels.
        proc = subprocess.Popen([binary, 'http', base], cwd=ROOT)
        try:
            while proc.poll() is None:
                time.sleep(.5)
            if proc.returncode:
                print('If ngrok reports ERR_NGROK_334, an existing agent owns your endpoint. Inspect https://dashboard.ngrok.com/agents and stop only that old session, or reuse it if it forwards to this Mac. Retrying or pooling does not repair the wrong upstream.')
            return proc.returncode
        except KeyboardInterrupt:
            return 0
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()


if __name__ == '__main__':
    raise SystemExit(main())
