# Script PowerShell para borrar registros de propiedadraw directamente
Write-Host "=== BORRADO DIRECTO DE PROPIEDADRAW ===" -ForegroundColor Cyan

# Intentar conectar a la base de datos y ejecutar TRUNCATE
try {
    # Configurar conexión (ajustar según tu configuración)
    $connectionString = "Server=localhost;Database=prometeo;Trusted_Connection=True;"
    
    Write-Host "Conectando a la base de datos..." -ForegroundColor Yellow
    
    # Crear conexión
    $connection = New-Object System.Data.SqlClient.SqlConnection
    $connection.ConnectionString = $connectionString
    $connection.Open()
    
    # Contar registros antes
    $command = $connection.CreateCommand()
    $command.CommandText = "SELECT COUNT(*) FROM ingestas_propiedadraw"
    $count = $command.ExecuteScalar()
    Write-Host "Registros actuales en PropiedadRaw: $count" -ForegroundColor Yellow
    
    if ($count -eq 0) {
        Write-Host "La tabla ya está vacía. No hay nada que borrar." -ForegroundColor Green
        $connection.Close()
        exit
    }
    
    # Confirmación automática
    Write-Host "Borrando $count registros..." -ForegroundColor Red
    Write-Host "Esta acción NO se puede deshacer." -ForegroundColor Red
    
    # Ejecutar TRUNCATE
    $command.CommandText = "TRUNCATE TABLE ingestas_propiedadraw"
    $rowsAffected = $command.ExecuteNonQuery()
    Write-Host "Tabla truncada exitosamente." -ForegroundColor Green
    
    # Verificar
    $command.CommandText = "SELECT COUNT(*) FROM ingestas_propiedadraw"
    $newCount = $command.ExecuteScalar()
    
    if ($newCount -eq 0) {
        Write-Host "✓ Tabla vacía confirmada" -ForegroundColor Green
    } else {
        Write-Host "✗ Tabla todavía tiene $newCount registros" -ForegroundColor Red
    }
    
    $connection.Close()
    
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
    Write-Host "Intentando método alternativo..." -ForegroundColor Yellow
    
    # Método alternativo: usar sqlcmd si está disponible
    try {
        Write-Host "Ejecutando sqlcmd..." -ForegroundColor Yellow
        & sqlcmd -S localhost -d prometeo -Q "TRUNCATE TABLE ingestas_propiedadraw"
        Write-Host "Comando sqlcmd ejecutado." -ForegroundColor Green
    } catch {
        Write-Host "Error con sqlcmd: $_" -ForegroundColor Red
    }
}

Write-Host "=== FIN DEL BORRADO ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Presiona cualquier tecla para continuar..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")