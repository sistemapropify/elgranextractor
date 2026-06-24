// Módulo ACM - JavaScript principal

// Variables globales del módulo
let acmMap;
let marcadorPrincipal = null;
let circuloRadio = null;
let marcadoresComparables = new Map(); // id -> {marker, data, seleccionado}
let propiedadesSeleccionadas = new Map(); // id -> data
let propiedadesEncontradas = []; // Todas las propiedades encontradas en la búsqueda

// URLs de iconos PNG personalizados por fuente
const ICONO_PRINCIPAL = 'https://maps.google.com/mapfiles/ms/icons/yellow-dot.png';
const ICONO_PROPIFFY = '/static/requerimientos/data/Pin-propify.png';
const ICONO_REMAX = '/static/requerimientos/data/pin-remax.png';
const ICONO_ADONDEVIVIR = '/static/requerimientos/data/adondevivir-pin.png';
const ICONO_COMPARABLE = 'https://maps.google.com/mapfiles/ms/icons/blue-dot.png';
// Icono seleccionado: rojo con número
const ICONO_SELECCIONADO = 'https://maps.google.com/mapfiles/ms/icons/red-dot.png';

// Inicializar eventos del formulario y controles (independiente de Google Maps)
function inicializarEventos() {
    console.log('ACM: inicializarEventos()');
    
    // Slider de radio
    const radioSlider = document.getElementById('radioBusqueda');
    const radioValue = document.getElementById('radioValue');
    
    if (radioSlider && radioValue) {
        radioSlider.addEventListener('input', () => {
            radioValue.textContent = radioSlider.value;
        });
    } else {
        console.warn('ACM: No se encontraron elementos del slider de radio');
    }

    // Botón de búsqueda (único, debajo del mapa)
    const btnBuscarMap = document.getElementById('btnBuscarMap');
    if (btnBuscarMap) {
        console.log('ACM: Asignando evento click a btnBuscarMap');
        btnBuscarMap.addEventListener('click', buscarComparables);
    } else {
        console.error('ACM: NO se encontró el botón btnBuscarMap');
    }

    // Botón para eliminar todos los comparables seleccionados
    const btnEliminarTodos = document.getElementById('btnEliminarTodos');
    if (btnEliminarTodos) {
        btnEliminarTodos.addEventListener('click', limpiarPropiedadesSeleccionadas);
    }

    // Función para abrir el modal de Resumen ACM
    function abrirModalResumenACM() {
        actualizarResumenACM();
        const modal = new bootstrap.Modal(document.getElementById('modalResumenACM'));
        modal.show();
    }

    // Botón "Resumen ACM" móvil - abre el modal con el resumen
    const btnResumenACM = document.getElementById('btnResumenACM');
    if (btnResumenACM) {
        btnResumenACM.addEventListener('click', abrirModalResumenACM);
    }

    // Botón "Resumen ACM" desktop - abre el modal con el resumen
    const btnResumenACMDesktop = document.getElementById('btnResumenACMDesktop');
    if (btnResumenACMDesktop) {
        btnResumenACMDesktop.addEventListener('click', abrirModalResumenACM);
    }

    // Cambio en tipo de propiedad para mostrar/ocultar campos
    const tipoPropiedad = document.getElementById('tipoPropiedad');
    if (tipoPropiedad) {
        function actualizarCamposPorTipo() {
            const tipo = tipoPropiedad.value.toLowerCase();
            const esTerreno = tipo === 'terreno';
            
            // Campos que deben ocultarse cuando es Terreno:
            // m² const., Piso, Hab., Baños — los terrenos no tienen estas características
            var camposAOcultar = [
                'acm-field-construccion',
                'acm-field-piso',
                'acm-field-habitaciones',
                'acm-field-banos'
            ];
            
            camposAOcultar.forEach(function(className) {
                var elementos = document.getElementsByClassName(className);
                Array.from(elementos).forEach(function(el) {
                    el.style.display = esTerreno ? 'none' : '';
                });
            });
            
            // El campo m² terr. siempre debe estar visible
            // (los terrenos usan área de terreno, no construcción)
        }
        
        tipoPropiedad.addEventListener('change', actualizarCamposPorTipo);
        // Ejecutar también al cargar la página para estado inicial
        actualizarCamposPorTipo();
    }

    // Event listeners para actualizar resumen cuando cambien los parámetros
    const metrosConstruccionInput = document.getElementById('metrosConstruccion');
    const metrosTerrenoInput = document.getElementById('metrosTerreno');
    const pisoInput = document.getElementById('piso');

    function actualizarResumenSiHaySeleccionados() {
        if (propiedadesSeleccionadas.size > 0) {
            actualizarResumenACM();
        }
    }

    if (metrosConstruccionInput) {
        metrosConstruccionInput.addEventListener('input', actualizarResumenSiHaySeleccionados);
        metrosConstruccionInput.addEventListener('change', actualizarResumenSiHaySeleccionados);
    }

    if (metrosTerrenoInput) {
        metrosTerrenoInput.addEventListener('input', actualizarResumenSiHaySeleccionados);
        metrosTerrenoInput.addEventListener('change', actualizarResumenSiHaySeleccionados);
    }

    if (pisoInput) {
        pisoInput.addEventListener('input', actualizarResumenSiHaySeleccionados);
        pisoInput.addEventListener('change', actualizarResumenSiHaySeleccionados);
    }
}

// Inicializar mapa ACM
function initACMMap() {
    console.log('initACMMap called');
    const defaultCenter = { lat: -16.4090, lng: -71.5375 }; // Arequipa, Perú
    acmMap = new google.maps.Map(document.getElementById('acmMap'), {
        center: defaultCenter,
        zoom: 13,
        scrollwheel: true,
        gestureHandling: 'greedy', // Permite scroll y gestos incluso con marcadores/interacciones
        styles: [
            {
                featureType: "poi",
                elementType: "labels",
                stylers: [{ visibility: "off" }]
            }
        ]
    });

    // Listener para clic en el mapa (colocar marcador principal)
    acmMap.addListener('click', (event) => {
        colocarMarcadorPrincipal(event.latLng);
    });

    // Inicializar buscador de direcciones con Google Places Autocomplete + Geocoding
    inicializarBuscadorDirecciones();
}

// Colocar marcador principal en el mapa
function colocarMarcadorPrincipal(latLng) {
    // Eliminar marcador anterior si existe
    if (marcadorPrincipal) {
        marcadorPrincipal.setMap(null);
    }

    // Crear nuevo marcador
    marcadorPrincipal = new google.maps.Marker({
        position: latLng,
        map: acmMap,
        title: '',
        clickable: false,
        icon: {
            url: ICONO_PRINCIPAL,
            scaledSize: new google.maps.Size(40, 40)
        },
        draggable: true,
        zIndex: 1000
    });

    // Actualizar inputs hidden
    document.getElementById('latitud').value = latLng.lat();
    document.getElementById('longitud').value = latLng.lng();

    // Listener para arrastrar marcador
    marcadorPrincipal.addListener('dragend', (event) => {
        console.log('Marcador movido - dragend event fired');
        const newLatLng = event.latLng;
        document.getElementById('latitud').value = newLatLng.lat();
        document.getElementById('longitud').value = newLatLng.lng();
        
        console.log(`Propiedades seleccionadas: ${propiedadesSeleccionadas.size}`);
        
        // Recalcular distancias para propiedades seleccionadas
        if (propiedadesSeleccionadas.size > 0) {
            propiedadesSeleccionadas.forEach((propiedad, id) => {
                // Calcular nueva distancia usando la fórmula de Haversine
                const nuevaDistancia = calcularDistancia(
                    newLatLng.lat(),
                    newLatLng.lng(),
                    propiedad.lat,
                    propiedad.lng
                );
                propiedad.distancia_metros = nuevaDistancia;
                console.log(`Propiedad ${id}: distancia actualizada a ${nuevaDistancia.toFixed(0)} metros`);
            });
        }
        
        // Actualizar resumen ACM siempre (para mostrar estado vacío si no hay seleccionadas)
        console.log('Actualizando resumen ACM...');
        actualizarResumenACM();
    });

    // Centrar mapa en el marcador
    acmMap.panTo(latLng);
    
    // Recalcular distancias para propiedades seleccionadas (si las hay)
    if (propiedadesSeleccionadas.size > 0) {
        propiedadesSeleccionadas.forEach((propiedad, id) => {
            // Calcular nueva distancia usando la fórmula de Haversine
            const nuevaDistancia = calcularDistancia(
                latLng.lat(),
                latLng.lng(),
                propiedad.lat,
                propiedad.lng
            );
            propiedad.distancia_metros = nuevaDistancia;
            console.log(`Propiedad ${id}: distancia actualizada a ${nuevaDistancia.toFixed(0)} metros`);
        });
    }
    
    // Actualizar resumen ACM siempre (para mostrar estado vacío si no hay seleccionadas)
    console.log('Marcador colocado inicialmente, actualizando resumen ACM...');
    actualizarResumenACM();
}


// Buscar propiedades comparables
async function buscarComparables() {
    // Validar que haya marcador principal
    if (!marcadorPrincipal) {
        alert('Por favor, selecciona un punto en el mapa haciendo clic en él.');
        return;
    }

    // Obtener datos del formulario
    const lat = document.getElementById('latitud').value;
    const lng = document.getElementById('longitud').value;
    const radio = document.getElementById('radioBusqueda').value;
    const tipoPropiedad = document.getElementById('tipoPropiedad').value;

    // Validar coordenadas
    if (!lat || !lng) {
        alert('Coordenadas no válidas. Selecciona un punto en el mapa.');
        return;
    }

    // Mostrar indicador de carga en el botón de búsqueda
    const btnsBuscar = [
        document.getElementById('btnBuscarMap')
    ].filter(Boolean);
    const estadosOriginales = btnsBuscar.map(btn => ({
        html: btn.innerHTML,
        disabled: btn.disabled
    }));
    btnsBuscar.forEach(btn => {
        btn.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Buscando...';
        btn.disabled = true;
    });

    try {
        // Enviar solicitud AJAX
        const response = await fetch('/acm/buscar-comparables/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken(),
            },
            body: JSON.stringify({
                lat: parseFloat(lat),
                lng: parseFloat(lng),
                radio: parseFloat(radio),
                tipo_propiedad: tipoPropiedad,
            }),
        });

        const data = await response.json();

        if (data.status === 'ok') {
            console.log('ACM: Respuesta OK, propiedades:', data.propiedades.length);
            // Limpiar marcadores, círculo y propiedades seleccionadas anteriores
            limpiarMarcadoresComparables();
            limpiarPropiedadesSeleccionadas();
            if (circuloRadio) {
                circuloRadio.setMap(null);
            }

            // Dibujar círculo de radio
            circuloRadio = new google.maps.Circle({
                strokeColor: '#228B22',
                strokeOpacity: 0.8,
                strokeWeight: 2,
                fillColor: '#90EE90',
                fillOpacity: 0.25,
                map: acmMap,
                center: { lat: parseFloat(lat), lng: parseFloat(lng) },
                radius: parseFloat(radio),
            });
            console.log('ACM: Círculo dibujado');

            // Guardar propiedades encontradas
            propiedadesEncontradas = data.propiedades;

            // Crear marcadores para cada propiedad
            data.propiedades.forEach(prop => {
                console.log('ACM: Creando marcador para propiedad', prop.id);
                crearMarcadorComparable(prop);
            });

            // Actualizar contador
            document.getElementById('contadorPropiedades').textContent = data.total;

            // Ajustar vista del mapa para mostrar todos los marcadores + círculo
            ajustarVistaMapa();

            // Mostrar mensaje de éxito
            mostrarToast('success', `${data.total} propiedades encontradas en el radio de ${radio} metros.`);
            
            // Mostrar botón "Análisis Avanzado"
            const btnAvanzado = document.getElementById('btnAnalisisAvanzado');
            if (btnAvanzado) {
                btnAvanzado.style.display = 'inline-flex';
            }
        } else {
            throw new Error(data.message || 'Error en la búsqueda');
        }
    } catch (error) {
        console.error('Error buscando comparables:', error);
        mostrarToast('danger', `Error: ${error.message}`);
    } finally {
        // Restaurar ambos botones
        btnsBuscar.forEach((btn, i) => {
            btn.innerHTML = estadosOriginales[i].html;
            btn.disabled = estadosOriginales[i].disabled;
        });
    }
}

// ─────────────────────────────────────────────────────────────
// ANÁLISIS AVANZADO — toggle mapa / gráfico espacial
// ─────────────────────────────────────────────────────────────

// Alterna entre Google Maps y el gráfico de análisis espacial
function toggleAnalisisView() {
    const mapContainer = document.getElementById('acmMap');
    const chartContainer = document.getElementById('acmChartContainer');
    const btnAvanzado = document.getElementById('btnAnalisisAvanzado');
    const btnBuscarContainer = document.getElementById('btnBuscarMapContainer');
    
    if (!mapContainer || !chartContainer) return;
    
    const showingMap = mapContainer.style.display !== 'none';
    
    if (showingMap) {
        // Cambiar a vista de gráfico
        mapContainer.style.display = 'none';
        chartContainer.style.display = 'block';
        if (btnAvanzado) btnAvanzado.textContent = '📊 Análisis Activo';
        if (btnBuscarContainer) btnBuscarContainer.style.display = 'none';
        
        // Si no hay imagen cargada, solicitarla
        const chartImg = document.getElementById('acmChartImg');
        if (chartImg && !chartImg.src) {
            solicitarAnalisisAvanzado();
        }
    } else {
        // Volver al mapa
        mapContainer.style.display = 'block';
        chartContainer.style.display = 'none';
        if (btnAvanzado) btnAvanzado.innerHTML = '<i class="bi bi-graph-up me-1"></i>Análisis Avanzado';
        if (btnBuscarContainer) btnBuscarContainer.style.display = 'block';
        
        // Forzar resize de Google Maps
        if (acmMap) {
            setTimeout(() => {
                google.maps.event.trigger(acmMap, 'resize');
            }, 100);
        }
    }
}

// Solicitar el PNG de análisis espacial al servidor
async function solicitarAnalisisAvanzado() {
    if (propiedadesSeleccionadas.size < 3) {
        alert('Selecciona al menos 3 propiedades como comparables para generar el análisis.');
        toggleAnalisisView(); // Volver al mapa
        return;
    }
    
    const chartImg = document.getElementById('acmChartImg');
    const chartContainer = document.getElementById('acmChartContainer');
    if (!chartImg || !chartContainer) return;
    
    // Mostrar loader
    chartContainer.innerHTML = `
        <div style="display:flex;align-items:center;justify-content:center;height:100%;min-height:300px;background:#0d1117;color:#8b949e;flex-direction:column;gap:12px;">
            <div class="spinner-border text-light" role="status"></div>
            <span style="font-size:14px;">Generando análisis espacial...</span>
        </div>
    `;
    
    try {
        // Preparar datos de propiedades seleccionadas
        const propiedadesData = [];
        propiedadesSeleccionadas.forEach((prop, id) => {
            propiedadesData.push({
                id: prop.id,
                precio: prop.precio || prop.precio_final || 0,
                area_terreno: prop.metros_terreno || 0,
                area_construida: prop.metros_construccion || 0,
                antiguedad: prop.antiguedad || 0,
                cocheras: prop.cocheras || 0,
                lat: prop.lat,
                lon: prop.lng,
                precio_m2_terreno: prop.precio_m2 || prop.precio_m2_final || 0,
                etiqueta: prop.titulo || prop.id,
            });
        });
        
        const response = await fetch('/acm/analisis-espacial/png/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken(),
            },
            body: JSON.stringify({ propiedades: propiedadesData }),
        });
        
        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.error || 'Error del servidor');
        }
        
        // Obtener blob de la imagen
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        
        // Reconstruir contenedor con la imagen
        chartContainer.innerHTML = `
            <img id="acmChartImg" src="${url}" alt="Análisis Espacial"
                 style="width:100%;height:100%;object-fit:contain;">
            <div style="position:absolute;top:8px;right:8px;z-index:10;">
                <button type="button" class="btn btn-sm"
                        onclick="toggleAnalisisView()"
                        style="background:rgba(0,0,0,0.7);color:#fff;border:1px solid #555;border-radius:6px;padding:4px 10px;font-size:11px;">
                    <i class="bi bi-map me-1"></i>Volver al Mapa
                </button>
            </div>
        `;
        
    } catch (err) {
        console.error('Error en análisis espacial:', err);
        chartContainer.innerHTML = `
            <div style="display:flex;align-items:center;justify-content:center;height:100%;min-height:200px;background:#0d1117;color:#f85149;flex-direction:column;gap:8px;">
                <span style="font-size:24px;">⚠️</span>
                <span style="font-size:13px;">Error: ${err.message}</span>
                <button class="btn btn-sm btn-outline-secondary mt-2" onclick="toggleAnalisisView()">
                    Volver al mapa
                </button>
            </div>
        `;
    }
}

// ─────────────────────────────────────────────────────────────

// Crear marcador para propiedad comparable
function crearMarcadorComparable(propiedad) {
    // Determinar icono según la fuente/portal
    let iconoUrl = ICONO_COMPARABLE;
    let esPropifai = propiedad.es_propify || propiedad.fuente === 'propifai';
    const portal = (propiedad.portal || '').toLowerCase();
    
    if (esPropifai) {
        iconoUrl = ICONO_PROPIFFY;
    } else if (portal === 'propifai' || portal === 'propify') {
        iconoUrl = ICONO_PROPIFFY;
    } else if (portal === 'remax') {
        iconoUrl = ICONO_REMAX;
    } else if (portal === 'adondevivir') {
        iconoUrl = ICONO_ADONDEVIVIR;
    }
    // Si no coincide con ningún portal conocido, usa ICONO_COMPARABLE (blue-dot)
    
    // Tamaño del icono
    const tamanoIcono = 32;
    
    // Calcular precio por m² para mostrar en la etiqueta del marcador
    const precioM2 = propiedad.precio_m2_final || propiedad.precio_m2;
    let labelText = '';
    if (precioM2 && precioM2 > 0) {
        labelText = '$' + Math.round(precioM2).toString() + '/m²';
    } else {
        labelText = esPropifai ? 'P' : '?';
    }
    
    // Crear elemento personalizado para el marcador con precio/m² visible
    const markerIcon = {
        url: iconoUrl,
        scaledSize: new google.maps.Size(tamanoIcono, tamanoIcono),
        labelOrigin: new google.maps.Point(tamanoIcono / 2, tamanoIcono + 14)
    };
    
    const marker = new google.maps.Marker({
        position: { lat: propiedad.lat, lng: propiedad.lng },
        map: acmMap,
        title: '',
        icon: markerIcon,
        label: {
            text: labelText,
            color: "#dc3545",
            fontSize: "12px",
            fontWeight: "bold"
        }
    });

    // Click en marcador: seleccionar/deseleccionar directamente (sin InfoWindow)
    marker.addListener('click', () => {
        toggleSeleccionarPropiedad(propiedad.id);
    });

    // Almacenar referencia
    marcadoresComparables.set(propiedad.id, {
        marker,
        data: propiedad,
        seleccionado: false,
        iconoUrl,
        iconoSeleccionadoUrl: ICONO_SELECCIONADO,
        esPropifai,
        tamanoIcono,
        labelText: labelText,
    });
}

// Toggle selección de propiedad
function toggleSeleccionarPropiedad(id) {
    const marcadorInfo = marcadoresComparables.get(id);
    if (!marcadorInfo) {
        console.warn(`⚠️ DEBUG ACM: toggleSeleccionarPropiedad(${id}) — NO ENCONTRADO en marcadoresComparables`);
        console.warn(`   Claves en marcadoresComparables:`, Array.from(marcadoresComparables.keys()));
        return;
    }
    console.log(`🔍 DEBUG ACM: toggleSeleccionarPropiedad(id=${id}, fuente=${marcadorInfo.data.fuente}, seleccionado_actual=${marcadorInfo.seleccionado})`);
    console.log(`   propiedadesSeleccionadas tiene ${propiedadesSeleccionadas.size} elementos:`, Array.from(propiedadesSeleccionadas.keys()));

    // Determinar tamaño del icono según si es Propifai
    const tamanoIcono = marcadorInfo.tamanoIcono || 32;
    const tamanoIconoSeleccionado = marcadorInfo.esPropifai ? 40 : 36; // Más grande cuando está seleccionado

    if (marcadorInfo.seleccionado) {
        // Deseleccionar - usar icono normal según la fuente
        marcadorInfo.marker.setIcon({
            url: marcadorInfo.iconoUrl || ICONO_COMPARABLE,
            scaledSize: new google.maps.Size(tamanoIcono, tamanoIcono)
        });
        // Restaurar etiqueta con precio/m² (guardado en labelText)
        const labelText = marcadorInfo.labelText || (marcadorInfo.esPropifai ? 'P' : '?');
        marcadorInfo.marker.setLabel({
            text: labelText,
            color: "#dc3545",
            fontSize: "12px",
            fontWeight: "bold"
        });
        marcadorInfo.seleccionado = false;
        propiedadesSeleccionadas.delete(id);
        
        // Eliminar tarjeta
        eliminarTarjetaPropiedad(id);
    } else {
        // Seleccionar - usar icono de seleccionado según la fuente
        marcadorInfo.marker.setIcon({
            url: marcadorInfo.iconoSeleccionadoUrl || ICONO_SELECCIONADO,
            scaledSize: new google.maps.Size(tamanoIconoSeleccionado, tamanoIconoSeleccionado)
        });
        // Mantener etiqueta (será actualizada con número por actualizarNumerosSeleccionados)
        marcadorInfo.seleccionado = true;
        propiedadesSeleccionadas.set(id, marcadorInfo.data);
        
        // Crear tarjeta en panel lateral
        crearTarjetaPropiedad(marcadorInfo.data);
    }

    // Actualizar contadores, números y resumen
    actualizarContadores();
    actualizarNumerosSeleccionados();
    actualizarResumenACM();
}

// Crear tarjeta de propiedad en panel lateral (mobile offcanvas)
function crearTarjetaPropiedad(propiedad) {
    const template = document.getElementById('templatePropiedad');
    const clone = template.content.cloneNode(true);
    
    // Rellenar datos
    const card = clone.querySelector('.propiedad-card');
    card.id = `propiedad-${propiedad.id}`;
    
    // Imagen
    const img = clone.querySelector('.propiedad-imagen');
    img.src = propiedad.imagen_url || '/static/acm/img/no-image.svg';
    
    // Tipo y estado
    clone.querySelector('.propiedad-tipo').textContent = propiedad.tipo;
    clone.querySelector('.propiedad-estado').textContent = propiedad.estado;
    
    // Ubicación
    clone.querySelector('.propiedad-ubicacion').textContent =
        `${propiedad.distrito}, ${propiedad.provincia}`;
    
    // Precio
    clone.querySelector('.propiedad-precio').textContent =
        `Precio: ${formatearPrecio(propiedad.precio)}`;
    
    // Precio final (si existe)
    if (propiedad.precio_final) {
        clone.querySelector('.propiedad-precio-final').textContent =
            `Precio final: ${formatearPrecio(propiedad.precio_final)}`;
    } else {
        clone.querySelector('.propiedad-precio-final').style.display = 'none';
    }
    
    // Precio por m²
    const precioM2 = propiedad.precio_m2_final || propiedad.precio_m2;
    if (precioM2) {
        clone.querySelector('.propiedad-precio-m2').textContent =
            `US$ ${precioM2.toFixed(2)}/m²`;
    }
    
    // Botón para quitar
    const btnQuitar = clone.querySelector('.btn-quitar');
    btnQuitar.addEventListener('click', () => {
        toggleSeleccionarPropiedad(propiedad.id);
    });
    
    // Botón para ver detalles
    const btnDetalle = clone.querySelector('.btn-detalle');
    btnDetalle.addEventListener('click', () => {
        mostrarDetallePropiedad(propiedad);
    });
    
    // Insertar en contenedor mobile (offcanvas)
    const container = document.getElementById('comparablesContainerMobile');
    const sinSeleccionados = document.getElementById('sinSeleccionadosMobile');
    
    if (sinSeleccionados) {
        sinSeleccionados.style.display = 'none';
    }
    
    if (container) {
        container.prepend(clone);
    }
    
    // También insertar en contenedor tablet (inline)
    const containerTablet = document.getElementById('comparablesContainerTablet');
    const sinSeleccionadosTablet = document.getElementById('sinSeleccionadosTablet');
    
    if (sinSeleccionadosTablet) {
        sinSeleccionadosTablet.style.display = 'none';
    }
    
    if (containerTablet) {
        // Clonar el template nuevamente para tablet
        const template = document.getElementById('templatePropiedad');
        const cloneTablet = template.content.cloneNode(true);
        const cardTablet = cloneTablet.querySelector('.propiedad-card');
        cardTablet.id = `propiedad-tablet-${propiedad.id}`;
        
        // Rellenar datos
        const imgT = cloneTablet.querySelector('.propiedad-imagen');
        imgT.src = propiedad.imagen_url || '/static/acm/img/no-image.svg';
        cloneTablet.querySelector('.propiedad-tipo').textContent = propiedad.tipo;
        cloneTablet.querySelector('.propiedad-estado').textContent = propiedad.estado;
        cloneTablet.querySelector('.propiedad-ubicacion').textContent =
            `${propiedad.distrito}, ${propiedad.provincia}`;
        cloneTablet.querySelector('.propiedad-precio').textContent =
            `Precio: ${formatearPrecio(propiedad.precio)}`;
        if (propiedad.precio_final) {
            cloneTablet.querySelector('.propiedad-precio-final').textContent =
                `Precio final: ${formatearPrecio(propiedad.precio_final)}`;
        } else {
            cloneTablet.querySelector('.propiedad-precio-final').style.display = 'none';
        }
        const precioM2T = propiedad.precio_m2_final || propiedad.precio_m2;
        if (precioM2T) {
            cloneTablet.querySelector('.propiedad-precio-m2').textContent =
                `US$ ${precioM2T.toFixed(2)}/m²`;
        }
        
        // Botón para quitar
        const btnQuitarT = cloneTablet.querySelector('.btn-quitar');
        btnQuitarT.addEventListener('click', () => {
            toggleSeleccionarPropiedad(propiedad.id);
        });
        // Botón para ver detalles
        const btnDetalleT = cloneTablet.querySelector('.btn-detalle');
        btnDetalleT.addEventListener('click', () => {
            mostrarDetallePropiedad(propiedad);
        });
        
        containerTablet.prepend(cloneTablet);
    }
}

// Eliminar tarjeta de propiedad
function eliminarTarjetaPropiedad(id) {
    const card = document.getElementById(`propiedad-${id}`);
    if (card) {
        card.remove();
    }
    
    // También eliminar tarjeta tablet
    const cardTablet = document.getElementById(`propiedad-tablet-${id}`);
    if (cardTablet) {
        cardTablet.remove();
    }
    
    // Mostrar mensaje si no hay seleccionados
    if (propiedadesSeleccionadas.size === 0) {
        const sinSeleccionados = document.getElementById('sinSeleccionadosMobile');
        if (sinSeleccionados) {
            sinSeleccionados.style.display = 'block';
        }
        const sinSeleccionadosTablet = document.getElementById('sinSeleccionadosTablet');
        if (sinSeleccionadosTablet) {
            sinSeleccionadosTablet.style.display = 'block';
        }
    }
}

// Actualizar contadores (mobile, tablet y desktop)
function actualizarContadores() {
    // Actualizar contador del botón flotante mobile
    const mobileCount = document.getElementById('mobileComparablesCount');
    if (mobileCount) {
        mobileCount.textContent = '(' + propiedadesSeleccionadas.size + ')';
    }
    // Actualizar contador tablet
    const tabletCount = document.getElementById('tabletComparablesCount');
    if (tabletCount) {
        tabletCount.textContent = propiedadesSeleccionadas.size;
    }
    // Habilitar/deshabilitar botón "Resumen ACM" (móvil)
    const btnResumenACM = document.getElementById('btnResumenACM');
    if (btnResumenACM) {
        btnResumenACM.disabled = propiedadesSeleccionadas.size === 0;
    }
    // Habilitar/deshabilitar botón "Resumen ACM" (desktop)
    const btnResumenACMDesktop = document.getElementById('btnResumenACMDesktop');
    if (btnResumenACMDesktop) {
        btnResumenACMDesktop.disabled = propiedadesSeleccionadas.size === 0;
    }
    // Habilitar/deshabilitar botón PDF (desktop/tablet)
    const btnPDF = document.getElementById('btnPDF_ACM');
    if (btnPDF) {
        btnPDF.disabled = propiedadesSeleccionadas.size === 0;
    }
    // Habilitar/deshabilitar botón PDF (modal móvil)
    const btnPDFModal = document.getElementById('btnPDF_ACM_modal');
    if (btnPDFModal) {
        btnPDFModal.disabled = propiedadesSeleccionadas.size === 0;
    }
    // Habilitar/deshabilitar botón Compartir (desktop/tablet)
    const btnCompartir = document.getElementById('btnCompartirACM');
    if (btnCompartir) {
        btnCompartir.disabled = propiedadesSeleccionadas.size === 0;
    }
    // Habilitar/deshabilitar botón Compartir (modal móvil)
    const btnCompartirModal = document.getElementById('btnCompartirACM_modal');
    if (btnCompartirModal) {
        btnCompartirModal.disabled = propiedadesSeleccionadas.size === 0;
    }
}

// Actualizar números secuenciales en marcadores y tarjetas
function actualizarNumerosSeleccionados() {
    let index = 1;
    for (const [id, data] of propiedadesSeleccionadas) {
        const marcadorInfo = marcadoresComparables.get(id);
        if (marcadorInfo) {
            // Actualizar etiqueta del marcador con el número
            marcadorInfo.marker.setLabel({
                text: index.toString(),
                color: "white",
                fontSize: "14px",
                fontWeight: "bold"
            });
        }
        // Actualizar tarjeta (si existe)
        const tarjeta = document.getElementById(`propiedad-${id}`);
        if (tarjeta) {
            const numeroElement = tarjeta.querySelector('.propiedad-numero');
            if (numeroElement) {
                numeroElement.textContent = `#${index}`;
            }
        }
        index++;
    }
}

// Actualizar resumen ACM
function actualizarResumenACM() {
    const propiedades = Array.from(propiedadesSeleccionadas.values());
    
    if (propiedades.length === 0) {
        // Mostrar estado vacío
        const emptyHtml = `
            <div class="col-12 text-center py-4 text-muted">
                <i class="bi bi-graph-up display-6 mb-3"></i>
                <p class="mb-0">Selecciona propiedades comparables para ver el análisis</p>
            </div>
        `;
        const resumenACM = document.getElementById('resumenACM');
        if (resumenACM) resumenACM.innerHTML = emptyHtml;
        const tabletResumenACM = document.getElementById('tabletResumenACM');
        if (tabletResumenACM) tabletResumenACM.innerHTML = emptyHtml;
        return;
    }
    
    // Calcular estadísticas
    const preciosM2 = propiedades
        .map(p => p.precio_m2_final || p.precio_m2)
        .filter(p => p && p > 0);
    
    if (preciosM2.length === 0) {
        return;
    }
    
    const min = Math.min(...preciosM2);
    const max = Math.max(...preciosM2);
    const promedio = preciosM2.reduce((a, b) => a + b, 0) / preciosM2.length;
    
    // Calcular promedio ponderado por distancia
    let sumaPonderada = 0;
    let sumaPesos = 0;
    
    propiedades.forEach(p => {
        const precio = p.precio_m2_final || p.precio_m2;
        const distancia = p.distancia_metros || 1;
        if (precio && precio > 0) {
            const peso = 1 / (distancia + 1);
            sumaPonderada += precio * peso;
            sumaPesos += peso;
        }
    });
    
    const promedioPonderado = sumaPesos > 0 ? sumaPonderada / sumaPesos : promedio;
    
    // Obtener metros a valuar del formulario
    const tipoPropiedad = document.getElementById('tipoPropiedad').value.toLowerCase();
    const esTerreno = tipoPropiedad === 'terreno';
    const metrosConstruccion = parseFloat(document.getElementById('metrosConstruccion').value) || 0;
    const metrosTerreno = parseFloat(document.getElementById('metrosTerreno').value) || 0;
    const metros = esTerreno ? metrosTerreno : (metrosConstruccion || metrosTerreno);
    
    // Calcular estimación
    const estimacionMin = metros * min;
    const estimacionMax = metros * max;
    const estimacionPromedio = metros * promedioPonderado;
    
    // Calcular los tres valores basados en el valor comercial (estimacionPromedio)
    const valorComercial = estimacionPromedio;
    const precioVentaSugerido = valorComercial * 0.9499;
    const valorRealizacionInmediata = valorComercial * 0.90;
    
    // Función auxiliar para formatear moneda (US$)
    function formatearMoneda(valor) {
        return `US$ ${valor.toLocaleString('es-PE', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    }
    
    // Generar HTML del resumen compacto - 3 tarjetas de valor
    const resumenHtml = `
        <!-- Fila: 3 tarjetas (izquierda: precio venta sugerido, centro: estimación principal, derecha: valor realización inmediata) -->
        <div class="row g-2">
            <div class="col-md-4">
                <div class="card border-0 bg-light h-100">
                    <div class="card-body p-2 text-center d-flex flex-column justify-content-center">
                        <div class="h6 text-primary mb-1">${formatearMoneda(precioVentaSugerido)}</div>
                        <div class="small text-muted mb-1">Precio Venta Sugerido</div>
                        <div class="small text-success">94.99% del comercial</div>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card border-0 bg-success bg-opacity-90 text-white h-100">
                    <div class="card-body p-3 text-center d-flex flex-column justify-content-center">
                        <div class="small mb-1">ESTIMACIÓN PARA TU PROPIEDAD</div>
                        <div class="h4 mb-1">${formatearMoneda(valorComercial)}</div>
                        <div class="small opacity-75">Valor Comercial (100%)</div>
                        <div class="small mt-1" style="color: #ff4444; font-weight: bold;">Precio/m²: ${formatearMoneda(promedioPonderado)}</div>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card border-0 bg-light h-100">
                    <div class="card-body p-2 text-center d-flex flex-column justify-content-center">
                        <div class="h6 text-primary mb-1">${formatearMoneda(valorRealizacionInmediata)}</div>
                        <div class="small text-muted mb-1">Valor Realización Inmediata</div>
                        <div class="small text-success">90.00% del comercial</div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Nota al pie -->
        <div class="row mt-3">
            <div class="col-12">
                <div class="text-muted small">
                    Basado en ${metros.toFixed(0)} m²${esTerreno ? ' de terreno' : ' de construcción'} y ${propiedades.length} propiedades comparables.
                </div>
            </div>
        </div>
    `;
    
    // Actualizar modal resumen ACM
    const resumenACM = document.getElementById('resumenACM');
    if (resumenACM) resumenACM.innerHTML = resumenHtml;
    
    // Actualizar resumen ACM inline para tablet
    const tabletResumenACM = document.getElementById('tabletResumenACM');
    if (tabletResumenACM) tabletResumenACM.innerHTML = resumenHtml;
}

// Funciones auxiliares

// Limpiar marcadores de propiedades comparables
function limpiarMarcadoresComparables() {
    marcadoresComparables.forEach((info, id) => {
        info.marker.setMap(null);
    });
    marcadoresComparables.clear();
}

// Limpiar propiedades seleccionadas
function limpiarPropiedadesSeleccionadas() {
    // Eliminar todas las tarjetas del DOM
    propiedadesSeleccionadas.forEach((data, id) => {
        const card = document.getElementById(`propiedad-${id}`);
        if (card) {
            card.remove();
        }
    });
    
    // Limpiar el Map de propiedades seleccionadas
    propiedadesSeleccionadas.clear();
    
    // Mostrar mensaje de "sin seleccionados" en mobile
    const sinSeleccionados = document.getElementById('sinSeleccionadosMobile');
    if (sinSeleccionados) {
        sinSeleccionados.style.display = 'block';
    }
    
    // Actualizar contadores y resumen
    actualizarContadores();
    actualizarResumenACM();
}

// Ajustar vista del mapa para mostrar todos los marcadores + círculo
function ajustarVistaMapa() {
    const bounds = new google.maps.LatLngBounds();
    
    // Incluir marcador principal
    if (marcadorPrincipal) {
        bounds.extend(marcadorPrincipal.getPosition());
    }
    
    // Incluir marcadores comparables
    marcadoresComparables.forEach(info => {
        bounds.extend(info.marker.getPosition());
    });
    
    // Incluir círculo de radio (extender un poco más allá del radio)
    if (circuloRadio) {
        const center = circuloRadio.getCenter();
        const radius = circuloRadio.getRadius();
        const north = google.maps.geometry.spherical.computeOffset(center, radius, 0);
        const south = google.maps.geometry.spherical.computeOffset(center, radius, 180);
        const east = google.maps.geometry.spherical.computeOffset(center, radius, 90);
        const west = google.maps.geometry.spherical.computeOffset(center, radius, 270);
        bounds.extend(north);
        bounds.extend(south);
        bounds.extend(east);
        bounds.extend(west);
    }
    
    // Si no hay nada que ajustar, usar vista por defecto
    if (bounds.isEmpty()) {
        acmMap.setCenter({ lat: -16.4090, lng: -71.5375 });
        acmMap.setZoom(13);
    } else {
        acmMap.fitBounds(bounds, { padding: 50 });
    }
}

// Calcular distancia entre dos puntos (fórmula de Haversine)
function calcularDistancia(lat1, lon1, lat2, lon2) {
    const R = 6371000; // Radio de la Tierra en metros
    const φ1 = lat1 * Math.PI / 180;
    const φ2 = lat2 * Math.PI / 180;
    const Δφ = (lat2 - lat1) * Math.PI / 180;
    const Δλ = (lon2 - lon1) * Math.PI / 180;

    const a = Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
              Math.cos(φ1) * Math.cos(φ2) *
              Math.sin(Δλ / 2) * Math.sin(Δλ / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

    return R * c; // Distancia en metros
}

// Mostrar toast de notificación
function mostrarToast(tipo, mensaje) {
    const toastContainer = document.getElementById('toastContainer');
    if (!toastContainer) return;
    
    const toastId = 'toast-' + Date.now();
    const toastHTML = `
        <div id="${toastId}" class="toast align-items-center text-bg-${tipo} border-0" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">
                    ${mensaje}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>
    `;
    
    toastContainer.insertAdjacentHTML('beforeend', toastHTML);
    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement, { delay: 3000 });
    toast.show();
    
    // Eliminar después de ocultar
    toastElement.addEventListener('hidden.bs.toast', () => {
        toastElement.remove();
    });
}

// Mostrar detalles de propiedad en modal
function mostrarDetallePropiedad(propiedad) {
    // Llenar imagen
    const imagen = document.getElementById('detalle-imagen');
    if (imagen) {
        imagen.src = propiedad.imagen_url || '/static/acm/img/no-image.svg';
    }
    
    // Llenar información básica
    document.getElementById('detalle-tipo').textContent = propiedad.tipo || 'No especificado';
    document.getElementById('detalle-estado').textContent = propiedad.estado || 'En Publicación';
    document.getElementById('detalle-ubicacion').textContent =
        `${propiedad.distrito || ''}, ${propiedad.provincia || ''}, ${propiedad.departamento || ''}`.trim();
    document.getElementById('detalle-distancia').textContent =
        propiedad.distancia_metros ? `${propiedad.distancia_metros.toFixed(0)} metros` : 'No disponible';
    document.getElementById('detalle-fuente').textContent = propiedad.fuente === 'propifai' ? 'Propifai' : 'Local';
    
    // Llenar características
    document.getElementById('detalle-precio').textContent = formatearPrecio(propiedad.precio);
    document.getElementById('detalle-precio-final').textContent = formatearPrecio(propiedad.precio_final);
    document.getElementById('detalle-precio-m2').textContent =
        propiedad.precio_m2_final || propiedad.precio_m2 ?
        `US$ ${(propiedad.precio_m2_final || propiedad.precio_m2).toFixed(2)}/m²` : 'No disponible';
    
    document.getElementById('detalle-area-construccion').textContent =
        propiedad.metros_construccion ? `${propiedad.metros_construccion} m²` : 'No disponible';
    document.getElementById('detalle-area-terreno').textContent =
        propiedad.metros_terreno ? `${propiedad.metros_terreno} m²` : 'No disponible';
    document.getElementById('detalle-habitaciones').textContent =
        propiedad.habitaciones ? propiedad.habitaciones : 'No disponible';
    document.getElementById('detalle-banos').textContent =
        propiedad.baños ? propiedad.baños : 'No disponible';
    
    // Llenar información adicional
    const adicionalDiv = document.getElementById('detalle-adicional');
    if (adicionalDiv) {
        let html = '';
        if (propiedad.codigo) {
            html += `<p><strong>Código:</strong> ${propiedad.codigo}</p>`;
        }
        if (propiedad.titulo) {
            html += `<p><strong>Título:</strong> ${propiedad.titulo}</p>`;
        }
        if (propiedad.es_propify) {
            html += `<p><strong>Fuente:</strong> Propifai</p>`;
        }
        if (propiedad.fuente === 'local') {
            html += `<p><strong>Fuente:</strong> Base de datos local</p>`;
        }
        adicionalDiv.innerHTML = html || '<p>No hay información adicional disponible.</p>';
    }
    
    // Actualizar enlace a página web
    const urlLink = document.getElementById('detalle-url');
    if (urlLink) {
        // Determinar la URL: priorizar url_propiedad (enlace original externo)
        let url = propiedad.url_propiedad || '';
        
        // Si es Propifai y tiene código pero no URL directa, construir enlace a Propifai
        if (!url && propiedad.es_propify && propiedad.codigo) {
            url = `https://propifai.com/propiedad/${propiedad.codigo}`;
        }
        
        if (url) {
            urlLink.href = url;
            urlLink.target = '_blank';
            urlLink.rel = 'noopener noreferrer';
            urlLink.classList.remove('disabled');
            urlLink.innerHTML = '<i class="bi bi-box-arrow-up-right me-1"></i>Ver pagina web original &raquo;';
            console.log(`ACM: URL para propiedad ${propiedad.id}: ${url}`);
        } else {
            urlLink.href = '#';
            urlLink.classList.add('disabled');
            urlLink.innerHTML = '<i class="bi bi-box-arrow-up-right me-1"></i>Sin enlace disponible';
            console.log(`ACM: Sin URL para propiedad ${propiedad.id}`);
        }
    }
    
    // Mostrar modal
    const modal = new bootstrap.Modal(document.getElementById('modalDetallePropiedad'));
    modal.show();
}

// Formatear precio en dólares
function formatearPrecio(precio) {
    if (!precio) return 'US$ 0.00';
    return `US$ ${parseFloat(precio).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

// Obtener token CSRF
function getCSRFToken() {
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
    return csrfToken ? csrfToken.value : '';
}

// Inicializar buscador de direcciones con Google Places Autocomplete + Geocoding
function inicializarBuscadorDirecciones() {
    const searchInput = document.getElementById('acmSearchBox');
    const searchBtn = document.getElementById('btnSearchAddress');
    if (!searchInput) {
        console.error('No se encontró el input acmSearchBox');
        return;
    }

    console.log('Inicializando buscador de direcciones...');

    // --- Google Places Autocomplete ---
    let autocomplete = null;
    try {
        if (!google || !google.maps || !google.maps.places) {
            throw new Error('Google Maps Places API no disponible');
        }

        console.log('Creando Autocomplete sin bounds específicos');

        autocomplete = new google.maps.places.Autocomplete(searchInput, {
            types: ['geocode', 'establishment'],
            componentRestrictions: { country: 'PE' },
            fields: ['formatted_address', 'geometry', 'name', 'address_components']
        });

        // Bind to map bounds for better suggestions
        autocomplete.bindTo('bounds', acmMap);

        console.log('Autocomplete creado exitosamente');

        // Cuando el usuario selecciona una sugerencia del autocomplete
        autocomplete.addListener('place_changed', () => {
            console.log('Place changed event fired');
            const place = autocomplete.getPlace();
            if (!place.geometry) {
                console.warn('Place sin geometría, usando geocoding manual');
                // Si no tiene geometría, hacer geocoding manual
                geocodeAddress(searchInput.value);
                return;
            }
            
            const location = place.geometry.location;
            console.log('Ubicación seleccionada:', location.lat(), location.lng());
            
            // Centrar mapa en la ubicación seleccionada
            if (place.geometry.viewport) {
                acmMap.fitBounds(place.geometry.viewport);
            } else {
                acmMap.setCenter(location);
                acmMap.setZoom(16);
            }
            
            // Colocar marcador principal
            colocarMarcadorPrincipal(location);
            searchInput.blur();
        });

        // Estilo personalizado para el dropdown de Places
        setTimeout(() => {
            const pacContainer = document.querySelector('.pac-container');
            if (pacContainer) {
                pacContainer.style.zIndex = '99999';
                console.log('Z-index aplicado al pac-container');
            } else {
                console.warn('No se encontró .pac-container');
            }
        }, 1000);

    } catch (e) {
        console.warn('Google Places Autocomplete no disponible, usando solo Geocoding:', e);
    }

    // --- Geocoding function (fallback + búsqueda manual) ---
    function geocodeAddress(query) {
        if (!query || query.trim() === '') return;
        
        const geocoder = new google.maps.Geocoder();
        // Agregar "Arequipa, Perú" para restringir la búsqueda
        const fullQuery = query.toLowerCase().includes('arequipa') ? query : `${query}, Arequipa, Perú`;
        
        geocoder.geocode({
            address: fullQuery,
            region: 'PE'
        }, (results, status) => {
            if (status === 'OK' && results.length > 0) {
                const location = results[0].geometry.location;
                
                // Centrar mapa en la ubicación
                if (results[0].geometry.viewport) {
                    acmMap.fitBounds(results[0].geometry.viewport);
                } else {
                    acmMap.setCenter(location);
                    acmMap.setZoom(16);
                }
                
                // Colocar marcador principal
                colocarMarcadorPrincipal(location);
                
                searchInput.blur();
            } else {
                console.warn('Geocoder no encontró resultados para:', fullQuery, status);
                mostrarToast('warning', 'No se encontró la dirección. Intenta con otro término (ej: "Cayma", "Yanahuara", "Plaza de Armas Arequipa").');
            }
        });
    }

    // --- Event Listeners ---

    // Botón de búsqueda (Geocoding manual)
    if (searchBtn) {
        searchBtn.addEventListener('click', () => {
            geocodeAddress(searchInput.value);
        });
    }

    // Enter en el input (solo si NO se usó Autocomplete)
    searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            // Si hay un autocomplete activo y se seleccionó una sugerencia,
            // el evento 'place_changed' ya se encargó. Si no, hacemos geocoding.
            if (!autocomplete || !document.querySelector('.pac-container.pac-logo:not(.pac-container-shadow)')) {
                geocodeAddress(searchInput.value);
            }
        }
    });
}

// ============================================================
// COMPARTIR ANÁLISIS ACM POR WHATSAPP CON ENLACE UTM
// ============================================================

/**
 * Genera un enlace único con UUID, lo guarda en BD y abre WhatsApp
 * con el enlace UTM para trackear clicks.
 */
async function compartirACM_WhatsApp() {
    const propiedades = Array.from(propiedadesSeleccionadas.values());
    if (propiedades.length === 0) {
        mostrarToast('warning', 'Selecciona al menos una propiedad comparable para compartir.');
        return;
    }

    // Mostrar indicador de carga
    const btns = [
        document.getElementById('btnCompartirACM'),
        document.getElementById('btnCompartirACM_modal')
    ].filter(Boolean);
    const estadosOriginales = btns.map(btn => ({ html: btn.innerHTML, disabled: btn.disabled }));
    btns.forEach(btn => {
        btn.innerHTML = '<i class="bi bi-hourglass-split me-1"></i>Generando...';
        btn.disabled = true;
    });

    try {
        // Recalcular estadísticas (misma lógica que actualizarResumenACM)
        const preciosM2 = propiedades
            .map(p => p.precio_m2_final || p.precio_m2)
            .filter(p => p && p > 0);

        const min = Math.min(...preciosM2);
        const max = Math.max(...preciosM2);
        const promedio = preciosM2.reduce((a, b) => a + b, 0) / preciosM2.length;

        let sumaPonderada = 0;
        let sumaPesos = 0;
        propiedades.forEach(p => {
            const precio = p.precio_m2_final || p.precio_m2;
            const distancia = p.distancia_metros || 1;
            if (precio && precio > 0) {
                const peso = 1 / (distancia + 1);
                sumaPonderada += precio * peso;
                sumaPesos += peso;
            }
        });
        const promedioPonderado = sumaPesos > 0 ? sumaPonderada / sumaPesos : promedio;

        const tipoPropiedad = document.getElementById('tipoPropiedad').value.toLowerCase();
        const esTerreno = tipoPropiedad === 'terreno';
        const metrosConstruccion = parseFloat(document.getElementById('metrosConstruccion').value) || 0;
        const metrosTerreno = parseFloat(document.getElementById('metrosTerreno').value) || 0;
        const metros = esTerreno ? metrosTerreno : (metrosConstruccion || metrosTerreno);

        const estimacionPromedio = metros * promedioPonderado;
        const valorComercial = estimacionPromedio;
        const precioVentaSugerido = valorComercial * 0.9499;
        const valorRealizacionInmediata = valorComercial * 0.90;

        // Preparar datos para enviar al backend
        const propiedadesData = propiedades.map(p => ({
            id: p.id,
            tipo: p.tipo,
            distrito: p.distrito,
            precio: p.precio,
            precio_m2: p.precio_m2_final || p.precio_m2,
            distancia_metros: p.distancia_metros,
            fuente: p.es_propify || p.fuente === 'propifai' ? 'Propifai' : 'Externo',
            es_propify: p.es_propify || false
        }));

        const payload = {
            tipo_propiedad: tipoPropiedad,
            area_m2: metros,
            es_terreno: esTerreno,
            precio_min_m2: min,
            precio_max_m2: max,
            precio_promedio_m2: promedio,
            precio_promedio_ponderado_m2: promedioPonderado,
            valor_comercial: valorComercial,
            precio_venta_sugerido: precioVentaSugerido,
            valor_realizacion: valorRealizacionInmediata,
            num_comparables: propiedades.length,
            propiedades: propiedadesData,
            // Enviar el ID del usuario de intelligence para asociar el enlace
            user_id: (typeof ACM_USER_ID !== 'undefined' && ACM_USER_ID !== null) ? ACM_USER_ID : undefined
        };

        // Enviar al backend para crear el enlace único
        const response = await fetch('/acm/generar-enlace/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken(),
            },
            body: JSON.stringify(payload),
        });

        const data = await response.json();

        if (data.status === 'ok') {
            // Abrir WhatsApp con el enlace
            if (data.whatsapp_url) {
                // Detectar si es dispositivo móvil
                const isMobile = /Android|iPhone|iPad|iPod|webOS|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
                const isAndroid = /Android/i.test(navigator.userAgent);
                const isIOS = /iPhone|iPad|iPod/i.test(navigator.userAgent);
                
                if (isMobile) {
                    // Extraer phone y text de la URL de api.whatsapp.com
                    const urlObj = new URL(data.whatsapp_url);
                    const phone = urlObj.searchParams.get('phone') || '';
                    const textRaw = urlObj.searchParams.get('text') || '';
                    // El texto ya viene codificado del backend, decodificarlo para re-codificarlo correctamente
                    const textDecoded = decodeURIComponent(textRaw);
                    const textEncoded = encodeURIComponent(textDecoded);
                    
                    if (isAndroid) {
                        // Android: usar intent:// que abre la app nativa directamente
                        // Formato: intent://send?phone=X&text=Y#Intent;scheme=whatsapp;package=com.whatsapp;end
                        const intentUrl = `intent://send?phone=${phone}&text=${textEncoded}#Intent;scheme=whatsapp;package=com.whatsapp;end`;
                        window.location.href = intentUrl;
                        // Fallback: si no abre la app, usar api.whatsapp.com después de 1.5s
                        setTimeout(() => {
                            window.location.href = data.whatsapp_url;
                        }, 1500);
                    } else if (isIOS) {
                        // iOS: usar whatsapp:// que funciona en Safari
                        const iosUrl = `whatsapp://send?phone=${phone}&text=${textEncoded}`;
                        window.location.href = iosUrl;
                        // Fallback
                        setTimeout(() => {
                            window.location.href = data.whatsapp_url;
                        }, 1500);
                    } else {
                        // Otros móviles: api.whatsapp.com
                        window.location.href = data.whatsapp_url;
                    }
                } else {
                    // Desktop: abrir WhatsApp Web directamente
                    window.location.href = data.whatsapp_url;
                }
            } else {
                // Si no hay teléfono, copiar enlace al portapapeles
                if (navigator.clipboard && data.enlace_utm) {
                    await navigator.clipboard.writeText(data.enlace_utm);
                    mostrarToast('success', 'Enlace copiado al portapapeles (sin teléfono configurado).');
                } else {
                    mostrarToast('warning', 'No se pudo abrir WhatsApp. Verifica tu número de teléfono en tu perfil.');
                }
            }
        } else {
            throw new Error(data.message || 'Error al generar el enlace');
        }
    } catch (error) {
        console.error('Error compartiendo ACM:', error);
        mostrarToast('danger', 'Error: ' + error.message);
    } finally {
        // Restaurar botones
        btns.forEach((btn, i) => {
            btn.innerHTML = estadosOriginales[i].html;
            btn.disabled = estadosOriginales[i].disabled;
        });
    }
}

// ============================================================
// GENERACIÓN DE PDF DEL ANÁLISIS ACM
// ============================================================

/**
 * Genera un PDF con el resumen del análisis ACM usando html2pdf.js
 * Primero guarda el análisis en el backend (historial) y obtiene un código ACM único.
 * Incluye: encabezado Propifai, código ACM, 3 tarjetas de valoración, tabla de propiedades comparables
 */
async function generarPDF_ACM() {
    const propiedades = Array.from(propiedadesSeleccionadas.values());
    if (propiedades.length === 0) {
        mostrarToast('warning', 'Selecciona al menos una propiedad comparable para generar el PDF.');
        return;
    }

    // Mostrar indicador de carga en ambos botones (modal y principal)
    const btns = [
        document.getElementById('btnPDF_ACM'),
        document.getElementById('btnPDF_ACM_modal')
    ].filter(Boolean);
    const estadosOriginales = btns.map(btn => ({ html: btn.innerHTML, disabled: btn.disabled }));
    btns.forEach(btn => {
        btn.innerHTML = '<i class="bi bi-hourglass-split me-1"></i>Guardando...';
        btn.disabled = true;
    });

    try {
        // --- Recalcular estadísticas (misma lógica que actualizarResumenACM) ---
        const preciosM2 = propiedades
            .map(p => p.precio_m2_final || p.precio_m2)
            .filter(p => p && p > 0);

        const min = Math.min(...preciosM2);
        const max = Math.max(...preciosM2);
        const promedio = preciosM2.reduce((a, b) => a + b, 0) / preciosM2.length;

        let sumaPonderada = 0;
        let sumaPesos = 0;
        propiedades.forEach(p => {
            const precio = p.precio_m2_final || p.precio_m2;
            const distancia = p.distancia_metros || 1;
            if (precio && precio > 0) {
                const peso = 1 / (distancia + 1);
                sumaPonderada += precio * peso;
                sumaPesos += peso;
            }
        });
        const promedioPonderado = sumaPesos > 0 ? sumaPonderada / sumaPesos : promedio;

        const tipoPropiedad = document.getElementById('tipoPropiedad').value.toLowerCase();
        const esTerreno = tipoPropiedad === 'terreno';
        const metrosConstruccion = parseFloat(document.getElementById('metrosConstruccion').value) || 0;
        const metrosTerreno = parseFloat(document.getElementById('metrosTerreno').value) || 0;
        const metros = esTerreno ? metrosTerreno : (metrosConstruccion || metrosTerreno);

        const estimacionMin = metros * min;
        const estimacionMax = metros * max;
        const estimacionPromedio = metros * promedioPonderado;
        const valorComercial = estimacionPromedio;
        const precioVentaSugerido = valorComercial * 0.9499;
        const valorRealizacionInmediata = valorComercial * 0.90;

        // --- 1. Guardar en backend primero ---
        btns.forEach(btn => { if (btn) btn.innerHTML = '<i class="bi bi-cloud-upload me-1"></i>Guardando...'; });

        const propiedadesData = propiedades.map(p => ({
            id: p.id,
            tipo: p.tipo,
            distrito: p.distrito,
            precio: p.precio,
            precio_m2: p.precio_m2_final || p.precio_m2,
            distancia_metros: p.distancia_metros,
            fuente: p.es_propify || p.fuente === 'propifai' ? 'Propifai' : 'Externo',
            es_propify: p.es_propify || false
        }));

        const payload = {
            tipo_propiedad: tipoPropiedad,
            area_m2: metros,
            es_terreno: esTerreno,
            precio_min_m2: min,
            precio_max_m2: max,
            precio_promedio_m2: promedio,
            precio_promedio_ponderado_m2: promedioPonderado,
            valor_comercial: valorComercial,
            precio_venta_sugerido: precioVentaSugerido,
            valor_realizacion: valorRealizacionInmediata,
            num_comparables: propiedades.length,
            propiedades: propiedadesData,
            user_id: (typeof ACM_USER_ID !== 'undefined' && ACM_USER_ID !== null) ? ACM_USER_ID : undefined
        };

        const response = await fetch('/acm/guardar-acm/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken(),
            },
            body: JSON.stringify(payload),
        });

        const data = await response.json();

        let codigoACM = '';
        if (data.status === 'ok') {
            codigoACM = data.codigo || '';
        } else {
            console.warn('No se pudo guardar en historial, generando PDF igual:', data.message);
        }

        // --- 2. Generar PDF con html2pdf.js ---
        btns.forEach(btn => { if (btn) btn.innerHTML = '<i class="bi bi-file-earmark-pdf me-1"></i>Generando PDF...'; });

        function formatearMoneda(valor) {
            return 'US$ ' + valor.toLocaleString('es-PE', {minimumFractionDigits: 2, maximumFractionDigits: 2});
        }

        function formatearPrecioLocal(precio) {
            if (!precio) return 'US$ 0.00';
            return 'US$ ' + parseFloat(precio).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        }

        const fechaActual = new Date().toLocaleDateString('es-PE', {
            year: 'numeric', month: 'long', day: 'numeric'
        });

        // Filas de propiedades para la tabla
        let filasPropiedades = '';
        propiedades.forEach((p, i) => {
            const precioM2 = p.precio_m2_final || p.precio_m2;
            const distancia = p.distancia_metros ? (p.distancia_metros.toFixed(0) + ' m') : '—';
            const fuente = p.es_propify || p.fuente === 'propifai' ? 'Propifai' : 'Externo';
            filasPropiedades += `
                <tr>
                    <td style="padding:6px 8px;border:1px solid #ddd;font-size:11px;text-align:center;">${i + 1}</td>
                    <td style="padding:6px 8px;border:1px solid #ddd;font-size:11px;">${p.tipo || '—'}</td>
                    <td style="padding:6px 8px;border:1px solid #ddd;font-size:11px;">${p.distrito || '—'}</td>
                    <td style="padding:6px 8px;border:1px solid #ddd;font-size:11px;text-align:right;">${formatearPrecioLocal(p.precio)}</td>
                    <td style="padding:6px 8px;border:1px solid #ddd;font-size:11px;text-align:right;">${precioM2 ? 'US$ ' + precioM2.toFixed(2) : '—'}</td>
                    <td style="padding:6px 8px;border:1px solid #ddd;font-size:11px;text-align:right;">${distancia}</td>
                    <td style="padding:6px 8px;border:1px solid #ddd;font-size:11px;text-align:center;">${fuente}</td>
                </tr>
            `;
        });

        const codigoDisplay = codigoACM ? `<p style="margin:2px 0 0 0;font-size:14px;color:#10b981;font-weight:bold;font-family:'Courier New',monospace;">Código: ${codigoACM}</p>` : '';

        const pdfContent = `
            <div id="pdf-acm-content" style="font-family:Arial,Helvetica,sans-serif;padding:30px;color:#1a1a2e;max-width:800px;margin:0 auto;">
                <!-- Encabezado -->
                <div style="text-align:center;margin-bottom:25px;padding-bottom:15px;border-bottom:3px solid #10b981;">
                    <h1 style="margin:0;font-size:22px;color:#10b981;font-weight:bold;">PROPIFAI</h1>
                    <p style="margin:4px 0 0 0;font-size:13px;color:#666;">Análisis Comparativo de Mercado (ACM)</p>
                    <p style="margin:2px 0 0 0;font-size:11px;color:#999;">Generado el ${fechaActual}</p>
                    ${codigoDisplay}
                </div>

                <!-- Parámetros de búsqueda -->
                <div style="margin-bottom:20px;padding:12px 15px;background:#f0fdf4;border-radius:8px;border-left:4px solid #10b981;">
                    <h3 style="margin:0 0 8px 0;font-size:14px;color:#065f46;">Parámetros del Análisis</h3>
                    <table style="width:100%;font-size:12px;border-collapse:collapse;">
                        <tr>
                            <td style="padding:2px 8px;color:#555;width:50%;"><strong>Tipo:</strong> ${tipoPropiedad.charAt(0).toUpperCase() + tipoPropiedad.slice(1)}</td>
                            <td style="padding:2px 8px;color:#555;width:50%;"><strong>Área:</strong> ${metros.toFixed(0)} m²${esTerreno ? ' (terreno)' : ' (construcción)'}</td>
                        </tr>
                        <tr>
                            <td style="padding:2px 8px;color:#555;"><strong>Comparables:</strong> ${propiedades.length} propiedades</td>
                            <td style="padding:2px 8px;color:#555;"><strong>Rango precio/m²:</strong> US$ ${min.toFixed(2)} – US$ ${max.toFixed(2)}</td>
                        </tr>
                    </table>
                </div>

                <!-- 3 Tarjetas de Valoración -->
                <div style="margin-bottom:20px;">
                    <h3 style="margin:0 0 10px 0;font-size:14px;color:#065f46;">Valoración Estimada</h3>
                    <table style="width:100%;border-collapse:collapse;">
                        <tr>
                            <td style="width:33.33%;padding:6px;">
                                <div style="background:#f8f9fa;border-radius:8px;padding:12px;text-align:center;border:1px solid #e5e7eb;">
                                    <div style="font-size:16px;font-weight:bold;color:#2563eb;">${formatearMoneda(precioVentaSugerido)}</div>
                                    <div style="font-size:10px;color:#666;margin-top:4px;">Precio Venta Sugerido</div>
                                    <div style="font-size:9px;color:#10b981;">94.99% del comercial</div>
                                </div>
                            </td>
                            <td style="width:33.33%;padding:6px;">
                                <div style="background:#10b981;border-radius:8px;padding:14px;text-align:center;color:white;">
                                    <div style="font-size:10px;margin-bottom:4px;">ESTIMACIÓN PARA TU PROPIEDAD</div>
                                    <div style="font-size:20px;font-weight:bold;">${formatearMoneda(valorComercial)}</div>
                                    <div style="font-size:10px;opacity:0.8;">Valor Comercial (100%)</div>
                                    <div style="font-size:10px;margin-top:4px;font-weight:bold;">Precio/m²: ${formatearMoneda(promedioPonderado)}</div>
                                </div>
                            </td>
                            <td style="width:33.33%;padding:6px;">
                                <div style="background:#f8f9fa;border-radius:8px;padding:12px;text-align:center;border:1px solid #e5e7eb;">
                                    <div style="font-size:16px;font-weight:bold;color:#2563eb;">${formatearMoneda(valorRealizacionInmediata)}</div>
                                    <div style="font-size:10px;color:#666;margin-top:4px;">Valor Realización Inmediata</div>
                                    <div style="font-size:9px;color:#10b981;">90.00% del comercial</div>
                                </div>
                            </td>
                        </tr>
                    </table>
                </div>

                <!-- Tabla de propiedades comparables -->
                <div style="margin-bottom:15px;">
                    <h3 style="margin:0 0 8px 0;font-size:14px;color:#065f46;">Propiedades Comparables</h3>
                    <table style="width:100%;border-collapse:collapse;font-size:11px;">
                        <thead>
                            <tr style="background:#10b981;color:white;">
                                <th style="padding:7px 8px;border:1px solid #10b981;text-align:center;width:30px;">#</th>
                                <th style="padding:7px 8px;border:1px solid #10b981;text-align:left;">Tipo</th>
                                <th style="padding:7px 8px;border:1px solid #10b981;text-align:left;">Distrito</th>
                                <th style="padding:7px 8px;border:1px solid #10b981;text-align:right;">Precio</th>
                                <th style="padding:7px 8px;border:1px solid #10b981;text-align:right;">US$/m²</th>
                                <th style="padding:7px 8px;border:1px solid #10b981;text-align:right;">Distancia</th>
                                <th style="padding:7px 8px;border:1px solid #10b981;text-align:center;">Fuente</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${filasPropiedades}
                        </tbody>
                    </table>
                </div>

                <!-- Resumen de estadísticas -->
                <div style="margin-top:15px;padding:12px 15px;background:#f8f9fa;border-radius:8px;border:1px solid #e5e7eb;">
                    <h3 style="margin:0 0 8px 0;font-size:13px;color:#065f46;">Estadísticas de Precio por m²</h3>
                    <table style="width:100%;font-size:12px;border-collapse:collapse;">
                        <tr>
                            <td style="padding:3px 8px;color:#555;"><strong>Mínimo:</strong> US$ ${min.toFixed(2)}/m²</td>
                            <td style="padding:3px 8px;color:#555;"><strong>Máximo:</strong> US$ ${max.toFixed(2)}/m²</td>
                        </tr>
                        <tr>
                            <td style="padding:3px 8px;color:#555;"><strong>Promedio simple:</strong> US$ ${promedio.toFixed(2)}/m²</td>
                            <td style="padding:3px 8px;color:#555;"><strong>Promedio ponderado:</strong> US$ ${promedioPonderado.toFixed(2)}/m²</td>
                        </tr>
                    </table>
                </div>

                <!-- Footer -->
                <div style="margin-top:25px;padding-top:12px;border-top:2px solid #10b981;text-align:center;font-size:10px;color:#999;">
                    <p style="margin:0;">Propifai — Inteligencia Inmobiliaria</p>
                    <p style="margin:2px 0 0 0;">Arequipa, Perú — Este informe es una estimación basada en datos comparables del mercado.</p>
                </div>
            </div>
        `;

        // Crear un contenedor temporal para el PDF
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = pdfContent;
        tempDiv.style.position = 'absolute';
        tempDiv.style.left = '-9999px';
        tempDiv.style.top = '0';
        document.body.appendChild(tempDiv);

        // Opciones de html2pdf
        const opt = {
            margin:        [0.5, 0.5, 0.5, 0.5],
            filename:     codigoACM ? `ACM_${codigoACM}.pdf` : `ACM_${tipoPropiedad}_${new Date().toISOString().split('T')[0]}.pdf`,
            image:        { type: 'jpeg', quality: 0.98 },
            html2canvas:  { scale: 2, useCORS: true, logging: false },
            jsPDF:        { unit: 'in', format: 'a4', orientation: 'portrait' }
        };

        // Generar PDF
        await html2pdf().set(opt).from(tempDiv).save();
        
        // Limpiar
        document.body.removeChild(tempDiv);
        
        const msgCodigo = codigoACM ? ` (${codigoACM})` : '';
        mostrarToast('success', `✅ PDF generado correctamente${msgCodigo}.`);
        
    } catch (error) {
        console.error('Error generando PDF:', error);
        mostrarToast('danger', 'Error: ' + error.message);
    } finally {
        // Restaurar botones
        btns.forEach((btn, i) => {
            if (btn) {
                btn.innerHTML = estadosOriginales[i].html;
                btn.disabled = estadosOriginales[i].disabled;
            }
        });
    }
}

// Auto-inicializar eventos cuando el DOM esté listo (independiente de Google Maps)
document.addEventListener('DOMContentLoaded', function() {
    inicializarEventos();
});