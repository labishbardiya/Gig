"""Check imports and local prerequisites; download only the selected speech model."""
import os
from pathlib import Path
import httpx
from faster_whisper import WhisperModel
from gig_backend.speech import api_key
from gig_backend.phone import create_phone_app

if __name__ == '__main__':
    root = Path(__file__).resolve().parent/'data'
    if not api_key(root):
        raise SystemExit('Run: uv run python setup_fish.py (key entry is hidden).')
    try:
        models = httpx.get('http://127.0.0.1:11434/api/tags', timeout=10).json()['models']
        wanted = os.getenv('GIG_MODEL','qwen3:4b')
        if wanted not in [m['name'] for m in models]:
            raise SystemExit('Missing dialogue model. Run: ollama pull '+wanted)
    except httpx.HTTPError:
        raise SystemExit('Start Ollama on the PC, then retry.')
    print('Loading local speech recognition; first run downloads model weights.')
    WhisperModel(os.getenv('GIG_STT_MODEL','base'), device=os.getenv('GIG_STT_DEVICE','cpu'),
                 compute_type=os.getenv('GIG_STT_COMPUTE','int8'))
    # Use a temporary app directory so checking imports does not rotate the live pairing code.
    import tempfile
    os.environ['GIG_ENABLE_LIVE_VOICE']='1'
    with tempfile.TemporaryDirectory(prefix='gig-preflight-') as temp:
        create_phone_app(temp)
    print('Imports, Ollama model inventory and speech model load passed. No inference or Fish request made.')
