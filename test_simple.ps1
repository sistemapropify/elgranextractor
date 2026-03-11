$url = "http://localhost:8000/market-analysis/heatmap/"
try {
    $response = Invoke-WebRequest -Uri $url -UseBasicParsing
    Write-Host "Status: $($response.StatusCode)"
    Write-Host "Content length: $($response.Content.Length)"
    
    # Verificaciones básicas
    $checks = @(
        @{Name="MarkerClusterer"; Pattern="markerclusterer"},
        @{Name="new MarkerClusterer"; Pattern="new MarkerClusterer"},
        @{Name="google.maps.Marker"; Pattern="new google.maps.Marker"},
        @{Name="InfoWindow"; Pattern="new google.maps.InfoWindow"},
        @{Name="toggleMarkers"; Pattern="toggleMarkers"}
    )
    
    foreach ($check in $checks) {
        if ($response.Content -match $check.Pattern) {
            Write-Host "✅ $($check.Name) presente" -ForegroundColor Green
        } else {
            Write-Host "⚠️  $($check.Name) no encontrado" -ForegroundColor Yellow
        }
    }
    
    # Contar puntos
    if ($response.Content -match 'const heatmapDataJson = (\[.*?\]);') {
        $jsonStr = $matches[1]
        $data = $jsonStr | ConvertFrom-Json
        Write-Host "`n📊 Puntos de datos: $($data.Count)"
        Write-Host "🔍 Marcadores a mostrar: $([math]::Min($data.Count, 100))"
    }
    
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
}