# Solución Definitiva para Despliegue en Azure

## Problema
Azure App Service muestra "Hey, Python developers!" en lugar de la aplicación Django.

## Causa Raíz
Azure Oryx no detecta la aplicación Django porque:
1. Los archivos de configuración (`runtime.txt`, `requirements.txt`) no están en la raíz del proyecto desplegado
2. Azure busca `application:app` pero Django usa `webapp.wsgi:application`
3. Oryx detecta Python 3.14 en lugar de 3.12

## Soluciones Implementadas

### Archivos creados en la **RAÍZ** del proyecto:
1. [`runtime.txt`](runtime.txt) - Python 3.12 (forzar versión)
2. [`requirements.txt`](requirements.txt) - Dependencias incluyendo whitenoise
3. [`oryx-manifest.toml`](oryx-manifest.toml) - Configuración explícita para Oryx
4. [`application.py`](application.py) - Punto de entrada para Azure
5. [`.deployment`](.deployment) - Configuración de despliegue

### Archivos modificados en `webapp/`:
1. [`webapp/settings.py`](webapp/webapp/settings.py) - Configuración de producción
2. [`webapp/requirements.txt`](webapp/requirements.txt) - whitenoise agregado
3. [`webapp/startup.sh`](webapp/startup.sh) - Script de inicio para Linux

## Estructura Final Correcta
```
d:/proyectos/prometeo/
├── runtime.txt                    # Python 3.12 (RAÍZ)
├── requirements.txt               # Dependencias (RAÍZ)
├── oryx-manifest.toml            # Config Oryx (RAÍZ)
├── application.py                # Punto entrada Azure (RAÍZ)
├── .deployment                   # Config despliegue (RAÍZ)
└── webapp/                       # Proyecto Django
    ├── manage.py
    ├── requirements.txt          # También aquí por compatibilidad
    ├── startup.sh               # Script inicio
    ├── webapp/
    │   ├── settings.py          # Config producción
    │   ├── wsgi.py              # WSGI application
    │   └── ...
    └── ...
```

## Pasos para Desplegar

### 1. Subir TODOS los cambios a Azure:
```bash
# Si usas Git
git add .
git commit -m "Fix Azure deployment: add root config files"
git push azure main

# O usar Azure CLI
az webapp up --name granextractor --resource-group [tu-grupo]
```

### 2. Forzar Rebuild Completo:
1. Ir a Azure Portal > App Service `granextractor`
2. "Centro de implementación" > "Reiniciar"
3. "Configuración" > "Configuración general" > "Reiniciar"

### 3. Configurar Variables de Entorno (Azure Portal):
- `DEBUG`: `False`
- `SECRET_KEY`: (generar clave segura)
- `ALLOWED_HOSTS`: `granextractor.azurewebsites.net`
- Variables de base de datos (ya configuradas)

### 4. Verificar Logs:
- "Supervisión" > "Secuencia de registros"
- Buscar: "Detected Django app" o "Starting gunicorn"

## Qué Esperar Después del Despliegue

### Logs de éxito:
```
Detected Django app
Python version: 3.12.x
Starting gunicorn with: webapp.wsgi:application
```

### Si sigue fallando:
1. **Forzar Python 3.12 manualmente**:
   - Azure Portal > "Configuración" > "Configuración general"
   - "Pila en tiempo de ejecución" > Python 3.12

2. **Eliminar cache de Oryx**:
   - En "Configuración avanzada" > "Configuración de la aplicación"
   - Agregar: `SCM_DO_BUILD_DURING_DEPLOYMENT = true`

3. **Usar startup.sh personalizado**:
   - En "Configuración" > "Configuración general"
   - "Comando de inicio": `bash startup.sh`

## Verificación Final
1. Visitar `https://granextractor.azurewebsites.net`
2. Debería ver "¡Bienvenido a tu proyecto Django en Azure!"
3. Si ves error 500, revisar logs para errores de Django

## Soporte Adicional
- Revisar `webapp/DEPLOYMENT_CHECKLIST.md` para más detalles
- Consultar `webapp/SOLUTION_SUMMARY.md` para análisis completo