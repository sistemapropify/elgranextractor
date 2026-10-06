/* ============================================================================
 * Zonificación por marcador (cuadrantización)
 *
 * Resuelve, para cada propiedad del mapa, la zona de uso del plano del PDM
 * (RDM-2, CE, ZRE-CH, ...) leyendo el color del plano en la posición del
 * marcador desde el backend, y la muestra en la tarjeta de la propiedad.
 * ==========================================================================*/
(function () {
    'use strict';

    var ENDPOINT = '/cuadrantizacion/zonificacion/clasificar/';
    var ENDPOINT_VERIFICAR = '/cuadrantizacion/zonificacion/verificar/';
    var MAX_POR_LOTE = 400;
    var TAMANO_LOTE = 250;

    var cache = {};        // clave -> resultado de clasificación
    var enCurso = {};      // clave -> true mientras se consulta

    function fuenteDe(propiedad) {
        return (propiedad && (propiedad.source_key || propiedad.source)) || '';
    }

    function propiedadIdDe(propiedad) {
        if (!propiedad) return '';
        if (propiedad.record_id !== undefined && propiedad.record_id !== null) {
            return String(propiedad.record_id);
        }
        if (propiedad.id !== undefined && propiedad.id !== null) {
            return String(propiedad.id);
        }
        return '';
    }

    function claveDe(propiedad) {
        var fuente = fuenteDe(propiedad);
        var identificador = propiedadIdDe(propiedad);
        if (fuente && identificador) return fuente + ':' + identificador;
        if (propiedad && propiedad.code) return 'c' + propiedad.code;
        return 'x' + (propiedad ? propiedad.lat + ',' + propiedad.lng : '');
    }

    function tokenCsrf() {
        var input = document.querySelector('[name=csrfmiddlewaretoken]');
        return input ? input.value : '';
    }

    function puedeVerificar(propiedad) {
        return Boolean(fuenteDe(propiedad) && propiedadIdDe(propiedad));
    }

    function escapar(texto) {
        if (window.escapeMapHtml) return window.escapeMapHtml(texto);
        return String(texto == null ? '' : texto)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    function bloqueHtml(zona, consultando, conBoton) {
        var verificada = zona && zona.verificada;
        if (zona && zona.codigo) {
            var color = zona.color || '#8b949e';
            var titulo = zona.uso ? ' title="' + escapar(zona.uso) + '"' : '';
            var media = zona.confianza === 'media'
                ? '<span class="propify-card-zona-aviso" title="La muestra cae en un borde o zona mixta">≈</span>'
                : '';
            var sello = verificada
                ? '<span class="propify-card-zona-sello" title="Zona verificada por una persona">✓ verificada</span>'
                : '';
            var boton = conBoton
                ? '<button type="button" class="propify-card-zona-boton" data-accion="verificar">' +
                    (verificada ? 'Quitar verificación' : 'Marcar verificada') + '</button>'
                : '';
            return '<span class="propify-card-zona-swatch" style="background:' +
                escapar(color) + '"></span>' +
                '<span class="propify-card-zona-codigo">' + escapar(zona.codigo) + '</span>' +
                '<span class="propify-card-zona-uso"' + titulo + '>' +
                escapar(zona.uso || '') + '</span>' + media + sello + boton;
        }
        if (consultando) {
            return '<span class="propify-card-zona-vacia">Consultando zonificación…</span>';
        }
        return '<span class="propify-card-zona-vacia">Sin zona asignada en el plano</span>';
    }

    function pintar(propiedad, zona) {
        var contenedor = document.getElementById('propify-card-zona');
        if (!contenedor) return;
        if (contenedor.dataset.clave !== claveDe(propiedad)) return;
        contenedor.innerHTML = bloqueHtml(zona, false, puedeVerificar(propiedad));
        var boton = contenedor.querySelector('.propify-card-zona-boton');
        if (boton) {
            boton.addEventListener('click', function () {
                verificar(propiedad, !(zona && zona.verificada));
            });
        }
    }

    function verificar(propiedad, valor) {
        if (!puedeVerificar(propiedad)) return;
        var contenedor = document.getElementById('propify-card-zona');
        if (contenedor) {
            contenedor.innerHTML =
                '<span class="propify-card-zona-vacia">Guardando verificación…</span>';
        }
        fetch(ENDPOINT_VERIFICAR, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': tokenCsrf()
            },
            body: JSON.stringify({
                fuente: fuenteDe(propiedad),
                propiedad_id: propiedadIdDe(propiedad),
                verificada: !!valor,
                lat: propiedad.lat,
                lng: propiedad.lng,
                propiedad_ref: propiedad.code || propiedad.title || ''
            })
        })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (datos) {
                var fila = datos && datos.zonificacion;
                cache[claveDe(propiedad)] = fila && fila.codigo ? fila : null;
                pintar(propiedad, cache[claveDe(propiedad)]);
            })
            .catch(function () {
                pintar(propiedad, cache[claveDe(propiedad)]);
            });
    }

    function guardar(propiedad, zona) {
        cache[claveDe(propiedad)] = zona;
    }

    function resolver(propiedad) {
        var clave = claveDe(propiedad);
        if (Object.prototype.hasOwnProperty.call(cache, clave)) {
            pintar(propiedad, cache[clave]);
            return;
        }
        if (enCurso[clave]) return;
        enCurso[clave] = true;
        fetch(ENDPOINT, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                puntos: [{
                    id: clave,
                    fuente: fuenteDe(propiedad),
                    propiedad_id: propiedadIdDe(propiedad),
                    lat: propiedad.lat,
                    lng: propiedad.lng
                }]
            })
        })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (datos) {
                var fila = datos && datos.resultados && datos.resultados[0];
                guardar(propiedad, fila && fila.codigo ? fila : null);
                pintar(propiedad, cache[clave]);
            })
            .catch(function () { /* la tarjeta se queda con el texto base */ })
            .then(function () { delete enCurso[clave]; });
    }

    function precargar(propiedades) {
        var pendientes = (propiedades || []).filter(function (p) {
            if (!p || p.lat == null || p.lng == null) return false;
            return !Object.prototype.hasOwnProperty.call(cache, claveDe(p));
        });
        if (!pendientes.length) return Promise.resolve(0);

        var lotes = [];
        for (var i = 0; i < pendientes.length; i += TAMANO_LOTE) {
            lotes.push(pendientes.slice(i, i + TAMANO_LOTE));
        }
        return Promise.all(lotes.slice(0, Math.ceil(MAX_POR_LOTE / TAMANO_LOTE)).map(function (lote) {
            return fetch(ENDPOINT, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    puntos: lote.map(function (p) {
                        return {
                            id: claveDe(p),
                            fuente: fuenteDe(p),
                            propiedad_id: propiedadIdDe(p),
                            lat: p.lat,
                            lng: p.lng
                        };
                    })
                })
            })
                .then(function (r) { return r.ok ? r.json() : null; })
                .then(function (datos) {
                    var filas = (datos && datos.resultados) || [];
                    filas.forEach(function (fila) {
                        cache[fila.id] = fila && fila.codigo ? fila : null;
                    });
                    return filas.length;
                })
                .catch(function () { return 0; });
        })).then(function (resultados) {
            return resultados.reduce(function (a, b) { return a + b; }, 0);
        });
    }

    function zonaDe(propiedad) {
        return cache[claveDe(propiedad)] || null;
    }

    window.ZonificacionMapa = {
        bloqueHtml: bloqueHtml,
        resolver: resolver,
        precargar: precargar,
        zonaDe: zonaDe,
        claveDe: claveDe,
        fuenteDe: fuenteDe,
        propiedadIdDe: propiedadIdDe,
        verificar: verificar,
        cache: cache
    };
})();
