# Checklist de Despliegue para Azure App Service

## ✅ Cambios realizados:

1. **runtime.txt**: Corregido de `python-3.14.2` a `python-3.12`
2. **requirements.txt**: Agregado `whitenoise` para servir archivos estáticos
3. **settings.py**: Actualizado con:
   - Configuración de WhiteNoise en middleware
   - ALLOWED_HOSTS configurable por variable de entorno
   - DEBUG desactivado por defecto
   - Configuración de seguridad mejorada
   - STATICFILES_STORAGE configurado para WhiteNoise
4. **.env**: Actualizado con variables de ejemplo
5. **.env.example**: Creado para referencia

## 🔧 Pasos para desplegar en Azure:

### 1. Configurar variables de entorno en Azure Portal:
   - Ir a tu App Service `granextractor`
   - Configuración > Configuración de la aplicación > Nueva configuración de la aplicación
   - Agregar las siguientes variables:
     - `DEBUG`: `False`
     - `SECRET_KEY`: (generar una clave segura)
     - `ALLOWED_HOSTS`: `granextractor.azurewebsites.net`
     - Variables de base de datos (ya configuradas)

### 2. Verificar configuración de Python:
   - Azure debería usar Python 3.12 según `runtime.txt`
   - Si hay problemas, verificar en "Configuración > Configuración general > Pila en tiempo de ejecución"

### 3. Re-desplegar la aplicación:
   - Usar el método de despliegue que ya tienes configurado (Git, FTP, etc.)
   - O usar: `az webapp up --name granextractor --resource-group [tu-grupo]`

### 4. Verificar logs después del despliegue:
   - Ir a "Supervisión > Secuencia de registros"
   - Buscar errores de aplicación

### 5. Recopilar archivos estáticos (si es necesario):
   - En Azure, los archivos estáticos ya están en `staticfiles/`
   - WhiteNoise los servirá automáticamente

## 🐛 Solución de problemas comunes:

### Si ves "Hey, Python developers!" (página por defecto de Azure):
1. Verificar que la aplicación se esté ejecutando
2. Revisar logs de aplicación para errores de Django
3. Verificar que `ALLOWED_HOSTS` incluya tu dominio
4. Verificar que `DEBUG=False` en producción

### Si hay errores de base de datos:
1. Verificar que el firewall de Azure SQL permita conexiones desde App Service
2. Verificar credenciales en variables de entorno
3. Verificar que el driver ODBC esté disponible (Azure generalmente lo tiene)

### Si los archivos estáticos no se cargan:
1. Verificar que WhiteNoise esté en `requirements.txt`
2. Verificar configuración de `STATICFILES_STORAGE`
3. Ejecutar `python manage.py collectstatic` localmente y subir los archivos

## 📞 Soporte:
- Revisar logs en "Supervisión > Registros de App Service"
- Habilitar "Registro de aplicaciones" en "Supervisión > Registros de App Service"
- Para errores específicos, buscar en la documentación de Django en Azure