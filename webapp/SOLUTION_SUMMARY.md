# Solución para el problema de despliegue en Azure

## Problema identificado
La aplicación Django no se muestra en producción (`granextractor.azurewebsites.net`) y en su lugar aparece el mensaje "Hey, Python developers!" (página por defecto de Azure App Service).

## Causas raíz encontradas en los logs
1. **Python 3.14.0** - Azure está usando Python 3.14 en lugar de 3.12 (a pesar de `runtime.txt`)
2. **"No framework detected"** - Oryx no detecta la aplicación Django
3. **Aplicación por defecto servida** - Azure está sirviendo `/opt/defaultsite` en lugar de la aplicación Django

## Soluciones implementadas

### 1. Configuración de Python (`runtime.txt`)
- Cambiado de `python-3.14.2` a `python-3.12`
- Creado `oryx-manifest.toml` para forzar detección de Python 3.12

### 2. Detección de Django
- Creado `oryx-manifest.toml` con configuración explícita de Django
- Asegurado que `requirements.txt` incluya Django y dependencias

### 3. Configuración de producción (`settings.py`)
- Agregado WhiteNoise para archivos estáticos
- Configurado `DEBUG=False` por defecto
- `ALLOWED_HOSTS` configurable por variable de entorno
- Mejoras de seguridad habilitadas

### 4. Script de inicio (`startup.sh`)
- Script para Linux App Service
- Instala dependencias, recopila archivos estáticos, ejecuta migraciones
- Inicia Gunicorn con configuración correcta

### 5. Configuración de despliegue (`.deployment`)
- Habilitado build durante el despliegue

## Archivos creados/modificados
- `webapp/runtime.txt` - Versión de Python corregida
- `webapp/requirements.txt` - Agregado whitenoise
- `webapp/webapp/settings.py` - Configuración de producción
- `webapp/.env` y `webapp/.env.example` - Variables de entorno
- `webapp/startup.sh` - Script de inicio para Linux
- `webapp/oryx-manifest.toml` - Configuración para Oryx
- `.deployment` - Configuración de despliegue
- `webapp/DEPLOYMENT_CHECKLIST.md` - Guía de despliegue

## Próximos pasos inmediatos

### 1. Subir los cambios a Azure
```bash
# Si usas Git
git add .
git commit -m "Fix deployment issues"
git push azure main

# O usar Azure CLI
az webapp up --name granextractor --resource-group [tu-grupo]
```

### 2. Configurar variables de entorno en Azure Portal
- `DEBUG`: `False`
- `SECRET_KEY`: (generar una clave segura)
- `ALLOWED_HOSTS`: `granextractor.azurewebsites.net`

### 3. Verificar logs después del despliegue
- Ir a Azure Portal > App Service > Supervisión > Secuencia de registros
- Buscar mensajes de éxito/error

### 4. Si persiste el problema
1. Forzar rebuild: En Azure Portal > Centro de implementación > Reiniciar
2. Verificar que `startup.sh` tenga permisos de ejecución
3. Revisar logs de build en "Registros de implementación"

## Notas importantes
- Azure puede cachear configuraciones anteriores, puede requerir múltiples despliegues
- El archivo `runtime.txt` puede ser ignorado si Azure ya tiene una configuración previa
- Considera reiniciar el App Service después de los cambios de configuración