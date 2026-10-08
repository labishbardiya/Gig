"""Start the private OpenClaw gateway and paired GIG phone server together.

Run from an installed GIG Python environment. The operator token stays in
process memory and is passed only to the two local child processes.
"""
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx
from gig_backend.config import load_project_env


ROOT = Path(__file__).resolve().parent
GATEWAY = ROOT / 'vendor/openclaw-runtime/node_modules/openclaw/openclaw.mjs'
CONFIG = ROOT / 'openclaw/openclaw.json'
STATE = ROOT / 'data/openclaw-state'


def check_inventory():
    if not shutil.which('node'):
        raise RuntimeError('Install Node 26.1+ or 24.16+ on this computer')
    if not GATEWAY.is_file():
        raise RuntimeError('Install pinned OpenClaw: npm install --prefix vendor/openclaw-runtime --ignore-scripts --save-exact openclaw@2026.9.8')
    with httpx.Client(timeout=5, trust_env=False) as client:
        data = client.get('http://127.0.0.1:11434/api/tags').json()
    models = {entry.get('name') for entry in data.get('models', [])}
    if 'qwen3:4b' not in models:
        raise RuntimeError('Local text model missing: ollama pull qwen3:4b')


def materialize_config():
    template = json.loads(CONFIG.read_text())
    STATE.mkdir(parents=True, exist_ok=True)
    (STATE / 'workspace').mkdir(exist_ok=True)
    template['agents']['defaults']['workspace'] = str(STATE / 'workspace')
    (STATE / 'phone').mkdir(exist_ok=True)
    path = STATE / 'openclaw.json'
    path.write_text(json.dumps(template, indent=2))
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def main():
    load_project_env()
    check_inventory()
    config = materialize_config()
    token = secrets.token_urlsafe(48)
    env = dict(os.environ,
               OPENCLAW_CONFIG_PATH=str(config),
               OPENCLAW_STATE_DIR=str(STATE),
               OPENCLAW_GATEWAY_TOKEN=token,
               OLLAMA_API_KEY='ollama-local',
               GIG_OPENCLAW_URL='http://127.0.0.1:18789',
               GIG_OPENCLAW_TOKEN=token,
               GIG_OPENCLAW_ENABLE='1',
               GIG_DATA_DIR=str(STATE / 'phone'),
               GIG_MODEL=os.environ.get('GIG_MODEL', 'qwen3:4b'),
               GIG_VISION_MODEL=os.environ.get('GIG_VISION_MODEL', 'qwen2.5vl:3b'))
    gateway = subprocess.Popen(['node', str(GATEWAY), 'gateway', 'run'], cwd=ROOT, env=env)
    phone = None
    try:
        with httpx.Client(timeout=2, trust_env=False) as client:
            for _ in range(40):
                if gateway.poll() is not None:
                    raise RuntimeError('OpenClaw exited during startup; inspect the console above')
                try:
                    result = client.get('http://127.0.0.1:18789/v1/models',
                                        headers={'Authorization': 'Bearer ' + token})
                    if result.status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(.5)
            else:
                raise RuntimeError('OpenClaw did not become ready on loopback port 18789')
        port = os.environ.get('GIG_PHONE_PORT', '8767')
        phone = subprocess.Popen([sys.executable, '-m', 'uvicorn',
                                  'gig_backend.phone:create_phone_app', '--factory',
                                  '--host', '127.0.0.1', '--port', port, '--no-access-log'],
                                 cwd=ROOT, env=env)
        print(f'GIG phone app: http://127.0.0.1:{port}/', flush=True)
        print('OpenClaw: restricted operator gateway on loopback. Pairing code is in data/openclaw-state/phone/phone-pair-code.', flush=True)
        try:
            while gateway.poll() is None and phone.poll() is None:
                time.sleep(1)
            return 1
        except KeyboardInterrupt:
            return 0
    finally:
        for proc in (phone, gateway):
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, httpx.HTTPError, ValueError) as error:
        print('Startup failed:', error, file=sys.stderr)
        raise SystemExit(1)
