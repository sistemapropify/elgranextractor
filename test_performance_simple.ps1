$url = "http://localhost:8000/market-analysis/heatmap/"
$iterations = 3
$totalTime = 0

Write-Host "Testing performance of heatmap page..."
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
        Write-Host "Iteration $i : ERROR - $_"
    }
}

$avgTime = [math]::Round($totalTime / $iterations, 2)
Write-Host "`nAverage load time: $avgTime ms"

# Evaluación de rendimiento
if ($avgTime -lt 1000) {
    Write-Host "✅ Rendimiento EXCELENTE - La página carga rápidamente (< 1 segundo)"
} elseif ($avgTime -lt 3000) {
    Write-Host "⚠️  Rendimiento ACEPTABLE - La página carga en 1-3 segundos"
} else {
    Write-Host "⚠️  Rendimiento LENTO - La página tarda más de 3 segundos"
}

# Verificar datos
try {
    $response = Invoke-WebRequest -Uri $url -UseBasicParsing
    $pattern = 'const heatmapDataJson = (\[.*?\]);'
    if ($response.Content -match $pattern) {
        $jsonStr = $matches[1]
        $data = $jsonStr | ConvertFrom-Json
        Write-Host "`nHeatmap data: $($data.Count) puntos, JSON size: $($jsonStr.Length) bytes"
    }
} catch {
    Write-Host "No se pudo analizar el JSON"
}