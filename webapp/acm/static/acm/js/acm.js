// Módulo ACM - JavaScript principal

// Variables globales del módulo
let acmMap;
let marcadorPrincipal = null;
let circuloRadio = null;
let marcadoresComparables = new Map(); // id -> {marker, data, seleccionado}
let propiedadesSeleccionadas = new Map(); // id -> data
let propiedadesEncontradas = []; // Todas las propiedades encontradas en la búsqueda

// URLs de iconos (reutilizar del proyecto existente)
const ICONO_PRINCIPAL = 'https://maps.google.com/mapfiles/ms/icons/yellow-dot.png';
const ICONO_COMPARABLE = 'https://maps.google.com/mapfiles/ms/icons/blue-dot.png';
const ICONO_SELECCIONADO = 'https://maps.google.com/mapfiles/ms/icons/red-dot.png';
const ICONO_PROPIFAI = 'https://maps.google.com/mapfiles/ms/icons/green-dot.png';
const ICONO_PROPIFAI_SELECCIONADO = 'https://maps.google.com/mapfiles/ms/icons/orange-dot.png';

// Inicializar mapa ACM
function initACMMap() {
    const defaultCenter = { lat: -16.4090, lng: -71.5375 }; // Arequipa, Perú
    acmMap = new google.maps.Map(document.getElementById('acmMap'), {
        center: defaultCenter,
        zoom: 13,
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

    // Inicializar eventos del formulario
    inicializarEventos();
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
        title: 'Punto a valuar',
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
    
    // Mostrar alerta con coordenadas
    const alerta = document.getElementById('puntoSeleccionadoAlert');
    const texto = document.getElementById('coordenadasTexto');
    texto.textContent = `Lat: ${latLng.lat().toFixed(6)}, Lng: ${latLng.lng().toFixed(6)}`;
    alerta.classList.remove('d-none');

    // Listener para arrastrar marcador
    marcadorPrincipal.addListener('dragend', (event) => {
        console.log('Marcador movido - dragend event fired');
        const newLatLng = event.latLng;
        document.getElementById('latitud').value = newLatLng.lat();
        document.getElementById('longitud').value = newLatLng.lng();
        texto.textContent = `Lat: ${newLatLng.lat().toFixed(6)}, Lng: ${newLatLng.lng().toFixed(6)}`;
        
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

// Inicializar eventos del formulario y controles
function inicializarEventos() {
    // Slider de radio
    const radioSlider = document.getElementById('radioBusqueda');
    const radioValue = document.getElementById('radioValue');
    
    radioSlider.addEventListener('input', () => {
        radioValue.textContent = radioSlider.value;
    });

    // Botón de búsqueda
    document.getElementById('btnBuscar').addEventListener('click', buscarComparables);

    // Botón para eliminar todos los comparables seleccionados
    const btnEliminarTodos = document.getElementById('btnEliminarTodos');
    if (btnEliminarTodos) {
        btnEliminarTodos.addEventListener('click', limpiarPropiedadesSeleccionadas);
    }

    // Cambio en tipo de propiedad para mostrar/ocultar campos
    document.getElementById('tipoPropiedad').addEventListener('change', function() {
        const tipo = this.value.toLowerCase();
        const metrosConstruccion = document.getElementById('metrosConstruccion');
        const metrosTerreno = document.getElementById('metrosTerreno');
        const piso = document.getElementById('piso');
        
        // Lógica para habilitar/deshabilitar campos según tipo
        // (puede expandirse según necesidades)
    });

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

    // Mostrar indicador de carga
    const btnBuscar = document.getElementById('btnBuscar');
    const originalText = btnBuscar.innerHTML;
    btnBuscar.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Buscando...';
    btnBuscar.disabled = true;

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
        } else {
            throw new Error(data.message || 'Error en la búsqueda');
        }
    } catch (error) {
        console.error('Error buscando comparables:', error);
        mostrarToast('danger', `Error: ${error.message}`);
    } finally {
        // Restaurar botón
        btnBuscar.innerHTML = originalText;
        btnBuscar.disabled = false;
    }
}

// Crear marcador para propiedad comparable
function crearMarcadorComparable(propiedad) {
    // Determinar icono según la fuente
    let iconoUrl = ICONO_COMPARABLE;
    let iconoSeleccionadoUrl = ICONO_SELECCIONADO;
    
    if (propiedad.es_propify || propiedad.fuente === 'propifai') {
        iconoUrl = ICONO_PROPIFAI;
        iconoSeleccionadoUrl = ICONO_PROPIFAI_SELECCIONADO;
    }
    
    const marker = new google.maps.Marker({
        position: { lat: propiedad.lat, lng: propiedad.lng },
        map: acmMap,
        title: `${propiedad.tipo} - ${propiedad.distrito}${propiedad.es_propify ? ' (Propifai)' : ''}`,
        icon: {
            url: iconoUrl,
            scaledSize: new google.maps.Size(32, 32)
        },
    });

    // InfoWindow al hacer clic
    const fuenteTexto = propiedad.es_propify ? ' (Propifai)' : '';
    const infoWindow = new google.maps.InfoWindow({
        content: `
            <div class="map-info-window">
                <h6>${propiedad.tipo}${fuenteTexto}</h6>
                <p class="mb-1"><strong>${formatearPrecio(propiedad.precio)}</strong></p>
                <p class="mb-1">${propiedad.metros_construccion ? 'Construcción: ' + propiedad.metros_construccion + ' m²' : ''}</p>
                <p class="mb-1">${propiedad.metros_terreno ? 'Terreno: ' + propiedad.metros_terreno + ' m²' : ''}</p>
                <p class="mb-1">Distancia: ${propiedad.distancia_metros} m</p>
                <p class="mb-1 small text-muted">${propiedad.distrito}, ${propiedad.provincia}</p>
                <button class="btn btn-sm btn-primary mt-1" onclick="toggleSeleccionarPropiedad(${propiedad.id})">
                    ${propiedadesSeleccionadas.has(propiedad.id) ? 'Deseleccionar' : 'Seleccionar'}
                </button>
            </div>
        `,
    });

    marker.addListener('click', () => {
        infoWindow.open(acmMap, marker);
    });

    // Almacenar referencia
    marcadoresComparables.set(propiedad.id, {
        marker,
        data: propiedad,
        seleccionado: false,
        infoWindow,
        iconoUrl,
        iconoSeleccionadoUrl,
    });

    // Doble clic para seleccionar/deseleccionar
    marker.addListener('dblclick', () => {
        toggleSeleccionarPropiedad(propiedad.id);
    });
}

// Toggle selección de propiedad
function toggleSeleccionarPropiedad(id) {
    const marcadorInfo = marcadoresComparables.get(id);
    if (!marcadorInfo) return;

    if (marcadorInfo.seleccionado) {
        // Deseleccionar - usar icono normal según la fuente
        marcadorInfo.marker.setIcon({
            url: marcadorInfo.iconoUrl || ICONO_COMPARABLE,
            scaledSize: new google.maps.Size(32, 32)
        });
        marcadorInfo.seleccionado = false;
        propiedadesSeleccionadas.delete(id);
        
        // Cerrar infoWindow si está abierto
        marcadorInfo.infoWindow.close();
        
        // Eliminar tarjeta
        eliminarTarjetaPropiedad(id);
    } else {
        // Seleccionar - usar icono de seleccionado según la fuente
        marcadorInfo.marker.setIcon({
            url: marcadorInfo.iconoSeleccionadoUrl || ICONO_SELECCIONADO,
            scaledSize: new google.maps.Size(32, 32)
        });
        marcadorInfo.seleccionado = true;
        propiedadesSeleccionadas.set(id, marcadorInfo.data);
        
        // Crear tarjeta en panel lateral
        crearTarjetaPropiedad(marcadorInfo.data);
    }

    // Actualizar contadores y resumen
    actualizarContadores();
    actualizarResumenACM();
}

// Crear tarjeta de propiedad en panel lateral
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
    
    // Insertar en contenedor
    const container = document.getElementById('comparablesContainer');
    const sinSeleccionados = document.getElementById('sinSeleccionados');
    
    if (sinSeleccionados) {
        sinSeleccionados.style.display = 'none';
    }
    
    container.prepend(clone);
}

// Eliminar tarjeta de propiedad
function eliminarTarjetaPropiedad(id) {
    const card = document.getElementById(`propiedad-${id}`);
    if (card) {
        card.remove();
    }
    
    // Mostrar mensaje si no hay seleccionados
    if (propiedadesSeleccionadas.size === 0) {
        const sinSeleccionados = document.getElementById('sinSeleccionados');
        if (sinSeleccionados) {
            sinSeleccionados.style.display = 'block';
        }
    }
}

// Actualizar contadores
function actualizarContadores() {
    document.getElementById('contadorSeleccionados').textContent = propiedadesSeleccionadas.size;
}

// Actualizar resumen ACM
function actualizarResumenACM() {
    const propiedades = Array.from(propiedadesSeleccionadas.values());
    
    if (propiedades.length === 0) {
        // Mostrar estado vacío
        document.getElementById('resumenACM').innerHTML = `
            <div class="col-12 text-center py-4 text-muted">
                <i class="bi bi-graph-up display-6 mb-3"></i>
                <p class="mb-0">Selecciona propiedades comparables para ver el análisis</p>
            </div>
        `;
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
    const metrosConstruccion = parseFloat(document.getElementById('metrosConstruccion').value) || 0;
    const metrosTerreno = parseFloat(document.getElementById('metrosTerreno').value) || 0;
    const metros = metrosConstruccion || metrosTerreno;
    
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
    
    // Generar HTML del resumen compacto - 2 filas: métricas + 3 tarjetas
    document.getElementById('resumenACM').innerHTML = `
        <!-- Fila 1: Métricas -->
        <div class="row g-2 mb-3">
            <div class="col-md-3 col-6">
                <div class="estadistica-item p-2">
                    <div class="estadistica-valor small">${propiedades.length}</div>
                    <div class="estadistica-label small">Propiedades Analizadas</div>
                </div>
            </div>
            <div class="col-md-3 col-6">
                <div class="estadistica-item p-2">
                    <div class="estadistica-valor small">${formatearMoneda(min)}</div>
                    <div class="estadistica-label small">Precio/m² Mínimo</div>
                </div>
            </div>
            <div class="col-md-3 col-6">
                <div class="estadistica-item p-2">
                    <div class="estadistica-valor small">${formatearMoneda(promedioPonderado)}</div>
                    <div class="estadistica-label small">Precio/m² Promedio</div>
                </div>
            </div>
            <div class="col-md-3 col-6">
                <div class="estadistica-item p-2">
                    <div class="estadistica-valor small">${formatearMoneda(max)}</div>
                    <div class="estadistica-label small">Precio/m² Máximo</div>
                </div>
            </div>
        </div>
        
        <!-- Fila 2: 3 tarjetas (izquierda: precio venta sugerido, centro: estimación principal, derecha: valor realización inmediata) -->
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
                    Basado en ${metros.toFixed(0)} m² y ${propiedades.length} propiedades comparables.
                </div>
            </div>
        </div>
    `;
}

// Funciones auxiliares

// Limpiar marcadores de propiedades comparables
function limpiarMarcadoresComparables() {
    marcadoresComparables.forEach((info, id) => {
        info.marker.setMap(null);
        if (info.infoWindow) {
            info.infoWindow.close();
        }
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
    
    // Mostrar mensaje de "sin seleccionados"
    const sinSeleccionados = document.getElementById('sinSeleccionados');
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

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    // Verificar si Google Maps está cargado
    if (typeof google !== 'undefined' && google.maps) {
        initACMMap();
    } else {
        console.error('Google Maps no está cargado');
    }
});