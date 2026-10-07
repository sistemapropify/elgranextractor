/* ============================================================================
 * Pre-evaluación de zona para el ACM
 *
 * Cuando se ubica el marcador (clic, arrastre del pin o dirección), consulta al
 * clasificador de zonificación del PDM qué zona de uso corresponde a ese punto
 * y la muestra en el panel de evaluación por componentes, antes de ejecutar la
 * búsqueda de comparables.
 * ==========================================================================*/
(function () {
    'use strict';

    var ENDPOINT = '/cuadrantizacion/zonificacion/clasificar/';
    var panel = null;
    var contador = 0;
    var ultimo = null;

    function $(id) { return document.getElementById(id); }

    function escapar(texto) {
        if (window.escapeMapHtml) return window.escapeMapHtml(texto);
        return String(texto == null ? '' : texto)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    function pintar(html) {
        if (!panel) panel = $('cmp-zona');
        if (!panel) return;
        panel.innerHTML = html;
        panel.hidden = false;
    }

    function pintarVacio(mensaje) {
        pintar('<h2>Zona de uso (PDM)</h2><p class="cmp-muted">' + escapar(mensaje) + '</p>');
    }

    function pintarZona(zona) {
        var color = zona.color || '#8b949e';
        var etiquetas = {
            alta: '<span class="cmp-zona-ok">alta</span>',
            media: '<span class="cmp-zona-aviso" title="El punto cae en un borde o zona mixta">' +
                   'aproximada</span>',
            baja: '<span class="cmp-zona-aviso" title="Polígono pequeño o muy texturado; ' +
                  'conviene confirmar en campo">a confirmar</span>'
        };
        var confianza = etiquetas[zona.confianza] || etiquetas.media;
        pintar(
            '<h2>Zona de uso (PDM)</h2>' +
            '<div class="cmp-zona-linea">' +
                '<span class="cmp-zona-swatch" style="background:' + escapar(color) + '"></span>' +
                '<strong class="cmp-zona-codigo">' + escapar(zona.codigo) + '</strong>' +
                (zona.categoria
                    ? '<span class="cmp-zona-categoria">' + escapar(zona.categoria) + '</span>'
                    : '') +
                confianza +
            '</div>' +
            '<p class="cmp-zona-nombre">' + escapar(zona.uso || zona.nombre || '') + '</p>' +
            '<p class="cmp-muted cmp-zona-nota">Pre-evaluación según el plano de zonificación. ' +
            'Sirve de contexto antes de calcular; no reemplaza la verificación en campo.</p>'
        );
    }

    function mensajeSinZona(datos, lat, lng) {
        var fila = datos && datos.resultados && datos.resultados[0];
        var coordenada = ' (' + Number(lat).toFixed(5) + ', ' + Number(lng).toFixed(5) + ')';
        if (fila && fila.motivo === 'fuera_del_plano') {
            return 'El punto está fuera del área cubierta por el plano de zonificación' +
                coordenada + '. El plano abarca la ciudad de Arequipa y su entorno inmediato.';
        }
        return 'El punto cae dentro del plano pero no tiene uso asignado en la leyenda' +
            coordenada + ': es terreno, manzana suelta o área no normada. Prueba con un ' +
            'punto sobre una zona coloreada.';
    }

    function actualizar(lat, lng) {
        if (lat == null || lng == null || !isFinite(lat) || !isFinite(lng)) return;
        ultimo = { lat: lat, lng: lng };
        contador += 1;
        var marca = contador;
        pintarVacio('Consultando la zona del plano…');
        fetch(ENDPOINT + '?lat=' + encodeURIComponent(lat) + '&lng=' + encodeURIComponent(lng), {
            credentials: 'same-origin',
            cache: 'no-store',
            headers: { 'Accept': 'application/json' }
        })
            .then(function (r) {
                // Si la sesión venció, Django redirige al login y devuelve HTML:
                // hay que avisarlo, no confundirlo con "sin zona".
                if (r.redirected && /\/login\//.test(r.url)) return null;
                if (!r.ok) return null;
                if ((r.headers.get('content-type') || '').indexOf('application/json') === -1) {
                    return null;
                }
                return r.json();
            })
            .then(function (datos) {
                if (marca !== contador) return;   // llegó tarde: hay un punto más nuevo
                var fila = datos && datos.resultados && datos.resultados[0];
                if (fila && fila.codigo) {
                    pintarZona(fila);
                } else if (datos && datos.sin_plano) {
                    pintarVacio('La capa de zonificación no está disponible.');
                } else if (datos && Array.isArray(datos.resultados)) {
                    pintarVacio(mensajeSinZona(datos, lat, lng));
                } else {
                    pintarVacio('No se pudo consultar la zonificación. Si la sesión ' +
                                'expiró, vuelve a iniciar sesión.');
                }
            })
            .catch(function () {
                if (marca !== contador) return;
                pintarVacio('No se pudo consultar la zonificación.');
            });
    }

    function limpiar() {
        if (!panel) panel = $('cmp-zona');
        if (panel) panel.hidden = true;
    }

    window.ACMZona = {
        actualizar: actualizar,
        limpiar: limpiar,
        ultimo: function () { return ultimo; }
    };

    function desdeFormulario() {
        var lat = document.querySelector('input[name="lat"]');
        var lng = document.querySelector('input[name="lng"]');
        if (!lat || !lng) return;
        actualizar(parseFloat(lat.value), parseFloat(lng.value));
    }

    function inicial() {
        desdeFormulario();
        ['lat', 'lng'].forEach(function (nombre) {
            var campo = document.querySelector('input[name="' + nombre + '"]');
            if (campo) campo.addEventListener('change', desdeFormulario);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', inicial);
    } else {
        inicial();
    }
})();
