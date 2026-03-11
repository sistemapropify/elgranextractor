$url = "http://localhost:8000/market-analysis/heatmap/"
try {
    $response = Invoke-WebRequest -Uri $url -UseBasicParsing
    Write-Host "Status: $($response.StatusCode)"
    Write-Host "Content length: $($response.Content.Length)"
    
    # Buscar heatmapDataJson
    $pattern = 'const heatmapDataJson = (\[.*?\]);'
    if ($response.Content -match $pattern) {
        $jsonStr = $matches[1]
        Write-Host "Found heatmapDataJson, length: $($jsonStr.Length)"
        
        # Convertir JSON
        $data = $jsonStr | ConvertFrom-Json
        Write-Host "Number of points: $($data.Count)"
        
        if ($data.Count -gt 0) {
            Write-Host "Sample point: $($data[0] | ConvertTo-Json -Compress)"
            
            # Contar fuentes
            $sources = @{}
            foreach ($p in $data) {
                $src = $p.fuente
                if (-not $src) { $src = "unknown" }
                $sources[$src] = ($sources[$src] + 1)
            }
            Write-Host "Sources:"
            $sources.GetEnumerator() | ForEach-Object { Write-Host "  $($_.Key): $($_.Value)" }
        }
    } else {
        Write-Host "heatmapDataJson not found"
    }
    
    # Verificar mensaje
    if ($response.Content -match "HEATMAP FUNCIONANDO CORRECTAMENTE") {
        Write-Host "✅ Heatmap message present"
    } else {
        Write-Host "⚠️  Heatmap message missing"
    }
} catch {
    Write-Host "Error: $_"
}