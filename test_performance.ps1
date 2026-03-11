$url = "http://localhost:8000/market-analysis/heatmap/"
$iterations = 3
$totalTime = 0

Write-Host "Testing performance of heatmap page..." -ForegroundColor Cyan
Write-Host "URL: $url"
Write-Host "Iterations: $iterations`n"

for ($i = 1; $i -le $iterations; $i++) {
    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        $response = Invoke-WebRequest -Uri $url -UseBasicParsing
        $stopwatch.Stop()
        $time = $stopwatch.ElapsedMilliseconds
        $totalTime += $time
        Write-Host "Iteration $i : $time ms, Size: $($response.Content.Length) bytes, Status: $($response.StatusCode)"
    } catch {
        Write-Host "Iteration $i : ERROR - $_" -ForegroundColor Red
    }
}

$avgTime = [math]::Round($totalTime / $iterations, 2)
Write-Host "`nAverage load time: $avgTime ms" -ForegroundColor Green

# Evaluación de rendimiento
if ($avgTime -lt 1000) {
    Write-Host "✅ Rendimiento EXCELENTE - La página carga rápidamente (< 1 segundo)" -ForegroundColor Green
} elseif ($avgTime -lt 3000) {
    Write-Host "⚠️  Rendimiento ACEPTABLE - La página carga en 1-3 segundos" -ForegroundColor Yellow
} else {
    Write-Host "⚠️  Rendimiento LENTO - La página tarda más de 3 segundos" -ForegroundColor Red
}

# Verificar tamaño del JSON
try {
    $response = Invoke-WebRequest -Uri $url -UseBasicParsing
    $pattern = 'const heatmapDataJson = (\[.*?\]);'
    if ($response.Content -match $pattern) {
        $jsonStr = $matches[1]
        $data = $jsonStr | ConvertFrom-Json
        Write-Host "`nHeatmap data: $($data.Count) puntos, JSON size: $($jsonStr.Length) bytes"
        
        # Recomendaciones
        if ($data.Count -gt 1000) {
            Write-Host "💡 RECOMENDACIÓN: Considerar paginación o carga diferida si el rendimiento se degrada" -ForegroundColor Cyan
        }
    }
} catch {
    Write-Host "No se pudo analizar el JSON" -ForegroundColor Yellow
}