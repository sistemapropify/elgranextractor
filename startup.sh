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

# ── Production Mode ──
# FIX-504: Evita precarga del modelo de embeddings (1GB RAM, ~20s) en startup.
# El modelo se carga lazy en la primera solicitud que lo requiera.
export PRODUCTION=true
echo "[PRE] Modo PRODUCTION activado — embeddings lazy load"

# ── Python Path ──
export PYTHONPATH="/home/site/wwwroot:/home/site/wwwroot/webapp${PYTHONPATH:+:$PYTHONPATH}"

# ── Activate Virtual Environment ──
ANTENV_DIR="/home/site/wwwroot/antenv"
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

# ── Install Camoufox browser for scrapers (headless in production) ──
# Oryx instala el paquete camoufox desde requirements.txt, pero el binario
# del navegador (fork de Firefox) se descarga por separado con `camoufox fetch`.
# En el contenedor Linux no hay display; Camoufox corre en headless=True (ver
# scrapi/camoufox_launcher.py). Ningún fallo aquí debe tumbar la web: el
# launcher también descarga el binario bajo demanda antes de cada scraping.
echo "[2/6] Scheduling Camoufox preparation (non-blocking)..."
# La web no puede depender del navegador del scraper para arrancar. Azure mata
# el contenedor si esta etapa tarda demasiado; Camoufox supera 600 MB y su
# extracción puede tomar varios minutos. Las librerías se preparan en segundo
# plano y el launcher conserva su fallback bajo demanda.
CAMOUFOX_APT_DEPS="libasound2 libatk1.0-0 libatk-bridge2.0-0 libcairo2 libcups2 libdbus-1-3 libdrm2 libgbm1 libglib2.0-0 libgtk-3-0 libnspr4 libnss3 libpango-1.0-0 libx11-6 libxcb1 libxcomposite1 libxdamage1 libxext6 libxfixes3 libxkbcommon0 libxrandr2 libxshmfence1 fonts-liberation xdg-utils"
export CAMOUFOX_DATA_DIR="${CAMOUFOX_DATA_DIR:-$HOME/.cache/camoufox}"
CAMOUFOX_BOOT_LOG="${HOME}/LogFiles/camoufox-startup.log"
mkdir -p "$(dirname "$CAMOUFOX_BOOT_LOG")"

prepare_camoufox() {
    echo "[$(date -u)] Preparing native Camoufox dependencies..."
    apt-get install -y -qq $CAMOUFOX_APT_DEPS 2>&1 || true

    if find "$CAMOUFOX_DATA_DIR" -type f -name 'camoufox-bin' -print -quit 2>/dev/null | grep -q .; then
        echo "[$(date -u)] Camoufox browser already available; fetch skipped."
        return 0
    fi

    echo "[$(date -u)] Browser not cached; download deferred to scraper execution."
}

prepare_camoufox >> "$CAMOUFOX_BOOT_LOG" 2>&1 &
echo "  ✓ Camoufox preparation running in background; web startup continues."
# ── Collect Static Files ──
# NOTA: No usar --clear porque borra STATIC_ROOT antes de copiar.
# Si la copia falla, el directorio queda vacio y todos los
# archivos estaticos devuelven 404 (MIME type text/html).
echo "[3/6] Collecting static files..."
cd /home/site/wwwroot/webapp
python manage.py collectstatic --noinput 2>&1
test -f staticfiles/canvas/css/canvas.css
test -f staticfiles/canvas/js/canvas_engine.js
test -f staticfiles/canvas/js/canvas_gallery.js
echo "  ✓ Static files collected."

# ── Run Migrations ──
echo "[4/6] Running database migrations..."
python manage.py migrate --noinput 2>&1
echo "  ✓ Migrations applied."

# ── Return to wwwroot for gunicorn context ──
cd /home/site/wwwroot

# ── Start Gunicorn ──
echo "[5/6] Starting Gunicorn..."
echo "  Port: ${PORT:-8000}"
echo "  Workers: 2 (max-requests: 1000, jitter: 50)"
echo "  Timeout: 600s (lazy model load)"
exec gunicorn webapp.wsgi:application \
    --bind=0.0.0.0:${PORT:-8000} \
    --workers=2 \
    --worker-class=gthread \
    --threads=4 \
    --timeout=600 \
    --max-requests=1000 \
    --max-requests-jitter=50 \
    --access-logfile='-' \
    --error-logfile='-' \
    --log-level=info
