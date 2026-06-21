/* ACM Mobile Interactivity - Manejo de interfaz responsive */

document.addEventListener('DOMContentLoaded', function() {
    // Elementos del DOM
    const toggleParamsPanelBtn = document.getElementById('toggleParamsPanel');
    const paramsPanelContent = document.getElementById('paramsPanelContent');
    const paramsPanel = document.querySelector('.mobile-params-panel .card');
    const mobileComparablesBtn = document.getElementById('mobileComparablesBtn');
    const mobileComparablesCount = document.getElementById('mobileComparablesCount');
    const mobileComparablesBadge = document.getElementById('mobileComparablesBadge');
    const contadorSeleccionados = document.getElementById('contadorSeleccionados');
    const comparablesContainer = document.getElementById('comparablesContainer');
    const comparablesContainerMobile = document.getElementById('comparablesContainerMobile');
    const sinSeleccionadosMobile = document.getElementById('sinSeleccionadosMobile');
    
    // Estado del panel de parámetros
    let isParamsPanelCollapsed = false;
    
    // Inicializar interactividad móvil
    initMobileInteractivity();
    
    // Sincronizar contadores entre desktop y móvil
    syncComparablesCount();
    
    /**
     * Inicializar interactividad móvil
     */
    function initMobileInteractivity() {
        // Toggle del panel de parámetros en móvil
        if (toggleParamsPanelBtn) {
            toggleParamsPanelBtn.addEventListener('click', toggleParamsPanel);
            
            // Actualizar ícono inicial
            updateToggleButtonIcon();
        }
        
        // Sincronizar comparables entre desktop y móvil
        if (comparablesContainer && comparablesContainerMobile) {
            setupComparablesSync();
        }
        
        // Ajustar altura del mapa en móvil
        adjustMapHeight();
        
        // Escuchar cambios de tamaño de ventana
        window.addEventListener('resize', handleResize);
        
        // Inicializar tooltips de Bootstrap
        initBootstrapTooltips();
    }
    
    /**
     * Alternar panel de parámetros (colapsar/expandir)
     */
    function toggleParamsPanel() {
        isParamsPanelCollapsed = !isParamsPanelCollapsed;
        
        if (isParamsPanelCollapsed) {
            // Colapsar panel
            paramsPanelContent.style.display = 'none';
            paramsPanel.classList.add('params-panel-collapsed');
        } else {
            // Expandir panel
            paramsPanelContent.style.display = 'block';
            paramsPanel.classList.remove('params-panel-collapsed');
        }
        
        updateToggleButtonIcon();
        adjustMapHeight();
    }
    
    /**
     * Actualizar ícono del botón de toggle
     */
    function updateToggleButtonIcon() {
        if (!toggleParamsPanelBtn) return;
        
        const icon = toggleParamsPanelBtn.querySelector('i');
        if (icon) {
            icon.className = isParamsPanelCollapsed ? 'bi bi-chevron-up' : 'bi bi-chevron-down';
        }
        
        // Actualizar tooltip
        toggleParamsPanelBtn.title = isParamsPanelCollapsed ? 'Expandir parámetros' : 'Colapsar parámetros';
    }
    
    /**
     * Ajustar altura del mapa según el estado del panel
     */
    function adjustMapHeight() {
        const mapElement = document.getElementById('acmMap');
        if (!mapElement) return;
        
        // Solo ajustar en móvil
        if (window.innerWidth >= 992) return;
        
        // Calcular altura disponible
        const viewportHeight = window.innerHeight;
        const paramsPanelHeight = isParamsPanelCollapsed ? 
            paramsPanel.offsetHeight : 
            document.querySelector('.mobile-params-panel').offsetHeight;
        
        // Reservar espacio para botón flotante y márgenes
        const floatingButtonHeight = 80;
        const margins = 32;
        
        // Calcular altura del mapa
        const availableHeight = viewportHeight - paramsPanelHeight - floatingButtonHeight - margins;
        const minMapHeight = 200;
        const mapHeight = Math.max(minMapHeight, availableHeight);
        
        // Aplicar altura
        mapElement.style.height = mapHeight + 'px';
        
        // Redibujar mapa si está inicializado
        if (typeof google !== 'undefined' && window.acmMap) {
            setTimeout(() => {
                google.maps.event.trigger(window.acmMap, 'resize');
            }, 100);
        }
    }
    
    /**
     * Sincronizar contador de comparables
     */
    function syncComparablesCount() {
        if (!contadorSeleccionados || !mobileComparablesCount || !mobileComparablesBadge) return;
        
        // Observar cambios en el contador de desktop
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.type === 'characterData' || mutation.type === 'childList') {
                    updateMobileComparablesCount();
                }
            });
        });
        
        // Configurar observador
        observer.observe(contadorSeleccionados, {
            characterData: true,
            childList: true,
            subtree: true
        });
        
        // Actualizar contador inicial
        updateMobileComparablesCount();
    }
    
    /**
     * Actualizar contador de comparables en móvil
     */
    function updateMobileComparablesCount() {
        if (!contadorSeleccionados || !mobileComparablesCount || !mobileComparablesBadge) return;
        
        const count = parseInt(contadorSeleccionados.textContent) || 0;
        
        // Actualizar texto del botón
        mobileComparablesCount.textContent = count;
        
        // Actualizar badge
        if (count > 0) {
            mobileComparablesBadge.textContent = count;
            mobileComparablesBadge.classList.remove('bg-light', 'text-dark');
            mobileComparablesBadge.classList.add('bg-warning', 'text-dark');
        } else {
            mobileComparablesBadge.textContent = 'Ver';
            mobileComparablesBadge.classList.remove('bg-warning', 'text-dark');
            mobileComparablesBadge.classList.add('bg-light', 'text-dark');
        }
        
        // Actualizar tooltip
        mobileComparablesBtn.title = count > 0 ? 
            `Ver ${count} comparable${count !== 1 ? 's' : ''} seleccionado${count !== 1 ? 's' : ''}` : 
            'Ver comparables seleccionados';
    }
    
    /**
     * Configurar sincronización de comparables entre desktop y móvil
     */
    function setupComparablesSync() {
        // Observar cambios en el contenedor de comparables de desktop
        const desktopObserver = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.type === 'childList') {
                    syncComparablesToMobile();
                }
            });
        });
        
        // Configurar observador para el contenedor de desktop
        desktopObserver.observe(comparablesContainer, {
            childList: true,
            subtree: true
        });
        
        // Sincronizar inicialmente
        syncComparablesToMobile();
    }
    
    /**
     * Sincronizar comparables de desktop a móvil
     */
    function syncComparablesToMobile() {
        if (!comparablesContainer || !comparablesContainerMobile) return;
        
        // Limpiar contenedor móvil
        comparablesContainerMobile.innerHTML = '';
        
        // Obtener todas las tarjetas de propiedades del contenedor de desktop
        const propiedadCards = comparablesContainer.querySelectorAll('.propiedad-card');
        
        if (propiedadCards.length === 0) {
            // Mostrar estado vacío
            comparablesContainerMobile.appendChild(sinSeleccionadosMobile.cloneNode(true));
            return;
        }
        
        // Clonar y adaptar cada tarjeta para móvil
        propiedadCards.forEach((card, index) => {
            const mobileCard = createMobileComparableCard(card, index);
            comparablesContainerMobile.appendChild(mobileCard);
        });
    }
    
    /**
     * Crear tarjeta de comparable para móvil
     */
    function createMobileComparableCard(desktopCard, index) {
        // Clonar la tarjeta
        const mobileCard = desktopCard.cloneNode(true);
        mobileCard.classList.add('propiedad-card-mobile');
        mobileCard.classList.remove('propiedad-card');
        
        // Ajustar para móvil
        const row = mobileCard.querySelector('.row');
        if (row) {
            // En móvil, hacer la imagen más pequeña
            const imgCol = row.querySelector('.col-4');
            const contentCol = row.querySelector('.col-8');
            
            if (imgCol && contentCol) {
                imgCol.className = 'col-3';
                contentCol.className = 'col-9';
                
                // Reducir tamaño de imagen
                const img = imgCol.querySelector('img');
                if (img) {
                    img.style.maxHeight = '60px';
                    img.style.objectFit = 'cover';
                }
            }
        }
        
        // Ajustar botones para móvil
        const buttonsContainer = mobileCard.querySelector('.d-flex.align-items-center.gap-2');
        if (buttonsContainer) {
            // Hacer botones más grandes para touch
            const buttons = buttonsContainer.querySelectorAll('button');
            buttons.forEach(btn => {
                btn.classList.add('btn-sm');
                btn.style.padding = '0.4rem';
            });
        }
        
        // Añadir evento de clic para ver detalles
        const detailBtn = mobileCard.querySelector('.btn-detalle');
        if (detailBtn) {
            detailBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                // Disparar clic en el botón original
                const originalDetailBtn = desktopCard.querySelector('.btn-detalle');
                if (originalDetailBtn) {
                    originalDetailBtn.click();
                }
            });
        }
        
        // Añadir evento de clic para quitar
        const removeBtn = mobileCard.querySelector('.btn-quitar');
        if (removeBtn) {
            removeBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                // Disparar clic en el botón original
                const originalRemoveBtn = desktopCard.querySelector('.btn-quitar');
                if (originalRemoveBtn) {
                    originalRemoveBtn.click();
                }
            });
        }
        
        return mobileCard;
    }
    
    /**
     * Manejar redimensionamiento de ventana
     */
    function handleResize() {
        adjustMapHeight();
        
        // Mostrar/ocultar elementos según tamaño
        const isMobile = window.innerWidth < 992;
        
        if (isMobile && !isParamsPanelCollapsed) {
            // En móvil, asegurar que el panel de parámetros esté expandido inicialmente
            paramsPanelContent.style.display = 'block';
            paramsPanel.classList.remove('params-panel-collapsed');
            updateToggleButtonIcon();
        }
    }
    
    /**
     * Inicializar tooltips de Bootstrap
     */
    function initBootstrapTooltips() {
        // Inicializar tooltips si Bootstrap está disponible
        if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
            const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
            tooltipTriggerList.map(function (tooltipTriggerEl) {
                return new bootstrap.Tooltip(tooltipTriggerEl);
            });
        }
    }
    
    /**
     * Utilidad: Formatear número con separadores de miles
     */
    function formatNumber(num) {
        return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    }
    
    // ============================================================
    // Lógica: Ocultar/mostrar campos según tipo de propiedad
    // ============================================================
    const tipoPropiedadSelect = document.getElementById('tipoPropiedad');
    const fieldConstruccion = document.querySelector('.acm-field-construccion');
    const fieldPiso = document.querySelector('.acm-field-piso');
    const fieldHabitaciones = document.querySelector('.acm-field-habitaciones');
    const fieldBanos = document.querySelector('.acm-field-banos');
    
    /**
     * Actualiza la visibilidad de los campos según el tipo de propiedad seleccionado.
     * Si es "Terreno", oculta: m² const., Piso, Hab., Baños
     * Si es cualquier otro tipo (o vacío), muestra todos los campos.
     */
    function actualizarCamposPorTipo() {
        const tipo = tipoPropiedadSelect ? tipoPropiedadSelect.value.toLowerCase().trim() : '';
        const esTerreno = tipo === 'terreno';
        
        // Mostrar/ocultar cada campo
        if (fieldConstruccion) {
            fieldConstruccion.style.display = esTerreno ? 'none' : '';
        }
        if (fieldPiso) {
            fieldPiso.style.display = esTerreno ? 'none' : '';
        }
        if (fieldHabitaciones) {
            fieldHabitaciones.style.display = esTerreno ? 'none' : '';
        }
        if (fieldBanos) {
            fieldBanos.style.display = esTerreno ? 'none' : '';
        }
    }
    
    // Escuchar cambios en el selector de tipo de propiedad
    if (tipoPropiedadSelect) {
        tipoPropiedadSelect.addEventListener('change', actualizarCamposPorTipo);
        // Ejecutar al inicio para aplicar estado inicial
        actualizarCamposPorTipo();
    }
    
    // Exponer funciones útiles globalmente
    window.acmMobile = {
        toggleParamsPanel: toggleParamsPanel,
        adjustMapHeight: adjustMapHeight,
        syncComparablesToMobile: syncComparablesToMobile,
        updateMobileComparablesCount: updateMobileComparablesCount,
        actualizarCamposPorTipo: actualizarCamposPorTipo
    };
    
    console.log('✅ ACM Mobile Interactivity inicializado');
});