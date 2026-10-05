param(
    [string]$Python = '',
    [switch]$Background,
    [string]$PilotUrl = ''
)

$ErrorActionPreference = 'Stop'
if (-not $Python) {
    $taskVenvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    $Python = if (Test-Path -LiteralPath $taskVenvPython) { $taskVenvPython } else { (Get-Command python -ErrorAction Stop).Source }
}
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw 'No se encontró el Python del scraper.' }
if ($Background -and $PilotUrl) { throw 'La prueba con guardado se ejecuta en primer plano.' }

# Capture settings, never print them, never write them to disk or pass them as arguments.
$taskSettingRows = & az webapp config appsettings list --name granextractorservice --resource-group rg-elgranextractor --subscription 0219eecc-9920-4789-9929-3091a2f09daf --query "[?starts_with(name, 'DB_') || starts_with(name, 'AZURE_STORAGE_')].{name:name,value:value}" --output json --only-show-errors
if ($LASTEXITCODE -ne 0) { throw 'No se pudo leer la configuración con tu sesión autorizada de Azure.' }
$taskSettings = @{}
($taskSettingRows -join "`n" | ConvertFrom-Json) | ForEach-Object { $taskSettings[$_.name] = $_.value }
$taskVars = @{
    DJANGO_SETTINGS_MODULE = 'scrapi.worker_settings'
    DJANGO_SECRET_KEY = [guid]::NewGuid().ToString()
    PYTHONPATH = (Join-Path $PSScriptRoot 'webapp')
    PYTHONIOENCODING = 'utf-8'
    PYTHONUNBUFFERED = '1'
    SCRAPING_REVISION = 'local-native'
}
if (Get-Command git -ErrorAction SilentlyContinue) {
    $taskRevision = & git -C $PSScriptRoot rev-parse HEAD 2>$null
    if ($LASTEXITCODE -eq 0) { $taskVars['SCRAPING_REVISION'] = 'pc-' + $taskRevision.Substring(0, 12) }
}
foreach ($taskName in @('HOST', 'NAME', 'USER', 'PASSWORD')) {
    $taskValue = $taskSettings[('DB_' + $taskName)]
    if (-not $taskValue) { throw ('Falta la configuración de DB_' + $taskName + '; no se inició el ejecutor.') }
    $taskVars[('SCRAPING_DB_' + $taskName)] = $taskValue
}
foreach ($taskName in @('AZURE_STORAGE_CONNECTION_STRING', 'AZURE_STORAGE_ACCOUNT_NAME', 'AZURE_STORAGE_ACCOUNT_KEY', 'AZURE_STORAGE_CONTAINER_NAME')) {
    $taskVars[$taskName] = if ($taskSettings.ContainsKey($taskName)) { $taskSettings[$taskName] } else { '' }
}
$taskPreviousVars = @{}
try {
    foreach ($taskName in $taskVars.Keys) {
        $taskPreviousVars[$taskName] = [Environment]::GetEnvironmentVariable($taskName, 'Process')
        [Environment]::SetEnvironmentVariable($taskName, $taskVars[$taskName], 'Process')
    }
    $taskArgs = @((Join-Path $PSScriptRoot 'webapp\manage.py'), 'scraping_local_worker')
    if ($PilotUrl) { $taskArgs += @('--pilot-url', $PilotUrl) }
    if ($Background) {
        $taskLogDir = Join-Path ([IO.Path]::GetTempPath()) 'propify-local-worker'
        New-Item -ItemType Directory -Path $taskLogDir -Force | Out-Null
        $taskRunName = [guid]::NewGuid().ToString('N')
        $taskQuotedArgs = $taskArgs | ForEach-Object { '"' + $_ + '"' }
        $taskProcess = Start-Process -FilePath $Python -ArgumentList $taskQuotedArgs -WorkingDirectory (Join-Path $PSScriptRoot 'webapp') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskLogDir ($taskRunName + '.out.log')) -RedirectStandardError (Join-Path $taskLogDir ($taskRunName + '.err.log')) -PassThru
        Write-Output ('Ejecutor iniciado. PID ' + $taskProcess.Id + '. Logs: ' + (Join-Path $taskLogDir $taskRunName))
    } else {
        & $Python @taskArgs
        if ($LASTEXITCODE -ne 0) { throw 'El ejecutor no pudo continuar. Revisa el error anterior.' }
    }
} finally {
    foreach ($taskName in $taskPreviousVars.Keys) {
        [Environment]::SetEnvironmentVariable($taskName, $taskPreviousVars[$taskName], 'Process')
    }
    $taskSettings.Clear()
    $taskVars.Clear()
}
