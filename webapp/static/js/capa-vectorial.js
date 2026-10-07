/* ============================================================================
 * Capas vectoriales del plano sobre Google Maps
 *
 * Dibuja GeoJSON como vectores: polígonos de zonificación (relleno sólido),
 * estructura vial (líneas negras con el grosor de cada nivel) y rótulos con
 * los códigos de zona. Cada capa tiene su propio control de visibilidad y
 * transparencia.
 *
 * Al ser vectores, los límites se mantienen como líneas exactas a cualquier
 * zoom, igual que las calles de Google Maps.
 * ==========================================================================*/
(function () {
    'use strict';

    var DATA_ID = 'capas-vectoriales-data';
    var CONTROLES_ID = 'capas-vectoriales-controles';

    var map = null;
    var capas = [];

    function $(id) { return document.getElementById(id); }

    function numero(valor, porDefecto) {
        var n = Number(valor);
        return isFinite(n) ? n : porDefecto;
    }

    /* ------------------------------ polígonos y líneas ---------------- */

    function estiloDe(capa) {
        return function (feature) {
            var datos = capa.datos;
            var opacidad = capa.visible ? capa.opacidad : 0;
            if (datos.tipo === 'lineas') {
                var ancho = numero(feature.getProperty('ancho'), 1);
                return {
                    strokeColor: feature.getProperty('color') || datos.color_borde || '#000000',
                    strokeOpacity: opacidad,
                    strokeWeight: Math.max(0.6, ancho * numero(datos.escala_ancho, 0.8)),
                    clickable: false
                };
            }
            var color = feature.getProperty(datos.propiedad_color) || '#8b949e';
            var borde = datos.color_borde || '';
            return {
                fillColor: color,
                fillOpacity: opacidad,
                strokeColor: borde || color,
                strokeOpacity: borde ? Math.min(1, opacidad + 0.25) : 0,
                strokeWeight: numero(datos.grosor_borde, 0.4),
                clickable: false,
                zIndex: numero(feature.getProperty('orden'), 0)
            };
        };
    }

    function repintar(capa) {
        if (capa.data) capa.data.setStyle(estiloDe(capa));
        if (capa.actualizarEtiquetas) capa.actualizarEtiquetas();
    }

    function montarDataLayer(capa) {
        capa.data = new google.maps.Data({ map: map });
        capa.data.setStyle(estiloDe(capa));
        capa.data.loadGeoJson(capa.datos.geojson_url, null, function (features) {
            console.info('capa.vectorial.lista', capa.datos.nombre, features.length);
            repintar(capa);
        });
    }

    /* ------------------------------ rótulos --------------------------- */

    function montarRotulos(capa) {
        var divs = [];
        var puntos = [];
        var contenedor = document.createElement('div');
        // z-index dentro del panel de superposición: los rótulos quedan por
        // encima de los polígonos y de las líneas, pero por debajo de los pines.
        contenedor.style.cssText =
            'position:absolute;left:0;top:0;pointer-events:none;z-index:10';

        var overlay = new google.maps.OverlayView();
        var tamanoBase = numero(capa.datos.tamano_rotulo, 13);
        var ultimoZoom = null;
        overlay.onAdd = function () {
            this.getPanes().overlayLayer.appendChild(contenedor);
        };
        overlay.draw = function () {
            var proyeccion = this.getProjection();
            if (!proyeccion) return;
            var zoom = map.getZoom();
            var mostrar = capa.visible && zoom >= numero(capa.datos.zoom_minimo, 0);
            contenedor.style.display = mostrar ? 'block' : 'none';
            contenedor.style.opacity = capa.opacidad;
            if (!mostrar) return;
            // El rótulo crece con el zoom para mantener la proporción con el mapa.
            if (zoom !== ultimoZoom) {
                var tamano = Math.round(tamanoBase * (1 + Math.max(0, zoom - 14) * 0.12));
                for (var j = 0; j < divs.length; j++) {
                    divs[j].style.fontSize = tamano + 'px';
                }
                ultimoZoom = zoom;
            }
            for (var i = 0; i < puntos.length; i++) {
                var div = divs[i];
                if (!div) continue;
                var p = proyeccion.fromLatLngToDivPixel(puntos[i]);
                if (!p) { div.style.display = 'none'; continue; }
                div.style.display = 'block';
                div.style.left = p.x + 'px';
                div.style.top = p.y + 'px';
            }
        };
        overlay.onRemove = function () {
            if (contenedor.parentNode) contenedor.parentNode.removeChild(contenedor);
        };
        overlay.setMap(map);

        capa.actualizarEtiquetas = function () { overlay.draw(); };

        fetch(capa.datos.geojson_url, { credentials: 'same-origin' })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (datos) {
                if (!datos || !datos.features) return;
                var tamano = numero(capa.datos.tamano_rotulo, 10);
                datos.features.forEach(function (feature) {
                    var coordenadas = feature.geometry && feature.geometry.coordinates;
                    if (!coordenadas) return;
                    var div = document.createElement('div');
                    div.className = 'capa-rotulo';
                    div.style.cssText =
                        'position:absolute;transform:translate(-50%,-50%);' +
                        'font:' + tamano + 'px/1.1 system-ui,-apple-system,Segoe UI,sans-serif;' +
                        'font-weight:600;color:' + (capa.datos.color_borde || '#111') + ';' +
                        'text-shadow:0 0 3px #fff,0 0 3px #fff,0 0 2px #fff;' +
                        'white-space:nowrap';
                    div.textContent = feature.properties[capa.datos.propiedad_codigo] || '';
                    contenedor.appendChild(div);
                    divs.push(div);
                    puntos.push(new google.maps.LatLng(coordenadas[1], coordenadas[0]));
                });
                overlay.draw();
            })
            .catch(function (error) {
                console.warn('capa.vectorial.rotulos', error);
            });
    }

    /* ------------------------------ panel ----------------------------- */

    function construirPanel() {
        var contenedor = $(CONTROLES_ID);
        if (!contenedor) return;
        contenedor.innerHTML = '';

        // Una casilla por capa y un único control de transparencia para todas.
        capas.forEach(function (capa) {
            var bloque = document.createElement('div');
            bloque.className = 'capa-vectorial-bloque';

            var etiqueta = document.createElement('label');
            etiqueta.className = 'capa-raster-toggle';
            var casilla = document.createElement('input');
            casilla.type = 'checkbox';
            casilla.checked = capa.visible;
            var texto = document.createElement('span');
            texto.textContent = capa.datos.nombre;
            etiqueta.appendChild(casilla);
            etiqueta.appendChild(texto);

            casilla.addEventListener('change', function () {
                capa.visible = casilla.checked;
                repintar(capa);
            });

            bloque.appendChild(etiqueta);
            contenedor.appendChild(bloque);
        });

        var control = document.createElement('div');
        control.className = 'capa-raster-control';
        var titulo = document.createElement('label');
        var valor = document.createElement('span');
        valor.className = 'capa-raster-valor';
        titulo.appendChild(document.createTextNode('Transparencia '));
        titulo.appendChild(valor);
        var rango = document.createElement('input');
        rango.type = 'range';
        rango.min = '0';
        rango.max = '100';
        rango.step = '1';
        rango.id = 'capas-vectoriales-transparencia';
        control.appendChild(titulo);
        control.appendChild(rango);
        contenedor.appendChild(control);

        function pintarValor() {
            var referencia = capas.length ? capas[0].opacidad : 0.65;
            var transparencia = Math.round((1 - referencia) * 100);
            rango.value = String(transparencia);
            valor.textContent = transparencia + '%';
        }
        pintarValor();

        rango.addEventListener('input', function () {
            var opacidad = Math.max(0, Math.min(1, 1 - parseFloat(rango.value) / 100));
            valor.textContent = Math.round(parseFloat(rango.value)) + '%';
            capas.forEach(function (capa) {
                capa.opacidad = opacidad;
                repintar(capa);
            });
        });
    }

    /* ------------------------------ arranque -------------------------- */

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

        // Con capas vectoriales activas, el panel de la imagen no se usa.
        var panelRaster = $('panel-capa-raster');
        if (panelRaster) panelRaster.style.display = 'none';

        capas = datos
            .slice()
            .sort(function (a, b) { return numero(a.orden, 0) - numero(b.orden, 0); })
            .map(function (capa) {
                return {
                    datos: capa,
                    visible: capa.visible !== false,
                    opacidad: numero(capa.opacidad, 0.65),
                };
            });

        construirPanel();
        capas.forEach(function (capa) {
            if (capa.datos.tipo === 'etiquetas') montarRotulos(capa);
            else montarDataLayer(capa);
        });
    }

    window.CapaVectorial = { init: init, capas: capas };
})();
