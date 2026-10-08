# Read-only PC inventory. Run inside the REMOTE Windows PowerShell terminal.
# Does not install software, change firewall settings, or print credentials.
$ErrorActionPreference = 'Continue'
Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, OSArchitecture
Get-CimInstance Win32_ComputerSystem | Select-Object @{Name='RAM_GiB';Expression={[math]::Round($_.TotalPhysicalMemory / 1GB, 1)}}
Get-PSDrive -PSProvider FileSystem | Select-Object Name, @{Name='Free_GiB';Expression={[math]::Round($_.Free / 1GB, 1)}}
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    nvidia-smi --query-gpu=name,memory.total,memory.free,driver_version --format=csv
} else { Write-Output 'nvidia-smi unavailable: GPU/driver not verified' }
foreach ($gigTool in @('python', 'uv', 'ollama', 'docker', 'git')) {
    if (Get-Command $gigTool -ErrorAction SilentlyContinue) { & $gigTool --version }
    else { Write-Output "$gigTool unavailable" }
}
try {
    $gigModels = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 5
    $gigModels.models | Select-Object name, size
} catch { Write-Output 'Local Ollama model service unavailable' }
