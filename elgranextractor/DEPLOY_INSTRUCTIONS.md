# Instrucciones Finales para Desplegar en Azure

## Problema Resuelto
Azure no detectaba tu aplicación Django porque los archivos de configuración (`runtime.txt`, `requirements.txt`, `oryx-manifest.toml`) estaban dentro de la carpeta `webapp/` en lugar de en la raíz del proyecto. Azure Oryx busca estos archivos en la raíz del repositorio desplegado.

## Cambios Realizados

### 1. Archivos Creados en la Raíz del Proyecto:
- `runtime.txt` - Python 3.12 (Azure compatible)
- `requirements.txt` - Dependencias incluyendo whitenoise
- `oryx-manifest.toml` - Configuración explícita para Oryx detectar Django
- `application.py` - Punto de entrada para Azure
- `.deployment` - Habilita build durante el despliegue

### 2. Archivos Eliminados (duplicados conflictivos):
- `webapp/runtime.txt` ❌ ELIMINADO
- `webapp/requirements.txt` ❌ ELIMINADO  
- `webapp/oryx-manifest.toml` ❌ ELIMINADO

### 3. Configuraciones Actualizadas en `webapp/`:
- `webapp/webapp/settings.py` - Configuración de producción
- `webapp/.env` - Variables de entorno de ejemplo
- `webapp/startup.sh` - Script de inicio para Linux App Service

## Pasos para Desplegar

### Paso 1: Subir Cambios a GitHub
```bash
git add .
git commit -m "Fix Azure deployment: move config files to root"
git push origin main
```

### Paso 2: Forzar Rebuild en Azure
1. Ve al portal de Azure: https://portal.azure.com
2. Navega a tu App Service: `granextractor`
3. En el menú izquierdo, ve a **"Centro de implementación"**
4. Haz clic en **"Sincronizar"** o **"Reimplementar"**
5. También puedes ir a **"Configuración"** → **"General"** → **"Reiniciar"**

### Paso 3: Verificar Variables de Entorno en Azure
1. En tu App Service, ve a **"Configuración"** → **"Configuración"**
2. En "Configuración de la aplicación", asegúrate de tener:
   - `DEBUG` = `False`
   - `ALLOWED_HOSTS` = `granextractor.azurewebsites.net,localhost,127.0.0.1`
   - `SECRET_KEY` = (un valor seguro)
   - Configuración de base de datos SQL Server

### Paso 4: Monitorear Logs
1. Ve a **"Supervisión"** → **"Registros de App Service"**
2. Habilita "Registro de aplicaciones (sistema de archivos)"
3. Ve a **"Herramientas avanzadas"** → **"Ir"** → **"LogFiles"** → **"Application"**

## Verificación de Éxito

Cuando el despliegue sea exitoso, verás en los logs:
```
Detected Python 3.12
Detected Django 6.0.1
Running build command: pip install -r requirements.txt
Running gunicorn webapp.wsgi:application --bind 0.0.0.0:8000
```

Tu aplicación estará disponible en: https://granextractor.azurewebsites.net

## Solución de Problemas

### Si aún ves "Hey, Python developers!":
1. Verifica que los archivos estén en la raíz del repositorio (no en `webapp/`)
2. Revisa los logs de build en Azure
3. Asegúrate de que `oryx-manifest.toml` tenga la configuración correcta

### Si hay errores de base de datos:
1. Verifica las variables de entorno de conexión a SQL Server
2. Asegúrate de que el firewall de Azure SQL permita conexiones desde App Service

### Si hay errores de archivos estáticos:
1. WhiteNoise está configurado para servir archivos estáticos
2. Ejecuta `python manage.py collectstatic` localmente y sube los archivos

## Contacto
Si después de seguir estos pasos aún tienes problemas, comparte los logs más recientes de Azure para análisis adicional.