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

# ── Install Camoufox browser for scrapers (headless in production) ──
# Oryx instala el paquete camoufox desde requirements.txt, pero el binario
# del navegador (fork de Firefox) se descarga por separado con `camoufox fetch`.
# En el contenedor Linux no hay display; Camoufox corre en headless=True (ver
# scrapi/camoufox_launcher.py). Si falta una librería nativa, el arranque falla
# explícitamente para no publicar un scraper que nunca podrá ejecutarse.
echo "[2/6] Preparing Camoufox browser for scrapers..."
# Librerías mínimas oficiales. Se instalan por familias porque Ubuntu 24.04
# renombró algunos paquetes con sufijo t64; una alternativa inexistente no
# debe cancelar la instalación completa (ese era el fallo anterior).
apt-get update -qq
install_one_of() {
    for package_name in "$@"; do
        if DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends "$package_name"; then
            return 0
        fi
    done
    return 1
}
install_one_of libgtk-3-0 libgtk-3-0t64
install_one_of libx11-xcb1
install_one_of libasound2 libasound2t64
ldconfig

for required_library in libgtk-3.so.0 libX11-xcb.so.1 libasound.so.2; do
    if ! ldconfig -p | grep -q "$required_library"; then
        echo "  ✗ Missing Camoufox runtime library: $required_library" >&2
        exit 1
    fi
done
echo "  ✓ Camoufox native libraries available."

# Camoufox usa platformdirs.user_cache_dir('camoufox'); no admite --data-dir.
# Forzamos el cache de Linux a /home, que es persistente en App Service.
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-/home/.cache}"
CAMOUFOX_CACHE="$XDG_CACHE_HOME/camoufox"
# Descargar el binario del navegador (solo la primera vez).
# `timeout 180` limita el bloqueo del boot: si no termina a tiempo, gunicorn
# arranca igual y el launcher (scrapi/camoufox_launcher.py) reintentará la
# descarga bajo demanda antes del scraping.
if python -c "from camoufox.pkgman import camoufox_path; print(camoufox_path(download_if_missing=False))" >/dev/null 2>&1; then
    echo "  ✓ Camoufox browser already downloaded, skipping fetch."
else
    echo "  ⏳ Downloading Camoufox browser (first time only, ~200MB)..."
    timeout 180 python -m camoufox fetch 2>&1 \
        || echo "  ⚠ Camoufox fetch failed/timeout; the launcher will retry on demand."
fi
echo "  Camoufox cache: $CAMOUFOX_CACHE"
echo "  ✓ Camoufox setup finished."

# ── Collect Static Files ──
# NOTA: No usar --clear porque borra STATIC_ROOT antes de copiar.
# Si la copia falla, el directorio queda vacio y todos los
# archivos estaticos devuelven 404 (MIME type text/html).
echo "[3/6] Collecting static files..."
cd "$APP_ROOT/webapp"
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
cd "$APP_ROOT"

# ── Start Gunicorn ──
echo "[5/6] Starting Gunicorn..."
echo "  Port: ${PORT:-8000}"
echo "  Workers: 2 (max-requests: 1000, jitter: 50)"
echo "  Timeout: 600s (lazy model load)"
exec gunicorn webapp.wsgi:application \
    --bind=0.0.0.0:${PORT:-8000} \
    --workers=2 \
    --timeout=600 \
    --max-requests=1000 \
    --max-requests-jitter=50 \
    --access-logfile='-' \
    --error-logfile='-' \
    --log-level=info
