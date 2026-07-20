#!/bin/bash

# ── Startup script for Propifai (PropTech SaaS) ──
# FIX-OOM: Configurado para Azure App Service (Linux, ~2GB RAM)
# - Workers reducidos para evitar OOM
# - Timeout extendido para carga lazy de modelos
# - Manejo de errores graceful
# FIX-504: Exporta PRODUCTION=true para saltar inicialización pesada
# en apps.py (modelo de embeddings, semantic router), evitando 504
# GatewayTimeout por startup lento. El modelo se carga lazy.

set -e  # Exit on error

# ── Modo Producción ──
# FIX-504: Esta variable hace que intelligence/apps.py salte la
# precarga del modelo de embeddings (1GB RAM, ~20s) en startup.
# El modelo se cargará lazy en la primera solicitud que lo requiera.
export PRODUCTION=true
echo "Modo PRODUCTION activado — precarga de embeddings saltada (lazy load)"

# ── PYTHONPATH ──
# Asegurar que tanto el root como webapp/ están en el path
export PYTHONPATH="$(pwd):$(pwd)/webapp${PYTHONPATH:+:$PYTHONPATH}"
echo "PYTHONPATH=$PYTHONPATH"

# Activate virtual environment if it exists
ANTENV_DIR="/home/site/wwwroot/antenv"
if [ -d "$ANTENV_DIR" ]; then
    source "$ANTENV_DIR/bin/activate"
    echo "Virtual environment activated: $ANTENV_DIR"
elif [ -d "antenv" ]; then
    source antenv/bin/activate
    echo "Virtual environment activated: ./antenv"
fi

# Install dependencies if requirements.txt exists
if [ -f "requirements.txt" ]; then
    echo "Installing dependencies..."
    pip install -r requirements.txt -q
fi

# Change to webapp directory
cd webapp 2>/dev/null || {
    echo "WARNING: webapp/ directory not found, trying current directory"
}

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput 2>&1

# Run migrations
echo "Running migrations..."
python manage.py migrate --noinput 2>&1

# ── Start Gunicorn ──
# FIX-OOM: Solo 2 workers para mantener ~500MB libres para el modelo de embeddings
# Timeout: 600s para carga lazy del modelo en primera solicitud
# FIX-504: PRODUCTION=true evita que los workers carguen el modelo de embeddings
echo "Starting Gunicorn (2 workers, 600s timeout)..."
exec gunicorn webapp.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 2 \
    --timeout 600 \
    --access-logfile '-' \
    --error-logfile '-' \
    --max-requests 1000 \
    --max-requests-jitter 50