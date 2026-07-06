#!/bin/bash

# ── Startup script for Propifai (PropTech SaaS) ──
# FIX-OOM: Configurado para Azure App Service (Linux, ~2GB RAM)
# - Workers reducidos para evitar OOM
# - Timeout extendido para carga lazy de modelos
# - Manejo de errores graceful

set -e  # Exit on error

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
echo "Starting Gunicorn (2 workers, 600s timeout)..."
exec gunicorn webapp.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 2 \
    --timeout 600 \
    --access-logfile '-' \
    --error-logfile '-' \
    --max-requests 1000 \
    --max-requests-jitter 50