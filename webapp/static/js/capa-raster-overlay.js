/* ============================================================================
 * Capa raster georreferenciada sobre Google Maps (cuadrantización)
 *
 * Superpone un plano en formato imagen (por ejemplo la Zonificación del PDM
 * Arequipa 2016-2025) sobre el mapa base y permite calibrarlo:
 * transparencia, giro, escala, desplazamiento y bloqueo.
 *
 * El encaje geográfico viene de las esquinas de la imagen (longitud/latitud)
 * guardadas en el modelo CapaRasterMapa. El ajuste fino se aplica encima y se
 * guarda en la base de datos, así que la capa queda igual para todos.
 * ==========================================================================*/
(function () {
    'use strict';

    var ENDPOINT = '/cuadrantizacion/capas-raster/';
    var DATA_ID = 'capas-raster-data';
    // Se sube cuando cambia el archivo de la capa: el nombre no cambia y la
    // capa se sirve con caché larga, así que hay que forzar la recarga.
    var VERSION_CAPA = '4';

    var map = null;
    var capas = [];
    var activa = 0;
    var listeners = [], idleListener = null;
    function bind(el, name, handler) {
        if (!el) return;
        el.addEventListener(name, handler);
        listeners.push([el, name, handler]);
    }
    function clear() {
        listeners.forEach(function (entry) { entry[0].removeEventListener(entry[1], entry[2]); });
        listeners = [];
        if (idleListener) google.maps.event.removeListener(idleListener);
        idleListener = null;
        capas.forEach(function (capa) { capa.overlayInstance.setMap(null); });
        capas = [];
        var selector = $('capa-raster-select');
        if (selector) selector.replaceChildren();
    }

    /* ----------------------------- utilidades ---------------------------- */

    function $(id) { return document.getElementById(id); }

    function urlConVersion(url) {
        if (!url) return url;
        return url + (url.indexOf('?') === -1 ? '?' : '&') + 'v=' + VERSION_CAPA;
    }

    function setValor(id, valor) {
        var el = $(id);
        if (el) el.value = valor;
    }

    function setTexto(id, valor) {
        var el = $(id);
        if (el) el.textContent = valor;
    }

    function setChecked(id, valor) {
        var el = $(id);
        if (el) el.checked = !!valor;
    }

    function alClic(id, manejador) {
        var el = $(id);
        bind(el, 'click', manejador);
    }

    function alCambiar(id, manejador) {
        var el = $(id);
        bind(el, 'change', manejador);
    }

    function mulMatrix(m, n) {
        return {
            a: m.a * n.a + m.c * n.b,
            b: m.b * n.a + m.d * n.b,
            c: m.a * n.c + m.c * n.d,
            d: m.b * n.c + m.d * n.d,
            e: m.a * n.e + m.c * n.f + m.e,
            f: m.b * n.e + m.d * n.f + m.f
        };
    }

    function applyMatrix(m, x, y) {
        return [m.a * x + m.c * y + m.e, m.b * x + m.d * y + m.f];
    }

    function clamp(value, min, max) {
        return Math.max(min, Math.min(max, value));
    }

    function setStatus(mensaje, esError) {
        var el = $('capa-raster-estado');
        if (!el) return;
        el.textContent = mensaje || '';
        el.style.color = esError ? '#f85149' : '';
    }

    function csrfToken() {
        var input = document.querySelector('[name=csrfmiddlewaretoken]');
        return input ? input.value : '';
    }

    /* ------------------------------ la capa ------------------------------ */

    function CapaRaster(datos, googleMap) {
        this.datos = datos;
        this.map = googleMap;
        this.image = null;
        this.handle = null;
        this.projection = null;
        this.width = 0;
        this.height = 0;
        // Ajuste en memoria (se copia al abrir para poder restablecer)
        this.ajuste = {
            opacidad: typeof datos.opacidad === 'number' ? datos.opacidad : 0.65,
            rotacion: datos.rotacion || 0,
            escala: datos.escala || 1,
            offset_x: datos.offset_x || 0,
            offset_y: datos.offset_y || 0
        };
        this.guardado = Object.assign({}, this.ajuste);
        this.bloqueado = !!datos.bloqueado;
        this.visible = datos.visible !== false;
        this.build();
    }

    CapaRaster.prototype.build = function () {
        var self = this;

        this.overlay = function () {};
        this.overlay.prototype = new google.maps.OverlayView();

        this.overlay.prototype.onAdd = function () {
            var div = document.createElement('div');
            div.style.cssText =
                'position:absolute;left:0;top:0;will-change:transform;pointer-events:none';

            var img = document.createElement('img');
            img.src = urlConVersion(self.datos.imagen_url);
            img.alt = self.datos.nombre || 'Capa raster';
            img.draggable = false;
            img.style.cssText =
                'position:absolute;left:0;top:0;transform-origin:0 0;' +
                'user-select:none;-webkit-user-drag:none;pointer-events:none';
            img.onload = function () {
                self.width = img.naturalWidth;
                self.height = img.naturalHeight;
                self.draw();
            };
            div.appendChild(img);
            self.container = div;
            self.image = img;
            this.getPanes().overlayLayer.appendChild(div);

            // Mango de arrastre: pequeño, para no bloquear el mapa debajo.
            var handle = document.createElement('div');
            handle.title = 'Arrastra para mover la capa';
            handle.style.cssText =
                'position:absolute;width:32px;height:32px;margin:-16px 0 0 -16px;' +
                'border-radius:50%;background:rgba(88,166,255,.92);border:2px solid #fff;' +
                'cursor:move;display:grid;place-items:center;color:#0d1117;font-size:14px;' +
                'box-shadow:0 2px 8px rgba(0,0,0,.5);z-index:2';
            handle.textContent = '\u2725';
            handle.addEventListener('mousedown', function (event) {
                self.startDrag(event);
            });
            self.handle = handle;
            this.getPanes().overlayMouseTarget.appendChild(handle);
        };

        this.overlay.prototype.draw = function () {
            self.projection = this.getProjection();
            self.draw();
        };

        this.overlay.prototype.onRemove = function () {
            if (self.container && self.container.parentNode) {
                self.container.parentNode.removeChild(self.container);
            }
            if (self.handle && self.handle.parentNode) {
                self.handle.parentNode.removeChild(self.handle);
            }
        };

        this.overlayInstance = new this.overlay();
        this.overlayInstance.setMap(this.map);
    };

    CapaRaster.prototype.baseMatrix = function () {
        var esquinas = this.datos.esquinas || {};
        var self = this;

        function punto(clave) {
            var par = esquinas[clave];
            return self.projection.fromLatLngToDivPixel(
                new google.maps.LatLng(par[1], par[0])
            );
        }

        var p0 = punto('tl');
        var p1 = punto('tr');
        var p2 = punto('bl');
        return {
            a: (p1.x - p0.x) / this.width,
            b: (p1.y - p0.y) / this.width,
            c: (p2.x - p0.x) / this.height,
            d: (p2.y - p0.y) / this.height,
            e: p0.x,
            f: p0.y
        };
    };

    CapaRaster.prototype.matrix = function () {
        var ajuste = this.ajuste;
        var rad = ajuste.rotacion * Math.PI / 180;
        var k = ajuste.escala * Math.cos(rad);
        var m = ajuste.escala * Math.sin(rad);
        var cx = this.width / 2;
        var cy = this.height / 2;
        var local = {
            a: k,
            b: m,
            c: -m,
            d: k,
            e: cx - (k * cx - m * cy) + ajuste.offset_x,
            f: cy - (m * cx + k * cy) + ajuste.offset_y
        };
        return mulMatrix(this.baseMatrix(), local);
    };

    CapaRaster.prototype.draw = function () {
        if (!this.image || !this.projection || !this.width || !this.height) return;
        var m = this.matrix();
        this.image.style.transform =
            'matrix(' + m.a + ',' + m.b + ',' + m.c + ',' + m.d + ',' + m.e + ',' + m.f + ')';
        this.image.style.opacity = String(this.ajuste.opacidad);
        this.container.style.display = (this.visible && this.datos.esquinas) ? 'block' : 'none';

        if (this.handle) {
            var centro = applyMatrix(m, this.width / 2, this.height / 2);
            this.handle.style.left = centro[0] + 'px';
            this.handle.style.top = centro[1] + 'px';
            this.handle.style.display =
                (this.visible && !this.bloqueado) ? 'grid' : 'none';
        }
        if (this === capas[activa]) this.refreshPanel();
    };

    /* ----------------------------- arrastre ------------------------------ */

    CapaRaster.prototype.startDrag = function (event) {
        if (this.bloqueado) return;
        var self = this;
        event.preventDefault();
        var inicio = {
            x: event.clientX,
            y: event.clientY,
            dx: this.ajuste.offset_x,
            dy: this.ajuste.offset_y
        };

        function mover(ev) {
            self.ajuste.offset_x = inicio.dx + (ev.clientX - inicio.x);
            self.ajuste.offset_y = inicio.dy + (ev.clientY - inicio.y);
            self.draw();
        }
        function soltar() {
            document.removeEventListener('mousemove', mover);
            document.removeEventListener('mouseup', soltar);
            document.body.style.cursor = '';
        }
        document.body.style.cursor = 'move';
        document.addEventListener('mousemove', mover);
        document.addEventListener('mouseup', soltar);
    };

    CapaRaster.prototype.moverMetros = function (este, norte) {
        if (this.bloqueado || !this.projection) return;
        var mpp = this.metrosPorPixel();
        if (!mpp) return;
        this.ajuste.offset_x += este / mpp;
        this.ajuste.offset_y -= norte / mpp;
        this.draw();
    };

    CapaRaster.prototype.metrosPorPixel = function () {
        if (!this.projection) return 0;
        var centro = this.map.getCenter();
        var p = this.projection.fromLatLngToDivPixel(centro);
        var q = this.projection.fromLatLngToDivPixel(
            new google.maps.LatLng(centro.lat(), centro.lng() + 0.005)
        );
        var pxPorGrado = Math.abs(q.x - p.x) / 0.005;
        if (!pxPorGrado) return 0;
        return 111320 * Math.cos(centro.lat() * Math.PI / 180) / pxPorGrado;
    };

    /* --------------------------- panel de control ------------------------ */

    CapaRaster.prototype.refreshPanel = function () {
        if (this !== capas[activa]) return;
        var ajuste = this.ajuste;
        var transparencia = Math.round((1 - ajuste.opacidad) * 100);
        var controles = [
            'capa-raster-transparencia', 'capa-raster-rotacion', 'capa-raster-escala'
        ];

        setValor('capa-raster-transparencia', transparencia);
        setTexto('capa-raster-transparencia-val', transparencia + '%');
        setValor('capa-raster-rotacion', ajuste.rotacion);
        setTexto('capa-raster-rotacion-val', ajuste.rotacion.toFixed(2));
        setValor('capa-raster-escala', ajuste.escala);
        setTexto('capa-raster-escala-val', ajuste.escala.toFixed(3));
        setChecked('capa-raster-visible', this.visible);
        setTexto('capa-raster-label-name', this.datos.nombre || 'Mostrar capa seleccionada');
        setChecked('capa-raster-bloqueo', this.bloqueado);

        controles.forEach(function (id) {
            if ($(id)) $(id).disabled = this.bloqueado;
        }, this);
        ['capa-raster-norte', 'capa-raster-sur', 'capa-raster-este',
         'capa-raster-oeste'].forEach(function (id) {
            if ($(id)) $(id).disabled = this.bloqueado;
        }, this);
        if ($('capa-raster-restablecer')) {
            $('capa-raster-restablecer').disabled = this.bloqueado;
        }

        var bloqueo = $('capa-raster-bloqueo-aviso');
        if (bloqueo) bloqueo.style.display = this.bloqueado ? 'block' : 'none';
    };

    /* ------------------------------ guardado ----------------------------- */

    CapaRaster.prototype.aPayload = function () {
        return {
            id: this.datos.id,
            opacidad: this.ajuste.opacidad,
            rotacion: this.ajuste.rotacion,
            escala: this.ajuste.escala,
            offset_x: this.ajuste.offset_x,
            offset_y: this.ajuste.offset_y,
            bloqueado: this.bloqueado,
            visible: this.visible
        };
    };

    function guardar(capa) {
        setStatus('Guardando…');
        return fetch(ENDPOINT, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken()
            },
            body: JSON.stringify(capa.aPayload())
        })
            .then(function (respuesta) {
                return respuesta.json().then(function (datos) {
                    if (!respuesta.ok) throw new Error(datos.error || 'No se pudo guardar');
                    return datos;
                });
            })
            .then(function (datos) {
                capa.datos = Object.assign({}, capa.datos, datos.capa || {});
                capa.guardado = Object.assign({}, capa.ajuste);
                setStatus('Ajuste guardado para todos los usuarios.');
            })
            .catch(function (error) {
                setStatus('Error al guardar: ' + error.message, true);
            });
    }

    /* ------------------------------ interfaz ----------------------------- */

    function capaActiva() { return capas[activa]; }

    function bindRango(id, alCambiar, formato) {
        var input = $(id);
        if (!input) return;
        bind(input, 'input', function () {
            var capa = capaActiva();
            if (!capa || capa.bloqueado) return;
            alCambiar(capa, parseFloat(input.value));
            $(id + '-val').textContent = formato(parseFloat(input.value));
            capa.draw();
        });
    }

    function initPanel() {
        var capa = capaActiva();
        if (!capa) return;

        bindRango('capa-raster-transparencia', function (c, valor) {
            c.ajuste.opacidad = clamp(1 - valor / 100, 0, 1);
            if (window.CapasMapa) window.CapasMapa.setOpacity(c.ajuste.opacidad);
        }, function (valor) { return Math.round(valor) + '%'; });

        bindRango('capa-raster-rotacion', function (c, valor) {
            c.ajuste.rotacion = valor;
        }, function (valor) { return valor.toFixed(2); });

        bindRango('capa-raster-escala', function (c, valor) {
            c.ajuste.escala = valor;
        }, function (valor) { return valor.toFixed(3); });

        alCambiar('capa-raster-visible', function (event) {
            capa = capaActiva();
            capa.visible = event.target.checked;
            capa.draw();
        });

        alCambiar('capa-raster-bloqueo', function (event) {
            capa = capaActiva();
            capa.bloqueado = event.target.checked;
            capa.draw();
        });

        alClic('capa-raster-norte', function () { capaActiva().moverMetros(0, 5); });
        alClic('capa-raster-sur', function () { capaActiva().moverMetros(0, -5); });
        alClic('capa-raster-este', function () { capaActiva().moverMetros(5, 0); });
        alClic('capa-raster-oeste', function () { capaActiva().moverMetros(-5, 0); });

        alClic('capa-raster-guardar', function () { guardar(capaActiva()); });

        alClic('capa-raster-restablecer', function () {
            capa = capaActiva();
            if (capa.bloqueado) return;
            capa.ajuste = Object.assign({}, capa.guardado);
            capa.draw();
            setStatus('Ajuste restablecido al último guardado.');
        });

        var selector = $('capa-raster-select');
        if (selector) {
            bind(selector, 'change', function (event) {
                activa = parseInt(event.target.value, 10) || 0;
                capaActiva().draw();
            });
        }
    }

    function initSelector() {
        var selector = $('capa-raster-select');
        if (!selector) return;
        if (capas.length < 2) {
            selector.parentNode.style.display = 'none';
            return;
        }
        selector.parentNode.style.display = '';
        capas.forEach(function (capa, indice) {
            var opcion = document.createElement('option');
            opcion.value = String(indice);
            opcion.textContent = capa.datos.nombre;
            selector.appendChild(opcion);
        });
    }

    /* ------------------------------- arranque ---------------------------- */

    function init(googleMap) {
        clear();
        activa = 0;
        map = googleMap;
        var nodo = $(DATA_ID);
        var datos = [];
        if (nodo) {
            try { datos = JSON.parse(nodo.textContent) || []; } catch (error) { datos = []; }
        }
        datos = datos.filter(function (capa) {
            return capa && capa.imagen_url && capa.esquinas &&
                capa.esquinas.tl && capa.esquinas.tr && capa.esquinas.br && capa.esquinas.bl;
        });

        var panel = $('panel-capa-raster');
        if (!datos.length) {
            if (panel) panel.style.display = 'none';
            return;
        }
        if (panel) panel.style.display = '';

        capas = datos.map(function (item) { return new CapaRaster(item, googleMap); });
        initSelector();
        initPanel();
        idleListener = google.maps.event.addListener(googleMap, 'idle', function () {
            capas.forEach(function (capa) { capa.draw(); });
        });
        capas.forEach(function (capa) { capa.draw(); });
    }

    function setOpacity(opacidad) {
        capas.forEach(function (capa) { capa.ajuste.opacidad = opacidad; capa.draw(); });
        if (capaActiva()) capaActiva().refreshPanel();
    }
    window.CapaRasterOverlay = { init: init, clear: clear, setOpacity: setOpacity };
})();
