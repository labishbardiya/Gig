$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
uv sync --frozen --extra voice --python 3.13
if ($LASTEXITCODE -ne 0) { throw 'Voice dependency installation failed.' }
$env:GIG_ENABLE_LIVE_VOICE = '1'
$env:GIG_MODEL = 'qwen3:4b'
$env:GIG_VISION_MODEL = 'qwen2.5vl:3b'
$env:GIG_STT_MODEL = 'base'
$env:GIG_STT_DEVICE = 'cpu'
$env:GIG_STT_COMPUTE = 'int8'
uv run --extra voice python voice_preflight.py
if ($LASTEXITCODE -ne 0) { throw 'Voice preflight failed. Resolve the printed issue first.' }
uv run --extra voice python -m uvicorn gig_backend.phone:create_phone_app --factory --host 127.0.0.1 --port 8767 --no-access-log
