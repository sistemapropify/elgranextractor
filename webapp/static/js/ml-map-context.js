/* Optional ML context: isolated from the original portals and polygon tools. */
(function(global) {
    'use strict';
    var layers = ['eligible', 'reference', 'review', 'duplicates'];
    var colors = {eligible: '#168353', reference: '#687787', review: '#bc7614', duplicates: '#8250c8'};
    var instances = new WeakMap();
    var endpoint = '/ingestas/scraping/ml/mapa/';

    function node(tag, text) {
        var element = document.createElement(tag);
        if (text !== undefined) element.textContent = text;
        return element;
    }

    function numeric(value) {
        if (value === null || value === undefined || value === '') return null;
        var result = Number(value);
        return Number.isFinite(result) ? result : null;
    }

    function numberText(value, suffix) {
        var result = numeric(value);
        return result === null ? '—' : result.toLocaleString('es-PE', {maximumFractionDigits: 2}) + (suffix || '');
    }

    function safePublication(value) {
        try {
            var url = new URL(String(value || ''));
            return ['http:', 'https:'].indexOf(url.protocol) !== -1 ? url.href : null;
        } catch (_) {
            return null;
        }
    }

    function card(feature) {
        var box = node('div');
        box.style.cssText = 'max-width:290px;color:#162333;font:13px/1.45 system-ui;overflow-wrap:anywhere';
        box.appendChild(node('strong', '#' + feature.id + ' · ' + (feature.fuente || 'Sin portal') + ' · ' + (feature.code || 'Sin código')));
        var title = node('p', feature.title || 'Sin título');
        title.style.margin = '6px 0';
        box.appendChild(title);
        var precision = String(feature.precision || '').toLowerCase();
        var precisionLabel = precision === 'exacta' ? 'Exa · exacta declarada' :
            precision === 'aproximada' ? 'Apx · aproximada' : 'Precisión desconocida';
        box.appendChild(node('div', precisionLabel + ' · ' + (feature.geo_label || 'Ubicación sin evaluar')));
        box.appendChild(node('div', 'USD ' + numberText(feature.price_usd)));
        box.appendChild(node('div', 'Terreno: ' + numberText(feature.land_area, ' m²') +
            ' · Construcción: ' + numberText(feature.built_area, ' m²')));
        box.appendChild(node('div', 'Antigüedad: ' + (numeric(feature.age) === null ? 'Sin dato' : numberText(feature.age, ' años'))));
        box.appendChild(node('div', 'Microzona: ' + (feature.zone_name || 'Sin asignación') +
            (feature.zone_version !== null && feature.zone_version !== undefined ? ' · v' + feature.zone_version : '')));
        box.appendChild(node('div', 'ML: ' + (feature.status_label || feature.status || 'Pendiente')));
        if (numeric(feature.duplicate_count) > 0) {
            box.appendChild(node('div', numberText(feature.duplicate_count) + ' posible(s) coincidencia(s)'));
        }
        var actions = node('div');
        actions.style.cssText = 'display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;align-items:center';
        var publication = safePublication(feature.url);
        if (publication) {
            var link = node('a', 'Publicación ↗');
            link.href = publication;
            link.target = '_blank';
            link.rel = 'noopener noreferrer';
            actions.appendChild(link);
        }
        var edit = node('button', 'Ver / editar');
        edit.type = 'button';
        edit.style.cssText = 'cursor:pointer;padding:5px 8px;border:1px solid #b6c5d5;border-radius:5px;background:#f2f6fa;color:#162333';
        edit.addEventListener('click', function() {
            if (typeof global.openScrapedEditor === 'function') global.openScrapedEditor(feature.id);
        });
        actions.appendChild(edit);
        var context = node('a', 'Revisar coincidencias');
        context.href = '/ingestas/scraping/calidad/?tab=contexto&record=' + encodeURIComponent(feature.id);
        actions.appendChild(context);
        box.appendChild(actions);
        return box;
    }

    global.setupMLContextLayer = function(map) {
        if (instances.has(map)) return instances.get(map);
        var panel = document.getElementById('ml-context-layers');
        if (!panel) return null;
        var checkboxes = Array.from(panel.querySelectorAll('input[name="ml-map-layer"]'));
        checkboxes.forEach(function(input) { input.checked = false; });
        var status = document.getElementById('ml-map-status');
        var info = new google.maps.InfoWindow({maxWidth: 320});
        var markers = [];
        var timer = null;
        var controller = null;
        var sequence = 0;
        var query = new URLSearchParams(global.location.search);
        var record = query.get('ml_record');
        if (!/^[1-9]\d*$/.test(record || '')) record = null;
        var linkedLat = numeric(query.get('ml_lat')), linkedLng = numeric(query.get('ml_lng'));
        var linkedLocation = record && linkedLat !== null && linkedLng !== null &&
            linkedLat >= -19 && linkedLat <= 0 && linkedLng >= -82 && linkedLng <= -68;
        var emptyMessage = 'Marca una capa para consultar el área visible.';
        if (linkedLocation) {
            map.setCenter({lat: linkedLat, lng: linkedLng});
            map.setZoom(16);
            emptyMessage = 'Activa una capa para ver el registro #' + record + ' en esta ubicación.';
            status.textContent = emptyMessage;
        }

        function selected() {
            return checkboxes.filter(function(input) {
                return input.checked && layers.indexOf(input.value) !== -1;
            }).map(function(input) { return input.value; });
        }

        function clear() {
            markers.forEach(function(marker) { marker.setMap(null); });
            markers = [];
            info.close();
        }

        function bounds() {
            var viewport = map.getBounds();
            if (!viewport) return null;
            var southWest = viewport.getSouthWest(), northEast = viewport.getNorthEast();
            var result = {south: southWest.lat(), west: southWest.lng(), north: northEast.lat(), east: northEast.lng()};
            if (!Object.values(result).every(Number.isFinite) ||
                result.south >= result.north || result.west >= result.east) return null;
            return result;
        }

        function inside(feature, viewport) {
            var lat = numeric(feature.lat), lng = numeric(feature.lng);
            return lat !== null && lng !== null && lat >= viewport.south && lat <= viewport.north &&
                lng >= viewport.west && lng <= viewport.east;
        }

        function schedule(delay, message) {
            if (timer !== null) clearTimeout(timer);
            timer = null;
            sequence += 1;
            if (controller) controller.abort();
            controller = null;
            clear();
            if (!selected().length) {
                status.textContent = emptyMessage;
                return;
            }
            status.textContent = message || 'Consultando contexto del área visible…';
            var current = sequence;
            timer = setTimeout(function() { timer = null; load(current); }, delay);
        }

        async function load(current) {
            var selection = selected(), viewport = bounds();
            if (current !== sequence || !selection.length) return;
            if (!viewport) {
                status.textContent = 'Acerca el mapa para consultar un área visible.';
                return;
            }
            controller = new AbortController();
            var params = new URLSearchParams();
            Object.keys(viewport).forEach(function(key) { params.set(key, String(viewport[key])); });
            params.set('layers', selection.join(','));
            if (record) params.set('record', record);
            try {
                var response = await fetch(endpoint + '?' + params.toString(), {
                    credentials: 'same-origin', cache: 'no-store', signal: controller.signal,
                    headers: {'Accept': 'application/json'}
                });
                if (current !== sequence) return;
                if (!response.ok) {
                    throw new Error(response.status === 401 || response.status === 403 ?
                        'Inicia sesión para consultar el contexto ML.' :
                        response.status === 503 ? 'El contexto ML todavía no está disponible.' : 'No se pudo cargar el contexto ML.');
                }
                var data = await response.json();
                if (current !== sequence) return;
                var visibleNow = bounds();
                if (!visibleNow || Object.keys(viewport).some(function(key) {
                    return visibleNow[key] !== viewport[key];
                })) return;
                if (!data.ready) throw new Error('El contexto ML todavía no está disponible.');
                var features = Array.isArray(data.features) ? data.features : [];
                features = features.filter(function(feature) {
                    return /^[1-9]\d*$/.test(String(feature.id)) && inside(feature, viewport);
                }).slice(0, 300);
                features.forEach(function(feature) {
                    var color = selection.indexOf('duplicates') !== -1 && numeric(feature.duplicate_count) > 0 ?
                        colors.duplicates : (colors[feature.status] || colors.review);
                    var marker = new google.maps.Marker({
                        map: map,
                        position: {lat: Number(feature.lat), lng: Number(feature.lng)},
                        title: '#' + feature.id + ' · ' + (feature.fuente || '') + ' · ' + (feature.status_label || feature.status || ''),
                        icon: {path: google.maps.SymbolPath.CIRCLE, scale: 9, fillColor: color,
                            fillOpacity: 1, strokeColor: '#ffffff', strokeWeight: 2},
                        zIndex: 1500
                    });
                    marker.addListener('click', function() {
                        info.setContent(card(feature));
                        info.open({map: map, anchor: marker, shouldFocus: false});
                    });
                    markers.push(marker);
                });
                var total = numeric(data.total);
                status.textContent = features.length + ' de ' + (total === null ? features.length : total) +
                    ' registros en el área visible.' + (data.truncated ?
                        ' Límite de 300: acerca el mapa para ver el detalle.' : '');
            } catch (error) {
                if (current !== sequence || error.name === 'AbortError') return;
                clear();
                status.textContent = error.message || 'No se pudo cargar el contexto ML.';
            } finally {
                if (current === sequence) controller = null;
            }
        }

        checkboxes.forEach(function(input) {
            input.addEventListener('change', function() { schedule(0); });
        });
        map.addListener('idle', function() { schedule(350); });
        global.addEventListener('scraped-property-saved', function(event) {
            var id = event.detail && event.detail.id;
            if (!Number.isSafeInteger(id) || id <= 0) return;
            schedule(0, 'Registro guardado. Consultando contexto actualizado…');
        });
        var instance = {refresh: function() { schedule(350); }};
        instances.set(map, instance);
        // No initial request; the user must explicitly select a layer.
        return instance;
    };
})(window);
