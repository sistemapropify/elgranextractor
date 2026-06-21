# 📋 PASOS SIMPLES PARA QUE FUNCIONE

## Paso 1: Ejecuta este SQL EN SQL SERVER

```sql
USE [tu_base_de_datos_real];
GO

-- Ejecuta solo las que NO tengas (verifica con SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='captura_capturacruda')

IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='captura_capturacruda' AND COLUMN_NAME='fuente_id')
    ALTER TABLE captura_capturacruda ADD fuente_id INT NULL;

IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='captura_capturacruda' AND COLUMN_NAME='hash_sha256')
    ALTER TABLE captura_capturacruda ADD hash_sha256 VARCHAR(64) NULL;

IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='captura_capturacruda' AND COLUMN_NAME='tamaño_bytes')
    ALTER TABLE captura_capturacruda ADD tamaño_bytes INT NULL;

IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='captura_capturacruda' AND COLUMN_NAME='estado_procesamiento')
    ALTER TABLE captura_capturacruda ADD estado_procesamiento VARCHAR(20) NULL DEFAULT 'capturado';

IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='captura_capturacruda' AND COLUMN_NAME='tipo_documento')
    ALTER TABLE captura_capturacruda ADD tipo_documento VARCHAR(20) NULL DEFAULT 'html';

GO
```

## Paso 2: Verifica que el servidor está corriendo

Terminal 1 debe tener esto corriendo:
```
cd webapp
set PYTHONPATH=%CD%
py manage.py runserver --noreload 0.0.0.0:8000
```

Si no, inícialo.

## Paso 3: Prueba con CURL (sin navegador)

Abre PowerShell y ejecuta:

```powershell
$url = "http://localhost:8000/api/capturas/manual/"
$body = @{ url = "https://httpbin.org/html" } | ConvertTo-Json
Invoke-RestMethod -Uri $url -Method Post -Body $body -ContentType "application/json"
```

Deberías ver un mensaje de éxito.

## Paso 4: Verifica en la base de datos

En SQL Server:
```sql
SELECT TOP 10 * FROM captura_capturacruda ORDER BY fecha_captura DESC;
```

Si ves registros = ¡FUNCIONA!

Si no ves registros = El problema es otro (no las columnas).

## Paso 5: Si aún no funciona

Dime QUÉ error exacto ves:
- ¿En el navegador al abrir /capturas/?
- ¿En el curl?
- ¿En la consola del servidor?

Y arreglaré ESE error específico.
