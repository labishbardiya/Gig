$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

function Require-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Missing $Name. Install it, reopen PowerShell, then retry."
    }
}

Require-Command 'uv'
Require-Command 'ollama'
Require-Command 'node'

Write-Host 'Checking GPU...' -ForegroundColor Cyan
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader

$required = @('qwen3:4b', 'qwen2.5vl:3b', 'qwen3-embedding:0.6b')
$available = @((ollama list | Select-Object -Skip 1 | ForEach-Object { ($_ -split '\s+')[0] }))
foreach ($model in $required) {
    if ($available -notcontains $model) {
        $answer = Read-Host "$model is missing. Download now? [y/N]"
        if ($answer -match '^(y|yes)$') { ollama pull $model }
        else { throw "GIG requires $model for the phone demo." }
    }
}

# These exist only in this PowerShell process and are never written to the repo.
$fish = Read-Host 'Fish Audio API key (leave blank to keep text-only replies)' -AsSecureString
if ($fish.Length -gt 0) {
    $env:FISH_AUDIO_API_KEY = [System.Net.NetworkCredential]::new('', $fish).Password
}
$nvidia = Read-Host 'NVIDIA API key (leave blank to disable Kimi cloud choice)' -AsSecureString
if ($nvidia.Length -gt 0) {
    $env:GIG_NVIDIA_API_KEY = [System.Net.NetworkCredential]::new('', $nvidia).Password
}

$env:GIG_MODEL = 'qwen3:4b'
$env:GIG_VISION_MODEL = 'qwen2.5vl:3b'
$env:GIG_SEMANTIC_MEMORY = '1'
$env:GIG_EMBED_MODEL = 'qwen3-embedding:0.6b'

$drivePath = Read-Host 'Google authorized-user JSON path (leave blank to keep Drive disabled)'
if ($drivePath) {
    if (-not (Test-Path -LiteralPath $drivePath -PathType Leaf)) {
        throw 'Google credential file was not found. Keep Drive disabled or provide its full path.'
    }
    $env:GIG_GOOGLE_CREDENTIALS_FILE = $drivePath
}

Write-Host 'Starting private GIG services on 127.0.0.1 only...' -ForegroundColor Cyan
uv run python run_harness.py
