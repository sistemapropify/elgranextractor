/* ============================================================================
 * Capa vectorial de zonificación sobre Google Maps
 *
 * Dibuja los polígonos del plano (GeoJSON) como vectores, no como imagen. Los
 * límites entre zonas quedan como líneas exactas a cualquier zoom, igual que
 * las calles de Google Maps, y los colores son los sólidos de la leyenda.
 *
 * Controles: transparencia del relleno y mostrar u ocultar la capa.
 * ==========================================================================*/
(function () {
    'use strict';

    var DATA_ID = 'capas-vectoriales-data';

    var map = null;
    var capas = [];
    var activa = 0;
    var capaGoogle = null;

    function $(id) { return document.getElementById(id); }

    function capaActual() { return capas[activa]; }

    function opacidadActual() {
        var capa = capaActual();
        return capa ? capa.opacidad : 0.65;
    }

    function visibleActual() {
        var capa = capaActual();
        return capa ? capa.visible : true;
    }

    function estilo(feature) {
        var capa = capaActual();
        if (!capa) return {};
        var color = feature.getProperty(capa.propiedad_color) || '#8b949e';
        var opacidad = visibleActual() ? opacidadActual() : 0;
        var borde = capa.color_borde || '';
        return {
            fillColor: color,
            fillOpacity: opacidad,
            strokeColor: borde || color,
            strokeOpacity: borde ? Math.min(1, opacidad + 0.25) : 0,
            strokeWeight: capa.grosor_borde || 0.4,
            clickable: false,
            zIndex: Number(feature.getProperty('orden')) || 0
        };
    }

    function repintar() {
        if (capaGoogle) capaGoogle.setStyle(estilo);
    }

    function montar() {
        var capa = capaActual();
        if (!capa || !capa.geojson_url) return;

        capaGoogle = new google.maps.Data({ map: map });
        capaGoogle.setStyle(estilo);
        capaGoogle.loadGeoJson(capa.geojson_url, null, function (features) {
            console.info('capa.vectorial.lista', capa.nombre, features.length, 'poligonos');
            repintar();
        });
    }

    function estado() {
        var el = $('capa-vectorial-estado');
        if (!el) return;
        el.textContent = capas.length
            ? capas.length + ' capa(s) · ' + capaActual().nombre
            : '';
    }

    function refrescarPanel() {
        var capa = capaActual();
        if (!capa) return;
        var transparencia = Math.round((1 - capa.opacidad) * 100);
        var rango = $('capa-vectorial-transparencia');
        var visible = $('capa-vectorial-visible');
        var valor = $('capa-vectorial-transparencia-val');
        if (rango) rango.value = transparencia;
        if (valor) valor.textContent = transparencia + '%';
        if (visible) visible.checked = capa.visible;
        estado();
    }

    function conectarPanel() {
        var capa = capaActual();
        if (!capa) return;

        var rango = $('capa-vectorial-transparencia');
        if (rango) {
            rango.addEventListener('input', function () {
                capa.opacidad = Math.max(0, Math.min(1, 1 - parseFloat(rango.value) / 100));
                var valor = $('capa-vectorial-transparencia-val');
                if (valor) valor.textContent = Math.round(parseFloat(rango.value)) + '%';
                repintar();
            });
        }

        var casilla = $('capa-vectorial-visible');
        if (casilla) {
            casilla.addEventListener('change', function () {
                capa.visible = casilla.checked;
                repintar();
            });
        }
    }

    function init(googleMap) {
        map = googleMap;
        var nodo = $(DATA_ID);
        var datos = [];
        if (nodo) {
            try { datos = JSON.parse(nodo.textContent) || []; } catch (error) { datos = []; }
        }
        datos = datos.filter(function (capa) { return capa && capa.geojson_url; });

        var panel = $('panel-capa-vectorial');
        if (!datos.length) {
            if (panel) panel.style.display = 'none';
            return;
        }
        if (panel) panel.style.display = '';

        // Si hay capa vectorial, el panel de la imagen no se usa.
        var panelRaster = $('panel-capa-raster');
        if (panelRaster) panelRaster.style.display = 'none';

        capas = datos;
        refrescarPanel();
        conectarPanel();
        montar();
    }

    window.CapaVectorial = { init: init, repintar: repintar };
})();
