FROM scraping-worker:test
USER root
COPY deploy/integration/requirements.lock /build/integration-requirements.lock
RUN pip install --no-cache-dir --require-hashes --no-deps -r /build/integration-requirements.lock && pip check
WORKDIR /app/webapp
COPY webapp/intelligence ./intelligence
COPY webapp/lead_intelligence ./lead_intelligence
COPY webapp/prospects ./prospects
COPY webapp/response_intelligence ./response_intelligence
COPY webapp/n8n_bridge ./n8n_bridge
COPY webapp/analisis_crm ./analisis_crm
COPY webapp/captura ./captura
COPY webapp/templates ./templates
COPY webapp/integration_test_settings.py webapp/integration_test_urls.py webapp/integration_test_runner.py webapp/integration_suite.py ./
USER worker
ENV DJANGO_SETTINGS_MODULE=integration_test_settings
