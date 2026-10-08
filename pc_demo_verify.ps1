$ErrorActionPreference = 'Stop'

Write-Host 'GIG local health:' -ForegroundColor Cyan
curl.exe --fail --silent http://127.0.0.1:8767/health
Write-Host ''

Write-Host 'Private process ports:' -ForegroundColor Cyan
Get-NetTCPConnection -State Listen -LocalPort 8767,18789,11434 -ErrorAction SilentlyContinue |
    Select-Object LocalAddress,LocalPort,OwningProcess

Write-Host 'Loaded Ollama models (empty before first request is normal):' -ForegroundColor Cyan
ollama ps
