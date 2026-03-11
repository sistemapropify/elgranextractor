$url = "http://localhost:8000/market-analysis/heatmap/"
try {
    $response = Invoke-WebRequest -Uri $url -UseBasicParsing
    Write-Host "Status: $($response.StatusCode)"
    Write-Host "Content length: $($response.Content.Length)"
    
    # Verificar que se cargó MarkerClusterer
    if ($response.Content -match 'markerclusterer') {
        Write-Host "✅ MarkerClusterer cargado" -ForegroundColor Green
    } else {
        Write-Host "⚠️  MarkerClusterer no encontrado" -ForegroundColor Yellow
    }
    
    # Verificar código de marcadores
    if ($response.Content -match 'new MarkerClusterer') {
        Write-Host "✅ Código de MarkerClusterer presente" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Código de MarkerClusterer no encontrado" -ForegroundColor Yellow
    }
    
    # Verificar marcadores individuales
    if ($response.Content -match 'new google.maps.Marker') {
        Write-Host "✅ Código de marcadores presente" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Código de marcadores no encontrado" -ForegroundColor Yellow
    }
    
    # Verificar tooltips
    if ($response.Content -match 'new google.maps.InfoWindow') {
        Write-Host "✅ Tooltips (InfoWindow) presentes" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Tooltips no encontrados" -ForegroundColor Yellow
    }
    
    # Verificar control de mostrar/ocultar marcadores
    if ($response.Content -match 'toggleMarkers') {
        Write-Host "✅ Control de mostrar/ocultar marcadores presente" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Control de mostrar/ocultar no encontrado" -ForegroundColor Yellow
    }
    
    # Contar puntos de datos
    $pattern = 'const heatmapDataJson = (\[.*?\]);'
    if ($response.Content -match $pattern) {
        $jsonStr = $matches[1]
        $data = $jsonStr | ConvertFrom-Json
        Write-Host "`n📊 Datos del heatmap:" -ForegroundColor Cyan
        Write-Host "   Total de puntos: $($data.Count)"
        Write-Host "   Marcadores a mostrar (limitado a 100): $([math]::Min($data.Count, 100))"
        
        # Mostrar algunas propiedades de ejemplo
        if ($data.Count -gt 0) {
            Write-Host "`n🔍 Ejemplo de propiedades:" -ForegroundColor Cyan
            $data[0..2] | ForEach-Object {
                Write-Host "   - Lat: $($_.lat), Lng: $($_.lng), Precio/m²: $($_.precio_m2), Fuente: $($_.fuente)"
            }
        }
    } else {
        Write-Host "⚠️  No se encontró heatmapDataJson" -ForegroundColor Red
    }
    
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
}