$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$webRoot = Join-Path $projectRoot 'webapp'
$pythonPath = Join-Path $projectRoot 'elgranextractor\venv\Scripts\python.exe'
$logDirectory = Join-Path $webRoot 'var'
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$logPath = Join-Path $logDirectory 'lead-control-worker.log'
if ((Test-Path -LiteralPath $logPath) -and (Get-Item -LiteralPath $logPath).Length -gt 20MB) {
    Copy-Item -LiteralPath $logPath -Destination (Join-Path $logDirectory 'lead-control-worker.previous.log') -Force
    Clear-Content -LiteralPath $logPath
}
Set-Location -LiteralPath $webRoot
# Django writes startup diagnostics to stderr; preserve them without treating
# native stderr as a PowerShell terminating exception.
$ErrorActionPreference = 'Continue'
& $pythonPath -u manage.py run_lead_control --interval 60 --workers 6 >> $logPath 2>&1
exit $LASTEXITCODE
