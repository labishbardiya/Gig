$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path '.venv-tts\Scripts\python.exe')) {
    uv venv --python 3.11 .venv-tts
    if ($LASTEXITCODE -ne 0) { throw 'Environment setup failed' }
    uv pip install --python .venv-tts\Scripts\python.exe 'torch==2.6.0' 'torchaudio==2.6.0' --index-url https://download.pytorch.org/whl/cu124
    if ($LASTEXITCODE -ne 0) { throw 'CUDA package installation failed' }
}
uv pip install --python .venv-tts\Scripts\python.exe 'chatterbox-tts @ git+https://github.com/resemble-ai/chatterbox.git@5de7a54aa4e5e2baadb0182dde554908b48b85c2' 'fastapi>=0.115,<1' 'uvicorn>=0.30,<1' soundfile
if ($LASTEXITCODE -ne 0) { throw 'TTS dependencies failed; do not change the main environment' }
& .venv-tts\Scripts\python.exe -m uvicorn voice_local.server:app --host 127.0.0.1 --port 8768 --no-access-log
