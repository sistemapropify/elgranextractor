FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254
ARG SCRAPING_REVISION=development
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_SETTINGS_MODULE=scrapi.worker_settings \
    CAMOUFOX_EXECUTABLE_PATH=/opt/camoufox/camoufox-bin CAMOUFOX_AUTO_INSTALL=0 \
    CAMOUFOX_HEADLESS=1 XDG_CACHE_HOME=/home/worker/.cache \
    FACEBOOK_MARKETPLACE_PROFILE_DIR=/home/worker/facebook-profile \
    SCRAPING_REVISION=$SCRAPING_REVISION
# Debian snapshot fixes native dependency versions; security updates require a reviewed rebuild.
RUN rm -f /etc/apt/sources.list.d/debian.sources \
    && printf '%s\n' \
       'deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/20260907T000000Z bookworm main' \
       'deb [check-valid-until=no] https://snapshot.debian.org/archive/debian-security/20260907T000000Z bookworm-security main' \
       > /etc/apt/sources.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg tini \
       libgtk-3-0 libx11-xcb1 libasound2 libdbus-glib-1-2 libnss3 libnspr4 \
       libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libdrm2 \
       libxtst6 libxt6 libpci3 libglib2.0-0 fonts-liberation unixodbc libgssapi-krb5-2 \
    && curl -fsSLo /tmp/msprod.deb https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb \
    && echo '8434dcb8c346dc95fbd63dbece056c343704590b58b6a5c323d39acf52bf0b48  /tmp/msprod.deb' | sha256sum -c - \
    && dpkg -i /tmp/msprod.deb && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18=18.5.1.1-1 \
    && rm -rf /var/lib/apt/lists/* /tmp/msprod.deb
COPY deploy/scraping/requirements.lock /build/requirements.lock
RUN pip install --no-cache-dir --require-hashes -r /build/requirements.lock
COPY deploy/scraping/browser.json deploy/scraping/install_browser.py /build/
RUN python /build/install_browser.py
WORKDIR /app/webapp
# Explicit source directories prevent credentials, profiles and diagnostic artifacts entering the image.
COPY webapp/manage.py ./
COPY webapp/scrapi ./scrapi
COPY webapp/ingestas ./ingestas
COPY webapp/colas ./colas
COPY webapp/intelligence/skills/base.py ./intelligence/skills/base.py
COPY webapp/intelligence/skills/scrapi ./intelligence/skills/scrapi
COPY webapp/captura/azure_storage.py ./captura/azure_storage.py
COPY webapp/templates/ingestas ./templates/ingestas
COPY deploy/scraping/entrypoint.sh /entrypoint.sh
RUN useradd --create-home --uid 10001 worker \
    && chmod 755 /entrypoint.sh \
    && mkdir -p /home/worker/.cache /home/worker/facebook-profile \
    && chown -R worker:worker /home/worker
USER worker
# Populate package fingerprint caches at build time; CI repeats this with networking disabled.
RUN python -m scrapi.worker_smoke
HEALTHCHECK --interval=30s --timeout=20s --start-period=240s --retries=3 \
    CMD ["python", "manage.py", "scraping_health"]
ENTRYPOINT ["/usr/bin/tini", "--", "/entrypoint.sh"]
