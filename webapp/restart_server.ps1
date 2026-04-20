# Script PowerShell para reiniciar el servidor Django
Write-Host "Deteniendo servidor Django..." -ForegroundColor Yellow

# Buscar procesos de Python que estén ejecutando manage.py runserver
$processes = Get-Process | Where-Object { 
    $_.ProcessName -eq "python" -or $_.ProcessName -eq "py" -or $_.ProcessName -eq "python3"
} | Where-Object {
    $_.CommandLine -like "*manage.py*" -and $_.CommandLine -like "*runserver*"
}

if ($processes) {
    Write-Host "Encontrados $($processes.Count) procesos de servidor Django" -ForegroundColor Yellow
    foreach ($proc in $processes) {
        Write-Host "  Deteniendo proceso PID $($proc.Id): $($proc.CommandLine)" -ForegroundColor Cyan
        Stop-Process -Id $proc.Id -Force
    }
    Start-Sleep -Seconds 2
} else {
    Write-Host "No se encontraron procesos de servidor Django ejecutándose" -ForegroundColor Green
}

Write-Host "`nIniciando servidor Django..." -ForegroundColor Yellow
cd "d:\proyectos\prometeo\webapp"
Start-Process -NoNewWindow -FilePath "py" -ArgumentList "manage.py", "runserver", "--noreload" -WorkingDirectory "d:\proyectos\prometeo\webapp"

Write-Host "Servidor reiniciado. Esperando 5 segundos para que inicie..." -ForegroundColor Green
Start-Sleep -Seconds 5

Write-Host "`nProbando conexión a la API..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/intelligence/rag/tables/?schema=dbo&database=propifai&nocache=1" -TimeoutSec 10
    Write-Host "  Status: $($response.StatusCode)" -ForegroundColor Green
    Write-Host "  Respuesta recibida correctamente" -ForegroundColor Green
} catch {
    Write-Host "  Error: $_" -ForegroundColor Red
}

Write-Host "`nReinicio completado." -ForegroundColor Green