#!/bin/bash

# Startup script for Azure App Service - Propifai
set -e

echo "=== Iniciando Propifai en Azure App Service ==="

# Cambiar al directorio de la aplicación
APP_DIR="/home/site/wwwroot"
if [ -d "/tmp/8dee6a19f209a4a" ]; then
    APP_DIR="/tmp/8dee6a19f209a4a"
fi
cd "$APP_DIR"

echo "Directorio de trabajo: $(pwd)"

# Activar virtual env
if [ -d "$APP_DIR/antenv" ]; then
    source "$APP_DIR/antenv/bin/activate"
    echo "Virtualenv activado: antenv"
fi

# Migraciones
echo "Ejecutando migraciones..."
python manage.py migrate --noinput || echo "Migraciones omitidas o ya aplicadas"

# Collect static
echo "Recolectando archivos estáticos..."
python manage.py collectstatic --noinput --clear 2>&1 || echo "Collectstatic omitido"

# Iniciar Gunicorn
echo "Iniciando Gunicorn en puerto ${PORT:-8000}..."
gunicorn --bind=0.0.0.0:${PORT:-8000} \
         --workers=2 \
         --timeout=120 \
         --access-logfile=- \
         --error-logfile=- \
         --log-level=info \
         settings.wsgi:application
