/* Optional ML context: isolated from the original portals and polygon tools. */
(function(global) {
    'use strict';
    var layers = ['eligible', 'reference', 'review', 'duplicates'];
    var colors = {eligible: '#168353', reference: '#687787', review: '#bc7614', duplicates: '#8250c8'};
    var instances = new WeakMap();
    var endpoint = '/ingestas/scraping/ml/mapa/';
    // Un color por tipo de propiedad: es el relleno del pin (el borde mantiene
    // el color de la capa ML).
    var TYPE_COLORS = {
        Casa: '#1f6feb', Departamento: '#8957e5', Terreno: '#2ea043',
        Oficina: '#d29922', Local: '#db61a2', Propiedad: '#39c5cf',
        'Sin tipo': '#8b949e', Otro: '#6e7781'
    };
    var TYPE_FALLBACK = ['#1f6feb', '#8957e5', '#2ea043', '#d29922', '#db61a2', '#39c5cf', '#e5534b'];

    function typeColor(type) {
        var name = String(type || '').trim() || 'Sin tipo';
        if (TYPE_COLORS[name]) return TYPE_COLORS[name];
        var hash = 0;
        for (var index = 0; index < name.length; index += 1) {
            hash = (hash * 31 + name.charCodeAt(index)) % 9973;
        }
        return TYPE_FALLBACK[hash % TYPE_FALLBACK.length];
    }

    function money(value) {
        var amount = numeric(value);
        return amount === null ? '' : '$ ' + amount.toLocaleString('es-PE', {maximumFractionDigits: 0});
    }

    // Dos líneas bajo el pin: precio por m² del terreno (o de la construcción
    // si no hay terreno) y antigüedad.
    function pinLabel(feature) {
        var rows = [];
        var price = numeric(feature.price_usd);
        var land = numeric(feature.land_area), built = numeric(feature.built_area);
        if (price !== null && price > 0) {
            if (land !== null && land > 0) rows.push('AT: ' + money(price / land) + '/m2');
            else if (built !== null && built > 0) rows.push('AC: ' + money(price / built) + '/m2');
        }
        var age = numeric(feature.age);
        if (age !== null) rows.push('Años: ' + age.toLocaleString('es-PE', {maximumFractionDigits: 1}));
        return rows;
    }

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
        box.className = 'ml-map-card';
        box.appendChild(node('strong', '#' + feature.id + ' · ' + (feature.fuente || 'Sin portal') + ' · ' + (feature.code || 'Sin código')));
        var title = node('p', feature.title || 'Sin título');
        title.style.margin = '6px 0';
        box.appendChild(title);
        box.appendChild(node('div', 'Tipo: ' + (feature.property_type || 'Sin tipo')));
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

    // Sobre este volumen el navegador dibuja bien, pero conviene avisarlo.
    var HEAVY_RENDER = 3000;
    // Una consulta colgada no debe dejar el panel en "Consultando…" para siempre.
    var FETCH_TIMEOUT_MS = 25000;
    // Google reports slightly different bounds on each idle event of the same
    // viewport; a tiny tolerance avoids pointless refetches.
    var BOUND_TOLERANCE = 0.000001;

    global.setupMLContextLayer = function(map) {
        if (instances.has(map)) return instances.get(map);
        var panel = document.getElementById('ml-context-layers');
        if (!panel) return null;
        var checkboxes = Array.from(panel.querySelectorAll('input[name="ml-map-layer"]'));
        checkboxes.forEach(function(input) { input.checked = false; });
        var status = document.getElementById('ml-map-status');
        var typeButtons = document.getElementById('ml-map-types');
        var districtSelect = document.getElementById('ml-map-district');
        var knownTypes = new Set();
        // Zonas disponibles por tipo, para no perder una selección al mover el mapa.
        var knownDistricts = {};
        // Se pueden tener uno o varios tipos a la vez.
        var selectedTypes = new Set();
        var selectedDistrict = '';
        var lastResult = null;
        var savedRecordId = null;
        // disableAutoPan keeps opening a card from moving the map; a pan would
        // fire 'idle', reload the viewport and close the card just opened.
        var info = new google.maps.InfoWindow({maxWidth: 320, disableAutoPan: true});
        var markersById = new Map();
        var openFeatureId = null;
        var timer = null;
        var controller = null;
        var sequence = 0;
        var lastSuccess = null;
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

        function selectionKey() {
            return selected().join(',');
        }

        // Alcance de la consulta: capas + distrito. Con distrito se trae el
        // distrito completo; sin distrito, solo el área visible.
        function scopeKey() {
            return selectionKey() + '|' + selectedDistrict;
        }

        function clearMarkers() {
            markersById.forEach(function(marker) {
                if (marker.mlLabel) { marker.mlLabel.setMap(null); marker.mlLabel = null; }
            });
            markersById.forEach(function(marker) { marker.setMap(null); });
            markersById.clear();
            openFeatureId = null;
            lastSuccess = null;
            lastResult = null;
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

        function sameBounds(left, right) {
            if (!left || !right) return false;
            return ['south', 'west', 'north', 'east'].every(function(key) {
                return Math.abs(left[key] - right[key]) <= BOUND_TOLERANCE;
            });
        }

        function inside(feature, viewport) {
            var lat = numeric(feature.lat), lng = numeric(feature.lng);
            return lat !== null && lng !== null && lat >= viewport.south && lat <= viewport.north &&
                lng >= viewport.west && lng <= viewport.east;
        }

        function strokeColor(feature, key) {
            if (key.indexOf('duplicates') !== -1 && numeric(feature.duplicate_count) > 0) {
                return colors.duplicates;
            }
            return colors[feature.status] || colors.review;
        }

        // Relleno: tipo de propiedad. Borde: capa ML a la que pertenece.
        function markerIcon(feature, key) {
            return {path: google.maps.SymbolPath.CIRCLE, scale: 9,
                fillColor: typeColor(propertyTypeOf(feature)), fillOpacity: 1,
                strokeColor: strokeColor(feature, key), strokeWeight: 3};
        }

        // Etiqueta bajo el pin, con el mismo patrón de overlay que las tarjetas.
        function labelOverlay(position) {
            var overlay = new google.maps.OverlayView();
            overlay.__position = position;
            overlay.onAdd = function() {
                var div = document.createElement('div');
                div.className = 'ml-pin-label';
                this.__div = div;
                this.getPanes().overlayLayer.appendChild(div);
            };
            overlay.draw = function() {
                if (!this.__div) return;
                var projection = this.getProjection();
                if (!projection || !this.__position) return;
                var point = projection.fromLatLngToDivPixel(this.__position);
                if (!point) return;
                this.__div.style.left = point.x + 'px';
                this.__div.style.top = (point.y + 12) + 'px';
            };
            overlay.onRemove = function() {
                if (this.__div && this.__div.parentNode) this.__div.parentNode.removeChild(this.__div);
                this.__div = null;
            };
            overlay.setMap(map);
            return overlay;
        }

        function updateLabel(marker, feature) {
            var rows = pinLabel(feature);
            if (!rows.length) {
                if (marker.mlLabel) { marker.mlLabel.setMap(null); marker.mlLabel = null; }
                return;
            }
            if (!marker.mlLabel) marker.mlLabel = labelOverlay(marker.getPosition());
            else marker.mlLabel.__position = marker.getPosition();
            if (!marker.mlLabel.__div) return;
            marker.mlLabel.__div.innerHTML = '';
            rows.forEach(function(row) {
                var line = document.createElement('div');
                line.textContent = row;
                marker.mlLabel.__div.appendChild(line);
            });
        }

        function markerTitle(feature) {
            return '#' + feature.id + ' · ' + propertyTypeOf(feature) + ' · ' + (feature.fuente || '') + ' · ' +
                (feature.status_label || feature.status || '');
        }

        // Refresh only what changed. Reusing the surviving markers keeps the
        // layer steady while panning and keeps the card the user opened alive.
        function draw(features, key) {
            var visible = new Set();
            features.forEach(function(feature) {
                var id = String(feature.id);
                visible.add(id);
                var marker = markersById.get(id);
                if (marker) {
                    marker.setPosition({lat: Number(feature.lat), lng: Number(feature.lng)});
                    marker.setIcon(markerIcon(feature, key));
                    marker.setTitle(markerTitle(feature));
                } else {
                    marker = new google.maps.Marker({
                        map: map,
                        position: {lat: Number(feature.lat), lng: Number(feature.lng)},
                        title: markerTitle(feature),
                        icon: markerIcon(feature, key),
                        zIndex: 1500
                    });
                    marker.addListener('click', function() {
                        openFeatureId = id;
                        info.setContent(card(marker.mlFeature));
                        info.open({map: map, anchor: marker, shouldFocus: false});
                    });
                    markersById.set(id, marker);
                }
                marker.mlFeature = feature;
                updateLabel(marker, feature);
                if (openFeatureId === id) info.setContent(card(feature));
            });
            markersById.forEach(function(marker, id) {
                if (visible.has(id)) return;
                if (marker.mlLabel) { marker.mlLabel.setMap(null); marker.mlLabel = null; }
                marker.setMap(null);
                markersById.delete(id);
                if (openFeatureId === id) {
                    openFeatureId = null;
                    info.close();
                }
            });
        }

        function propertyTypeOf(feature) {
            return String(feature.property_type || '').trim() || 'Sin tipo';
        }

        function selectedTypeLabel() {
            return Array.from(selectedTypes).sort(function(left, right) {
                return left.localeCompare(right, 'es', {sensitivity: 'base'});
            }).join(', ');
        }

        function districtOf(feature) {
            return String(feature.district || '').trim() || 'Sin distrito';
        }

        function fillSelect(select, values, defaultLabel) {
            if (!select) return;
            select.innerHTML = '';
            var all = node('option', defaultLabel);
            all.value = '';
            select.appendChild(all);
            values.sort(function(left, right) {
                return left.localeCompare(right, 'es', {sensitivity: 'base'});
            }).forEach(function(value) {
                var option = node('option', value);
                option.value = value;
                select.appendChild(option);
            });
        }

        // Botones de tipo: se combinan los que se quieran (Casa + Terreno).
        // Volver a pulsar uno lo quita de la selección.
        function renderTypeButtons() {
            if (!typeButtons) return;
            typeButtons.innerHTML = '';
            Array.from(knownTypes).sort(function(left, right) {
                return left.localeCompare(right, 'es', {sensitivity: 'base'});
            }).forEach(function(value) {
                var active = selectedTypes.has(value);
                var button = node('button', value);
                button.type = 'button';
                button.className = 'ml-type-button' + (active ? ' active' : '');
                button.setAttribute('aria-pressed', active ? 'true' : 'false');
                button.style.borderColor = typeColor(value);
                if (active) button.style.background = typeColor(value);
                button.addEventListener('click', function() {
                    if (selectedTypes.has(value)) selectedTypes.delete(value);
                    else selectedTypes.add(value);
                    renderTypeButtons();
                    refreshDistrictOptions();
                    applyFilters();
                });
                typeButtons.appendChild(button);
            });
        }

        function refreshTypeOptions(features) {
            features.forEach(function(feature) {
                var type = propertyTypeOf(feature);
                knownTypes.add(type);
                if (!knownDistricts[type]) knownDistricts[type] = new Set();
                knownDistricts[type].add(districtOf(feature));
            });
            // Mantener la elección del usuario mientras se recarga el alcance.
            selectedTypes.forEach(function(type) {
                if (!knownTypes.has(type)) selectedTypes.delete(type);
            });
            renderTypeButtons();
            refreshDistrictOptions();
        }

        // Los distritos dependen de los tipos elegidos: se listan los que tienen
        // registros de cualquiera de ellos en lo ya consultado.
        function refreshDistrictOptions() {
            if (!districtSelect) return;
            var union = new Set();
            selectedTypes.forEach(function(type) {
                (knownDistricts[type] || new Set()).forEach(function(name) { union.add(name); });
            });
            var districts = Array.from(union);
            fillSelect(districtSelect, districts, 'Todos los distritos');
            districtSelect.disabled = !selectedTypes.size || !districts.length;
            if (!selectedTypes.size || districts.indexOf(selectedDistrict) === -1) selectedDistrict = '';
            districtSelect.value = selectedDistrict;
        }

        function filteredFeatures() {
            if (!lastResult) return [];
            // Nada se dibuja hasta elegir un tipo: el mapa queda limpio y el
            // navegador no arma miles de pines que nadie pidió.
            if (!selectedTypes.size) return [];
            return lastResult.features.filter(function(feature) {
                return selectedTypes.has(propertyTypeOf(feature)) &&
                    (!selectedDistrict || districtOf(feature) === selectedDistrict);
            });
        }

        // Capa a la que pertenece un registro según su evaluación vigente.
        function layerOf(feature) {
            if (feature.status === 'eligible') return 'eligible';
            if (feature.status === 'reference') return 'reference';
            return 'review';
        }

        function layerLabel(layer) {
            return {eligible: 'Candidatas', reference: 'Referencias', review: 'Por revisar'}[layer] || layer;
        }

        // Al corregir, el registro cambia de estado y de tipo: puede quedar fuera
        // de la capa activa o de los filtros. Se busca por su id con todas las
        // capas y se ajusta la vista para que el usuario lo vuelva a ver.
        function reattachSavedRecord(id) {
            var viewport = bounds();
            if (!viewport || !id) return Promise.resolve();
            var params = new URLSearchParams();
            Object.keys(viewport).forEach(function(name) { params.set(name, String(viewport[name])); });
            params.set('layers', layers.join(','));
            params.set('record', String(id));
            return fetch(endpoint + '?' + params.toString(), {
                credentials: 'same-origin', cache: 'no-store', headers: {'Accept': 'application/json'}
            })
                .then(function(response) { return response.ok ? response.json() : null; })
                .then(function(data) {
                    var feature = data && Array.isArray(data.features) ? data.features[0] : null;
                    if (!feature) {
                        status.textContent = 'El registro #' + id +
                            ' no tiene coordenadas o no está en el seguimiento ML; ábrelo desde Calidad.';
                        return;
                    }
                    var target = layerOf(feature), adjusted = false;
                    checkboxes.forEach(function(input) {
                        if (input.value === target && !input.checked) { input.checked = true; adjusted = true; }
                    });
                    if (!selectedTypes.has(propertyTypeOf(feature))) {
                        knownTypes.add(propertyTypeOf(feature));
                        selectedTypes.add(propertyTypeOf(feature));
                        adjusted = true;
                    }
                    if (selectedDistrict && districtOf(feature) !== selectedDistrict) {
                        selectedDistrict = '';
                        adjusted = true;
                    }
                    // Si la corrección movió el registro fuera del área, se
                    // lleva el mapa hasta él para que no se pierda de vista.
                    var lat = numeric(feature.lat), lng = numeric(feature.lng);
                    var visible = bounds();
                    var outside = lat !== null && lng !== null && (!visible ||
                        lat < visible.south || lat > visible.north || lng < visible.west || lng > visible.east);
                    if (outside) {
                        map.setCenter({lat: lat, lng: lng});
                        if (typeof map.getZoom === 'function' && map.getZoom() < 16) map.setZoom(16);
                        adjusted = true;
                    }
                    // Reflejar en los selectores lo que se acaba de ajustar.
                    renderTypeButtons();
                    refreshDistrictOptions();
                    var message = 'Registro #' + id + ' guardado: quedó en «' + layerLabel(target) + '»';
                    message += selectedTypes.size ? ' · tipo ' + selectedTypeLabel() : '';
                    message += (selectedDistrict ? ' · ' + selectedDistrict : '') + '.';
                    if (adjusted) schedule(0, message);
                    else status.textContent = message;
                })
                .catch(function() { /* el aviso de guardado original se conserva */ });
        }

        // Los filtros corren en el cliente: elegir tipo o distrito no vuelve a
        // consultar el área ni reinicia la capa.
        function applyFilters() {
            if (!lastResult) return;
            var features = filteredFeatures();
            draw(features, lastResult.key);
            var scope = selectedDistrict ? ' en el distrito ' + selectedDistrict : ' en el área visible';
            if (!selectedTypes.size) {
                status.textContent = lastResult.features.length +
                    (lastResult.features.length === 1 ? ' registro' : ' registros') + scope +
                    '. Elige uno o varios tipos de propiedad para verlos.';
                return;
            }
            var label = features.length + (features.length === 1 ? ' registro de ' : ' registros de ') +
                selectedTypeLabel() + scope + '.';
            var hidden = lastResult.features.length - features.length;
            status.textContent = label +
                (hidden > 0 ? ' ' + hidden + ' quedan fuera por el tipo elegido.' : '') +
                (features.length > HEAVY_RENDER ? ' Son muchos pines: el mapa puede tardar en moverse.' : '');
        }

        function schedule(delay, message, force) {
            if (timer !== null) clearTimeout(timer);
            timer = null;
            sequence += 1;
            if (controller) controller.abort();
            controller = null;
            var key = selectionKey();
            if (!key) {
                clearMarkers();
                // Sin capas activas no hay dónde reubicar el registro guardado.
                savedRecordId = null;
                status.textContent = emptyMessage;
                return;
            }
            // A saved record (or an explicit refresh) must requery even when the
            // viewport and the layers did not change.
            if (force) lastSuccess = null;
            // Changing layers makes the current pins stale; drop them now
            // instead of leaving a layer the user just turned off on screen.
            if (lastSuccess && lastSuccess.key !== scopeKey()) clearMarkers();
            var current = sequence;
            timer = setTimeout(function() { timer = null; load(current, message); }, delay);
        }

        async function load(current, message) {
            var selection = selected(), viewport = bounds(), district = selectedDistrict;
            if (current !== sequence || !selection.length) return;
            if (!viewport) {
                status.textContent = 'Acerca el mapa para consultar un área visible.';
                return;
            }
            var key = scopeKey();
            // 'idle' also fires when the map merely finished drawing; never
            // requery a scope that already answered. Con distrito el alcance es
            // el distrito completo, así que mover el mapa no cambia la consulta.
            if (lastSuccess && lastSuccess.key === key &&
                (district || sameBounds(lastSuccess.viewport, viewport))) return;
            status.textContent = message || (district ?
                'Consultando el distrito ' + district + '…' : 'Consultando contexto del área visible…');
            controller = new AbortController();
            var timedOut = false;
            var timeoutId = setTimeout(function() {
                timedOut = true;
                controller.abort();
            }, FETCH_TIMEOUT_MS);
            var params = new URLSearchParams();
            Object.keys(viewport).forEach(function(name) { params.set(name, String(viewport[name])); });
            params.set('layers', selection.join(','));
            if (district) params.set('district', district);
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
                if (!district) {
                    var visibleNow = bounds();
                    if (!visibleNow || !sameBounds(visibleNow, viewport)) return;
                }
                if (!data.ready) throw new Error('El contexto ML todavía no está disponible.');
                var features = Array.isArray(data.features) ? data.features : [];
                features = features.filter(function(feature) {
                    return /^[1-9]\d*$/.test(String(feature.id)) &&
                        (district ? true : inside(feature, viewport));
                });
                lastSuccess = {key: key, viewport: district ? null : viewport};
                lastResult = {features: features, total: numeric(data.total), key: key};
                refreshTypeOptions(features);
                applyFilters();
                if (savedRecordId !== null && savedRecordId !== undefined) {
                    var pending = savedRecordId;
                    savedRecordId = null;
                    reattachSavedRecord(pending);
                }
            } catch (error) {
                if (current !== sequence) return;
                if (error.name === 'AbortError' && !timedOut) return;
                status.textContent = timedOut ?
                    'La consulta tardó demasiado. Acota con tipo de propiedad o distrito.' :
                    (error.message || 'No se pudo cargar el contexto ML.');
            } finally {
                clearTimeout(timeoutId);
                if (current === sequence) controller = null;
            }
        }

        checkboxes.forEach(function(input) {
            input.addEventListener('change', function() { schedule(0); });
        });
        if (districtSelect) {
            districtSelect.addEventListener('change', function() {
                selectedDistrict = districtSelect.value;
                // El distrito es el alcance completo: se vuelve a consultar.
                schedule(0);
            });
        }
        map.addListener('idle', function() { schedule(350); });
        global.addEventListener('scraped-property-saved', function(event) {
            var id = event.detail && event.detail.id;
            if (!Number.isSafeInteger(id) || id <= 0) return;
            // The saved record's card shows pre-save values; close it but keep
            // the pins steady until the refreshed data arrives.
            openFeatureId = null;
            info.close();
            savedRecordId = id;
            schedule(0, 'Registro guardado. Consultando contexto actualizado…', true);
        });
        var instance = {refresh: function() { schedule(350, null, true); }};
        instances.set(map, instance);
        // No initial request; the user must explicitly select a layer.
        return instance;
    };
})(window);
