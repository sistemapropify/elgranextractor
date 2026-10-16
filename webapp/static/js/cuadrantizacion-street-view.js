/* Native Google Street View; requests run only on an explicit user action. */
(() => {
    'use strict';
    const instances = new WeakMap();
    function init(map) {
        if (instances.has(map)) return instances.get(map);
        const get = id => document.getElementById(id);
        const container = get('map-container'), button = get('cuadra-streetview-open');
        if (!container || !button || typeof map.getStreetView !== 'function') return;
        const panorama = map.getStreetView();
        const toolbar = get('cuadra-streetview-toolbar'), close = get('cuadra-streetview-close');
        const message = get('cuadra-streetview-status');
        let service = null, request = 0, timeout = null, wasVisible = false;
        function status(text, error = false) {
            message.textContent = text;
            message.dataset.error = String(error);
        }
        function finish() {
            clearTimeout(timeout);
            timeout = null;
            button.disabled = false;
            button.textContent = 'Ver calle en el centro';
        }
        function sync() {
            const visible = panorama.getVisible();
            container.classList.toggle('cuadra-streetview-active', visible);
            toolbar.hidden = !visible;
            if (visible) {
                request++;
                finish();
                status('Street View abierto. Puedes recorrer la calle y volver al mapa.');
            } else if (wasVisible) {
                request++;
                finish();
                status('Vista cerrada. Puedes elegir otra calle desde el mapa.');
            }
            wasVisible = visible;
        }
        function closeViewer() {
            request++;
            finish();
            panorama.setVisible(false);
            status('Centra el mapa en el punto que quieres revisar o arrastra el muñeco amarillo a una calle.');
            button.focus();
        }
        function openCenter() {
            const target = map.getCenter();
            if (!target) { status('Espera a que termine de cargar el mapa.', true); return; }
            const stamp = ++request;
            if (!service) service = new google.maps.StreetViewService();
            button.disabled = true;
            button.textContent = 'Buscando vista…';
            status('Buscando imágenes de calle a menos de 100 m del centro del mapa…');
            timeout = setTimeout(() => {
                if (stamp !== request) return;
                request++;
                finish();
                status('Google no respondió a tiempo. Puedes volver a intentarlo.', true);
            }, 15000);
            try {
                service.getPanorama({location: target, radius: 100,
                    preference: google.maps.StreetViewPreference.NEAREST}, (result, code) => {
                    if (stamp !== request) return;
                    finish();
                    if (code !== 'OK' || !result?.location?.pano) {
                        status(code === 'ZERO_RESULTS'
                            ? 'No hay Street View disponible a menos de 100 m. Centra el mapa en otra calle.'
                            : 'No se pudo abrir Street View. Comprueba la conexión o la configuración de Google Maps.', true);
                        return;
                    }
                    const spherical = google.maps.geometry?.spherical;
                    panorama.setPano(result.location.pano);
                    if (spherical && result.location.latLng) {
                        panorama.setPov({heading: spherical.computeHeading(result.location.latLng, target), pitch: 0});
                    }
                    panorama.setVisible(true);
                });
            } catch (_) {
                request++;
                finish();
                status('No se pudo consultar Street View. Vuelve a intentarlo.', true);
            }
        }
        button.addEventListener('click', openCenter);
        close.addEventListener('click', closeViewer);
        panorama.addListener('visible_changed', sync);
        const instance = {close: closeViewer};
        instances.set(map, instance);
        sync();
        return instance;
    }
    window.CuadraStreetView = {init};
})();
