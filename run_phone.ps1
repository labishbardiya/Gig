$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'Install uv first, then reopen this terminal.'
}
if (-not $env:GIG_MODEL) { $env:GIG_MODEL = 'qwen3:4b' }
if (-not $env:GIG_VISION_MODEL) { $env:GIG_VISION_MODEL = 'qwen2.5vl:3b' }
uv sync --frozen --python 3.13
if ($LASTEXITCODE -ne 0) { throw 'Dependency setup failed.' }
uv run python -m uvicorn gig_backend.phone:create_phone_app --factory --host 127.0.0.1 --port 8767 --no-access-log
