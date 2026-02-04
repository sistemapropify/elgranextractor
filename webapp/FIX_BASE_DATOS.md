# 🔧 SOLUCIÓN AL ERROR DE COLUMNAS FALTANTES

## ❌ ERROR
```
Invalid column name 'estado_http', 'estado_procesamiento', 'tipo_documento', etc.
```

## ✅ SOLUCIÓN

### Opción 1: Aplicar Migraciones Correctamente

```bash
# 1. Detener el servidor (Ctrl+C)

# 2. En una nueva terminal:
cd webapp
set PYTHONPATH=%CD%

# 3. Ver qué migraciones faltan
py manage.py showmigrations captura

# 4. Aplicar TODAS las migraciones
py manage.py migrate captura

# 5. Si falla, aplicar una por una:
py manage.py migrate captura 0002
py manage.py migrate captura 0003  
py manage.py migrate captura 0004

# 6. Reiniciar servidor
py manage.py runserver --noreload 0.0.0.0:8000
```

### Opción 2: Agregar Columnas Manualmente en SQL Server

Si las migraciones fallan, ejecuta este SQL directamente en SQL Server:

```sql
-- Conecta a tu base de datos y ejecuta:

ALTER TABLE captura_capturacruda ADD estado_http VARCHAR(15) DEFAULT 'exito';
ALTER TABLE captura_capturacruda ADD estado_procesamiento VARCHAR(20) DEFAULT 'pendiente';
ALTER TABLE captura_capturacruda ADD tipo_documento VARCHAR(20) DEFAULT 'html';
ALTER TABLE captura_capturacruda ADD contenido_binario_blob VARCHAR(255) DEFAULT '';
ALTER TABLE captura_capturacruda ADD texto_extraido TEXT NULL;
ALTER TABLE captura_capturacruda ADD azure_blob_url VARCHAR(500) DEFAULT '';
ALTER TABLE captura_capturacruda ADD azure_blob_name VARCHAR(255) DEFAULT '';
ALTER TABLE captura_capturacruda ADD metadata_tecnica NVARCHAR(MAX) DEFAULT '{}';
ALTER TABLE captura_capturacruda ADD pdf_tiene_texto BIT NULL;
ALTER TABLE captura_capturacruda ADD pdf_num_paginas INT NULL;

-- Después, marcar las migraciones como aplicadas:
```

Luego en Django:
```bash
cd webapp
set PYTHONPATH=%CD%
py manage.py migrate captura --fake
```

### Opción 3: Recrear la Tabla (CUIDADO: Borra datos)

```bash
# 1. Eliminar tabla en SQL Server
DROP TABLE captura_capturacruda;

# 2. Recrear con migrate
cd webapp
set PYTHONPATH=%CD%
py manage.py migrate captura

# 3. Reiniciar
py manage.py runserver --noreload 0.0.0.0:8000
```

---

## 🎯 DESPUÉS DE ARREGLAR

1. Ve a: `http://localhost:8000/capturas/`
2. Verás el **botón verde de Captura Manual**
3. Ingresa una URL y haz click en "CAPTURAR AHORA"
4. ¡Funciona!

---

## 📝 NOTA

El problema es que las migraciones de Django no se aplicaron a SQL Server. Una vez agregues las columnas (cualquier opción arriba), todo funcionará perfectamente.
