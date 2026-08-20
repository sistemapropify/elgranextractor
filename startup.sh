#!/bin/bash
# ============================================================
# startup.sh — Propifai (Prometeo) Azure App Service Startup
# ============================================================
# SINGLE SOURCE OF TRUTH: This is the only startup script used
# by Azure App Service. All other startup configs (Procfile,
# appsvc.yaml, webapp/startup.sh) are secondary.
# ============================================================
set -e  # Exit on any error

echo "=========================================="
echo "  Propifai — Startup Script"
echo "  $(date -u)"
echo "=========================================="

# Azure/Oryx puede ejecutar desde /home/site/wwwroot o desde un directorio
# temporal /tmp/8dee*. La ubicación del propio script es la fuente fiable.
APP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ ! -f "$APP_ROOT/webapp/manage.py" ]; then
    echo "  ✗ No se encontró webapp/manage.py bajo $APP_ROOT" >&2
    exit 1
fi
echo "[PRE] Application root: $APP_ROOT"

# ── Production Mode ──
# FIX-504: Evita precarga del modelo de embeddings (1GB RAM, ~20s) en startup.
# El modelo se carga lazy en la primera solicitud que lo requiera.
export PRODUCTION=true
echo "[PRE] Modo PRODUCTION activado — embeddings lazy load"

# ── Python Path ──
export PYTHONPATH="$APP_ROOT:$APP_ROOT/webapp${PYTHONPATH:+:$PYTHONPATH}"

# ── Activate Virtual Environment ──
ANTENV_DIR="$APP_ROOT/antenv"
if [ -d "$ANTENV_DIR" ]; then
    source "$ANTENV_DIR/bin/activate"
    echo "[PRE] Virtual environment activated: $ANTENV_DIR"
elif [ -d "/antenv" ]; then
    source /antenv/bin/activate
    echo "[PRE] Virtual environment activated: /antenv"
fi

# ── Install ODBC Driver 18 for SQL Server ──
echo "[1/6] Installing ODBC Driver 18 for SQL Server..."
if ! command -v sqlcmd &> /dev/null && ! odbcinst -j &> /dev/null 2>&1; then
    curl -sSL https://packages.microsoft.com/keys/microsoft.asc | apt-key add - 2>/dev/null || true
    curl -sSL https://packages.microsoft.com/config/ubuntu/22.04/prod.list > /etc/apt/sources.list.d/mssql-release.list 2>/dev/null || true
    apt-get update -qq 2>/dev/null || true
    ACCEPT_EULA=Y apt-get install -y -qq msodbcsql18 unixodbc-dev 2>/dev/null || true
    echo "  ODBC Driver 18 installation attempted."
    # Verify installation
    if odbcinst -j &> /dev/null; then
        echo "  ✓ ODBC Driver installed successfully."
    else
        echo "  ⚠ ODBC Driver installation may have failed. Check logs."
    fi
else
    echo "  ✓ ODBC Driver already installed, skipping."
fi

# ── Camoufox ──
# No instalar paquetes ni descargar navegadores durante el arranque web.
# scrapi/camoufox_launcher.py prepara Camoufox al iniciar un job.
echo "[2/6] Camoufox deferred to scraper execution."

# Instalar en segundo plano las bibliotecas nativas requeridas por Camoufox.
# Gunicorn puede iniciar de inmediato; el launcher espera este marcador antes
# de abrir el navegador. /tmp se recrea en cada arranque del contenedor.
CAMOUFOX_DEPS_LOG="/home/LogFiles/camoufox-deps.log"
CAMOUFOX_DEPS_INSTALLING="/tmp/propifai-camoufox-deps.installing"
CAMOUFOX_DEPS_READY="/tmp/propifai-camoufox-deps.ready"
mkdir -p /home/LogFiles
rm -f "$CAMOUFOX_DEPS_READY"
touch "$CAMOUFOX_DEPS_INSTALLING"
(
    set +e
    echo "[$(date -u)] Installing Camoufox native dependencies..."
    timeout 180 apt-get update -qq
    if timeout 300 apt-get install -y -qq         libgtk-3-0 libx11-xcb1 libasound2; then
        touch "$CAMOUFOX_DEPS_READY"
        echo "[$(date -u)] Camoufox native dependencies installed."
    elif timeout 300 apt-get install -y -qq         libgtk-3-0t64 libx11-xcb1 libasound2t64; then
        touch "$CAMOUFOX_DEPS_READY"
        echo "[$(date -u)] Camoufox t64 native dependencies installed."
    else
        echo "[$(date -u)] ERROR installing Camoufox native dependencies."
    fi
    rm -f "$CAMOUFOX_DEPS_INSTALLING"
) >> "$CAMOUFOX_DEPS_LOG" 2>&1 &
echo "  Camoufox native dependency installation started in background."

# ── Collect Static Files ──
# NOTA: No usar --clear porque borra STATIC_ROOT antes de copiar.
# Si la copia falla, el directorio queda vacio y todos los
# archivos estaticos devuelven 404 (MIME type text/html).
echo "[3/6] Verifying static files from build artifact..."
cd "$APP_ROOT/webapp"
if [ -f staticfiles/canvas/css/canvas.css ] \
  && [ -f staticfiles/canvas/js/canvas_engine.js ] \
  && [ -f staticfiles/canvas/js/canvas_gallery.js ]; then
    echo "  Static files already present; collectstatic skipped."
else
    echo "  Static artifact incomplete; running bounded collectstatic..."
    if timeout 90 python manage.py collectstatic --noinput 2>&1; then
        echo "  Static files collected."
    else
        echo "  WARNING: collectstatic failed or timed out; startup continues."
    fi
fi

# ── Run Migrations ──
# Un problema transitorio de SQL no debe mantener offline el proceso HTTP.
echo "[4/6] Running bounded database migrations..."
if timeout 90 python manage.py migrate --noinput 2>&1; then
    echo "  Migrations applied."
else
    echo "  WARNING: migrations failed or timed out; startup continues."
fi
# ── Return to wwwroot for gunicorn context ──
cd "$APP_ROOT"

# ── Start Gunicorn ──
echo "[5/6] Starting Gunicorn..."
echo "  Port: ${PORT:-8000}"
echo "  Workers: 1 (memory-safe Azure mode)"
echo "  Timeout: 600s (lazy model load)"
exec gunicorn webapp.wsgi:application \
    --bind=0.0.0.0:${PORT:-8000} \
    --workers=1 \
    --worker-class=gthread \
    --threads=4 \
    --timeout=600 \
    --max-requests=1000 \
    --max-requests-jitter=50 \
    --access-logfile='-' \
    --error-logfile='-' \
    --log-level=info
