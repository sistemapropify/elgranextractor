// Módulo ACM - JavaScript principal

// Variables globales del módulo
let acmMap;
let marcadorPrincipal = null;
let circuloRadio = null;
let marcadoresComparables = new Map(); // id -> {marker, data, seleccionado}
let propiedadesSeleccionadas = new Map(); // id -> data
let propiedadesEncontradas = []; // Todas las propiedades encontradas en la búsqueda

// URLs de iconos - usar iconos más distintivos para diferenciar fuentes
const ICONO_PRINCIPAL = 'https://maps.google.com/mapfiles/ms/icons/yellow-dot.png';
const ICONO_COMPARABLE = 'https://maps.google.com/mapfiles/ms/icons/blue-dot.png';
const ICONO_SELECCIONADO = 'https://maps.google.com/mapfiles/ms/icons/red-dot.png';
// Para Propifai usar iconos diferentes: morado y rosa para mejor contraste
const ICONO_PROPIFAI = 'https://maps.google.com/mapfiles/ms/icons/purple-dot.png';
const ICONO_PROPIFAI_SELECCIONADO = 'https://maps.google.com/mapfiles/ms/icons/pink-dot.png';

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

    // Cambio en tipo de propiedad para mostrar/ocultar campos
    const tipoPropiedad = document.getElementById('tipoPropiedad');
    if (tipoPropiedad) {
        tipoPropiedad.addEventListener('change', function() {
            const tipo = this.value.toLowerCase();
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
                    if (esTerreno) {
                        el.classList.add('acm-field-hidden');
                    } else {
                        el.classList.remove('acm-field-hidden');
                    }
                });
            });
            
            // El campo m² terr. siempre debe estar visible
            // (los terrenos usan área de terreno, no construcción)
        });
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

// Crear marcador para propiedad comparable
function crearMarcadorComparable(propiedad) {
    // Determinar icono según la fuente
    let iconoUrl = ICONO_COMPARABLE;
    let iconoSeleccionadoUrl = ICONO_SELECCIONADO;
    let esPropifai = propiedad.es_propify || propiedad.fuente === 'propifai';
    
    if (esPropifai) {
        iconoUrl = ICONO_PROPIFAI;
        iconoSeleccionadoUrl = ICONO_PROPIFAI_SELECCIONADO;
    }
    
    // Tamaño diferente para Propifai (más grande para destacar)
    const tamanoIcono = esPropifai ? 36 : 32;
    
    // Calcular precio por m² para mostrar en la etiqueta del marcador
    const precioM2 = propiedad.precio_m2_final || propiedad.precio_m2;
    let labelText = '';
    if (precioM2 && precioM2 > 0) {
        // Mostrar precio/m² en dólares, ej: "$850/m²"
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
        title: `${propiedad.tipo} - ${propiedad.distrito}${esPropifai ? ' (PROPIFAI)' : ' (Local)'} - $${precioM2 ? precioM2.toFixed(2) : 'N/A'}/m²`,
        icon: markerIcon,
        // Mostrar precio por m² en dólares como etiqueta del marcador (debajo del icono)
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
        iconoSeleccionadoUrl,
        esPropifai,
        tamanoIcono,
        labelText: labelText,  // Guardar texto de la etiqueta para restaurarlo al deseleccionar
    });
}

// Toggle selección de propiedad
function toggleSeleccionarPropiedad(id) {
    const marcadorInfo = marcadoresComparables.get(id);
    if (!marcadorInfo) return;

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
    
    // Botón para ver detalles
    const btnDetalle = clone.querySelector('.btn-detalle');
    btnDetalle.addEventListener('click', () => {
        mostrarDetallePropiedad(propiedad);
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
    const contador = document.getElementById('contadorSeleccionados');
    if (contador) {
        contador.textContent = propiedadesSeleccionadas.size;
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
                    Basado en ${metros.toFixed(0)} m²${esTerreno ? ' de terreno' : ' de construcción'} y ${propiedades.length} propiedades comparables.
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

// Auto-inicializar eventos cuando el DOM esté listo (independiente de Google Maps)
document.addEventListener('DOMContentLoaded', function() {
    inicializarEventos();
});