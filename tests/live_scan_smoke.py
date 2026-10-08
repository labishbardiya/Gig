"""Explicit opt-in local vision smoke test; never captures the user's camera.

Run: GIG_VISION_MODEL=qwen2.5vl:3b .venv/bin/python tests/live_scan_smoke.py
Uses a synthetic page and a temporary database, not the user's saved documents.
"""
import base64
import io
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw, ImageFont
from fastapi.testclient import TestClient
from gig_backend.phone import create_phone_app

image = Image.new('RGB', (1000, 700), 'white')
draw = ImageDraw.Draw(image)
font_path = '/System/Library/Fonts/Supplemental/Arial.ttf'
font = ImageFont.truetype(font_path, 44) if Path(font_path).exists() else ImageFont.load_default(size=44)
draw.multiline_text((60, 70), 'GIG TEST DOCUMENT\nMeeting: Friday at 2 PM\nBring the prototype.\nReference: 4821', font=font, fill='black', spacing=28)
buffer = io.BytesIO()
image.save(buffer, 'JPEG', quality=92)
encoded = 'data:image/jpeg;base64,' + base64.b64encode(buffer.getvalue()).decode()
with tempfile.TemporaryDirectory(prefix='gig-scan-smoke-') as root:
    client = TestClient(create_phone_app(root), base_url='https://testserver')
    client.post('/pair', json={'code': (Path(root)/'phone-pair-code').read_text().strip()})
    started = time.perf_counter()
    result = client.post('/ask', json={'model':'local', 'text':'Transcribe this page.', 'operation':'scan', 'image':encoded})
    result.raise_for_status()
    answer = result.json()
    file = client.post('/documents', json={'title':'Synthetic smoke test','format':'pdf','image':encoded,'consent':True}).json()
    pdf = client.get(file['url'])
    assert pdf.content.startswith(b'%PDF')
    print(json.dumps({'synthetic_test':True, 'model':__import__('os').getenv('GIG_VISION_MODEL'),
        'transcription':answer['answer'], 'model_request_ms':answer['model_request_ms'],
        'scan_save_download_ms':round((time.perf_counter()-started)*1000), 'pdf_bytes':len(pdf.content),
        'reference_preserved':'4821' in answer['answer'],
        'scope':'single Mac localhost smoke test; excludes phone, Wi-Fi, speech and RTX'}, indent=2))
