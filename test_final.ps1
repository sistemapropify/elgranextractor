$url = "http://localhost:8000/market-analysis/heatmap/"
try {
    $response = Invoke-WebRequest -Uri $url -UseBasicParsing
    Write-Host "✅ Página cargada - Status: $($response.StatusCode), Tamaño: $($response.Content.Length) bytes" -ForegroundColor Green
    
    # Verificar errores comunes
    $errors = @()
    
    if ($response.Content -match 'MarkerClusterer is not defined') {
        $errors += "❌ Error: MarkerClusterer is not defined"
    }
    
    if ($response.Content -match 'Error al cargar Google Maps') {
        $errors += "❌ Error: Google Maps no se cargó"
    }
    
    if ($response.Content -match 'google is not defined') {
        $errors += "❌ Error: Google Maps API no cargada"
    }
    
    # Verificar elementos positivos
    if ($response.Content -match 'initializeHeatmap') {
        Write-Host "✅ Función initializeHeatmap presente" -ForegroundColor Green
    }
    
    if ($response.Content -match 'heatmapDataJson') {
        Write-Host "✅ Datos del heatmap presentes" -ForegroundColor Green
    }
    
    if ($response.Content -match 'toggleMarkers') {
        Write-Host "✅ Control de marcadores presente" -ForegroundColor Green
    }
    
    # Mostrar resultados
    if ($errors.Count -gt 0) {
        Write-Host "`n⚠️  Errores encontrados:" -ForegroundColor Red
        $errors | ForEach-Object { Write-Host "   $_" -ForegroundColor Red }
    } else {
        Write-Host "`n✅ No se encontraron errores evidentes en el HTML" -ForegroundColor Green
    }
    
    # Verificar script de MarkerClusterer
    if ($response.Content -match 'cdnjs.cloudflare.com.*markerclusterer') {
        Write-Host "✅ Script de MarkerClusterer cargado desde CDN" -ForegroundColor Green
    } else {
        Write-Host "⚠️  Script de MarkerClusterer no encontrado en CDN" -ForegroundColor Yellow
    }
    
} catch {
    Write-Host "❌ Error al acceder a la página: $_" -ForegroundColor Red
}