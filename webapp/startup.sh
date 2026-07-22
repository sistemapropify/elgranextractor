#!/bin/bash

# Startup script for Azure App Service - Propifai
set -e

echo "=== Iniciando Propifai en Azure App Service ==="

# Determinar directorio de la app
APP_DIR="/home/site/wwwroot"

# Si Oryx extrajo en un subdirectorio temporal, usarlo
for d in /tmp/8dee*/; do
    if [ -d "$d" ]; then
        APP_DIR="$d"
        break
    fi
done

# El proyecto Django está en webapp/ dentro del repo
if [ -f "$APP_DIR/webapp/manage.py" ]; then
    APP_DIR="$APP_DIR/webapp"
fi

cd "$APP_DIR"
echo "Directorio de trabajo: $(pwd)"
echo "Manage.py existe: $(test -f manage.py && echo SI || echo NO)"

# Activar virtual env
if [ -d "$APP_DIR/antenv" ]; then
    source "$APP_DIR/antenv/bin/activate"
    echo "Virtualenv activado: antenv"
elif [ -d "/home/site/wwwroot/antenv" ]; then
    source "/home/site/wwwroot/antenv/bin/activate"
    echo "Virtualenv activado: antenv (home/site/wwwroot)"
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
