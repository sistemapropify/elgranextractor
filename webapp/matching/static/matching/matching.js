/**
 * JavaScript para el dashboard de matching.
 * Maneja la lógica AJAX, gráficos y interacciones del usuario.
 */

class MatchingDashboard {
    constructor() {
        this.currentRequerimientoId = null;
        this.currentData = null;
        this.charts = {};
        this.currentPage = 1;
        this.pageSize = 10;
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.initCharts();
    }
    
    bindEvents() {
        // Selector de requerimiento
        $('#selectRequerimiento').on('change', (e) => this.onRequerimientoChange(e));
        
        // Botón ejecutar matching
        $('#btnEjecutarMatching').on('click', () => this.ejecutarMatching());
        
        // Filtro de score mínimo
        $('#filterScoreMin').on('change', () => this.filterResults());
        
        // Botones de guardar
        $('#btnGuardarResultados').on('click', () => this.guardarResultados());
        $('#btnGuardarBD').on('click', () => this.guardarEnBaseDatos());
        
        // Botones de exportación
        $('#btnExportPDF').on('click', () => this.exportarPDF());
        $('#btnExportExcel').on('click', () => this.exportarExcel());
        
        // Botón enviar correo
        $('#btnEnviarCorreo').on('click', () => this.enviarCorreo());
        
        // Botón limpiar
        $('#btnLimpiar').on('click', () => this.limpiarDashboard());
        
        // Cambio de gráficos
        $('[data-chart]').on('click', (e) => this.switchChart(e));
    }
    
    initCharts() {
        const ctx = document.getElementById('chartPrincipal').getContext('2d');
        
        // Gráfico de distribución (por defecto)
        this.charts.distribucion = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Compatibles', 'Descartadas por tipo', 'Descartadas por distrito', 'Descartadas por presupuesto'],
                datasets: [{
                    data: [0, 0, 0, 0],
                    backgroundColor: [
                        '#10b981', // Verde
                        '#f59e0b', // Amarillo
                        '#ef4444', // Rojo
                        '#8b5cf6'  // Violeta
                    ],
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    },
                    title: {
                        display: true,
                        text: 'Distribución de propiedades'
                    }
                }
            }
        });
        
        // Gráfico de top 10
        this.charts.top10 = null;
        
        // Gráfico de aporte por campo
        this.charts.aporte = null;
        
        // Establecer gráfico activo
        this.activeChart = 'distribucion';
    }
    
    onRequerimientoChange(e) {
        const id = $(e.target).val();
        if (!id) {
            $('#resumenRequerimiento').hide();
            return;
        }
        
        this.currentRequerimientoId = id;
        this.cargarResumenRequerimiento(id);
    }
    
    cargarResumenRequerimiento(requerimientoId) {
        $.ajax({
            url: `/api/matching/${requerimientoId}/resumen/`,
            method: 'GET',
            success: (data) => {
                this.mostrarResumenRequerimiento(data);
            },
            error: (xhr) => {
                console.error('Error cargando resumen:', xhr);
                this.mostrarErrorResumen();
            }
        });
    }
    
    mostrarResumenRequerimiento(data) {
        const req = data.requerimiento;
        const html = `
            <div class="alert alert-info">
                <div class="row">
                    <div class="col-md-3">
                        <strong><i class="bi bi-person"></i> Agente:</strong><br>
                        ${req.agente || 'No especificado'}
                    </div>
                    <div class="col-md-3">
                        <strong><i class="bi bi-house"></i> Tipo:</strong><br>
                        ${req.tipo_propiedad_display || 'No especificado'}
                    </div>
                    <div class="col-md-3">
                        <strong><i class="bi bi-geo-alt"></i> Distritos:</strong><br>
                        ${req.distritos || 'No especificado'}
                    </div>
                    <div class="col-md-3">
                        <strong><i class="bi bi-cash-coin"></i> Presupuesto:</strong><br>
                        ${req.presupuesto_display || 'No especificado'}
                    </div>
                </div>
                <div class="row mt-2">
                    <div class="col-md-3">
                        <strong><i class="bi bi-door-closed"></i> Habitaciones:</strong><br>
                        ${req.habitaciones || 'Indiferente'}
                    </div>
                    <div class="col-md-3">
                        <strong><i class="bi bi-droplet"></i> Baños:</strong><br>
                        ${req.banos || 'Indiferente'}
                    </div>
                    <div class="col-md-3">
                        <strong><i class="bi bi-arrows-fullscreen"></i> Área:</strong><br>
                        ${req.area_m2 ? req.area_m2 + ' m²' : 'Indiferente'}
                    </div>
                    <div class="col-md-3">
                        <strong><i class="bi bi-alarm"></i> Estado:</strong><br>
                        ${req.es_urgente ? '<span class="badge bg-danger">URGENTE</span>' : 'Normal'}
                    </div>
                </div>
            </div>
        `;
        
        $('#resumenRequerimiento').html(html).show();
    }
    
    mostrarErrorResumen() {
        $('#resumenRequerimiento').html(`
            <div class="alert alert-warning">
                <i class="bi bi-exclamation-triangle"></i>
                No se pudo cargar el resumen del requerimiento.
            </div>
        `).show();
    }
    
    ejecutarMatching() {
        if (!this.currentRequerimientoId) {
            this.mostrarAlerta('Por favor seleccione un requerimiento primero.', 'warning');
            return;
        }
        
        const btn = $('#btnEjecutarMatching');
        const originalText = btn.html();
        btn.prop('disabled', true).html('<i class="bi bi-hourglass-split me-2"></i> Procesando...');
        
        const limite = 100;
        const scoreMinimo = $('#filterScoreMin').val() || 0;
        
        $.ajax({
            url: `/api/matching/${this.currentRequerimientoId}/ejecutar/`,
            method: 'GET',
            data: { limite, score_minimo: scoreMinimo },
            success: (data) => {
                this.currentData = data;
                this.mostrarResultados(data);
                btn.prop('disabled', false).html(originalText);
                
                // Scroll a resultados
                $('html, body').animate({
                    scrollTop: $('#panelResultados').offset().top - 100
                }, 500);
            },
            error: (xhr) => {
                const errorMsg = xhr.responseJSON?.error || 'Error desconocido al ejecutar matching';
                this.mostrarAlerta(`Error: ${errorMsg}`, 'danger');
                btn.prop('disabled', false).html(originalText);
            }
        });
    }
    
    mostrarResultados(data) {
        // Mostrar todos los paneles
        $('#panelEstadisticas, #panelGraficos, #panelResultados, #panelDescartadas, #panelAcciones').show();
        
        // Actualizar estadísticas
        this.actualizarEstadisticas(data.estadisticas);
        
        // Actualizar gráficos
        this.actualizarGraficos(data);
        
        // Actualizar tabla de resultados
        this.actualizarTablaResultados(data.resultados);
        
        // Actualizar propiedades descartadas
        this.actualizarPropiedadesDescartadas(data.estadisticas);
    }
    
    actualizarEstadisticas(estadisticas) {
        $('#totalEvaluadas').text(estadisticas.total_evaluadas);
        $('#totalDescartadas').text(estadisticas.total_descartadas);
        $('#totalCompatibles').text(estadisticas.total_compatibles);
        $('#scorePromedio').text(estadisticas.score_promedio?.toFixed(1) || '0.0');
        
        // Actualizar propiedad top si existe
        if (estadisticas.propiedad_top) {
            const top = estadisticas.propiedad_top;
            $('#propiedadTopCard').remove();
            $('#estadisticasCards').append(`
                <div class="col-md-3" id="propiedadTopCard">
                    <div class="stat-card card text-center bg-light">
                        <div class="card-body">
                            <div class="stat-number text-primary">${top.score_total?.toFixed(1) || '0.0'}</div>
                            <div class="text-muted">Propiedad top</div>
                            <small class="text-truncate d-block">${top.propiedad?.code || 'N/A'}</small>
                        </div>
                    </div>
                </div>
            `);
        }
    }
    
    actualizarGraficos(data) {
        const estadisticas = data.estadisticas;
        
        // Actualizar gráfico de distribución
        if (this.charts.distribucion) {
            const descartadas = estadisticas.descartadas_por_campo || {};
            this.charts.distribucion.data.datasets[0].data = [
                estadisticas.total_compatibles || 0,
                descartadas.tipo_propiedad || 0,
                descartadas.distrito || 0,
                descartadas.presupuesto || 0
            ];
            this.charts.distribucion.update();
        }
        
        // Crear gráfico de top 10 si no existe
        if (!this.charts.top10 && data.resultados.length > 0) {
            this.crearChartTop10(data.resultados);
        }
        
        // Crear gráfico de aporte si no existe
        if (!this.charts.aporte && data.resultados.length > 0) {
            this.crearChartAporte(data.resultados);
        }
    }
    
    crearChartTop10(resultados) {
        const top10 = resultados.slice(0, 10);
        const ctx = document.getElementById('chartPrincipal').getContext('2d');
        
        this.charts.top10 = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: top10.map(r => r.propiedad.code),
                datasets: [{
                    label: 'Score',
                    data: top10.map(r => r.score_total),
                    backgroundColor: top10.map(r => {
                        const score = r.score_total;
                        if (score >= 75) return '#10b981';
                        if (score >= 50) return '#f59e0b';
                        return '#ef4444';
                    }),
                    borderWidth: 1
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    title: {
                        display: true,
                        text: 'Top 10 propiedades por score'
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        max: 100
                    }
                }
            }
        });
    }
    
    crearChartAporte(resultados) {
        if (resultados.length === 0) return;
        
        // Calcular aporte promedio por campo
        const campos = {};
        resultados.forEach(r => {
            if (r.score_detalle) {
                Object.entries(r.score_detalle).forEach(([campo, valor]) => {
                    if (!campos[campo]) campos[campo] = [];
                    campos[campo].push(valor);
                });
            }
        });
        
        const promedios = {};
        Object.entries(campos).forEach(([campo, valores]) => {
            promedios[campo] = valores.reduce((a, b) => a + b, 0) / valores.length;
        });
        
        const ctx = document.getElementById('chartPrincipal').getContext('2d');
        
        this.charts.aporte = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: Object.keys(promedios),
                datasets: [{
                    label: 'Aporte promedio al score',
                    data: Object.values(promedios).map(v => v * 100),
                    backgroundColor: '#8b5cf6',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    title: {
                        display: true,
                        text: 'Aporte promedio de cada campo al score total'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        title: {
                            display: true,
                            text: 'Porcentaje'
                        }
                    }
                }
            }
        });
    }
    
    switchChart(e) {
        const chartType = $(e.target).data('chart');
        if (!chartType || !this.charts[chartType]) return;
        
        // Actualizar botones activos
        $('[data-chart]').removeClass('active');
        $(e.target).addClass('active');
        
        // Ocultar gráfico actual
        this.charts[this.activeChart]?.destroy();
        
        // Mostrar nuevo gráfico
        this.activeChart = chartType;
        const canvas = document.getElementById('chartPrincipal');
        const ctx = canvas.getContext('2d');
        
        // Recrear el gráfico
        if (chartType === 'distribucion') {
            this.actualizarGraficos(this.currentData);
        } else if (chartType === 'top10' && !this.charts.top10) {
            this.crearChartTop10(this.currentData?.resultados || []);
        } else if (chartType === 'aporte' && !this.charts.aporte) {
            this.crearChartAporte(this.currentData?.resultados || []);
        } else {
            // Si el gráfico ya existe, solo mostrarlo
            this.charts[chartType] = new Chart(ctx, this.charts[chartType].config);
        }
    }
    
    actualizarTablaResultados(resultados) {
        this.currentResults = resultados;
        this.renderTablePage(1);
        this.renderPagination(resultados.length);
    }
    
    renderTablePage(page) {
        this.currentPage = page;
        const start = (page - 1) * this.pageSize;
        const end = start + this.pageSize;
        const pageResults = this.currentResults.slice(start, end);
        
        const tbody = $('#tbodyResultados');
        tbody.empty();
        
        pageResults.forEach((item, index) => {
            const propiedad = item.propiedad;
            const score = item.score_total;
            const scoreClass = score >= 75 ? 'score-high' : score >= 50 ? 'score-medium' : 'score-low';
            const globalIndex = start + index;
            
            tbody.append(`
                <tr>
                    <td class="fw-bold">${globalIndex + 1}</td>
                    <td>
                        <strong>${propiedad.code}</strong><br>
                        <small class="text-muted">${propiedad.title || 'Sin título'}</small>
                    </td>
                    <td>${propiedad.district || 'No especificado'}</td>
                    <td>${propiedad.precio_formateado || 'No especificado'}</td>
                    <td>${propiedad.tipo_propiedad || 'Propiedad'}</td>
                    <td>
                        <div class="d-flex align-items-center">
                            <div class="progress progress-score flex-grow-1 me-2">
                                <div class="progress-bar ${scoreClass}" role="progressbar" style="width: ${score}%"></div>
                            </div>
                            <span class="fw-bold">${score.toFixed(1)}</span>
                        </div>
                    </td>
                    <td>
                        <button class="btn btn-sm btn-outline-primary" onclick="matchingDashboard.verDetallePropiedad(${globalIndex})">
                            <i class="bi bi-eye"></i> Ver
                        </button>
                    </td>
                </tr>
            `);
        });
    }
    
    renderPagination(totalResults) {
        const totalPages = Math.ceil(totalResults / this.pageSize);
        const pagination = $('#paginationResultados');
        pagination.empty();
        
        if (totalPages <= 1) return;
        
        // Botón anterior
        pagination.append(`
            <li class="page-item ${this.currentPage === 1 ? 'disabled' : ''}">
                <a class="page-link" href="#" onclick="matchingDashboard.changePage(${this.currentPage - 1})">
                    <i class="bi bi-chevron-left"></i>
                </a>
            </li>
        `);
        
        // Páginas
        for (let i = 1; i <= totalPages; i++) {
            if (i === 1 || i === totalPages || (i >= this.currentPage - 2 && i <= this.currentPage + 2)) {
                pagination.append(`
                    <li class="page-item ${i === this.currentPage ? 'active' : ''}">
                        <a class="page-link" href="#" onclick="matchingDashboard.changePage(${i})">${i}</a>
                    </li>
                `);
            } else if (i === this.currentPage - 3 || i === this.currentPage + 3) {
                pagination.append('<li class="page-item disabled"><a class="page-link" href="#">...</a></li>');
            }
        }
        
        // Botón siguiente
        pagination.append(`
            <li class="page-item ${this.currentPage === totalPages ? 'disabled' : ''}">
                <a class="page-link" href="#" onclick="matchingDashboard.changePage(${this.currentPage + 1})">
                    <i class="bi bi-chevron-right"></i>
                </a>
            </li>
        `);
    }
    
    changePage(page) {
        if (page < 1 || page > Math.ceil(this.currentResults.length / this.pageSize)) return;
        this.renderTablePage(page);
    }
    
    actualizarPropiedadesDescartadas(estadisticas) {
        const descartadas = estadisticas.descartadas_por_campo || {};
        const total = estadisticas.total_descartadas || 0;
        
        $('#badgeTotalDescartadas').text(total);
        
        let html = '';
        const campos = [
            { key: 'tipo_propiedad', label: 'Tipo de propiedad', icon: 'bi-house' },
            { key: 'metodo_pago', label: 'Método de pago', icon: 'bi-credit-card' },
            { key: 'distrito', label: 'Distrito', icon: 'bi-geo-alt' },
            { key: 'presupuesto', label: 'Presupuesto', icon: 'bi-cash-coin' }
        ];
        
        campos.forEach(campo => {
            const cantidad = descartadas[campo.key] || 0;
            if (cantidad > 0) {
                html += `
                    <div class="col-md-3 mb-3">
                        <div class="card">
                            <div class="card-body text-center">
                                <i class="bi ${campo.icon} display-6 text-danger mb-2"></i>
                                <h5 class="card-title">${campo.label}</h5>
                                <div class="display-4 text-danger">${cantidad}</div>
                                <small class="text-muted">propiedades descartadas</small>
                            </div>
                        </div>
                    </div>
                `;
            }
        });
        
        $('#contenidoDescartadas').html(html || '<div class="col-12 text-center text-muted py-4"><i class="bi bi-check-circle display-4 text-success"></i><p class="mt-2">No hay propiedades descartadas</p></div>');
    }
    
    filterResults() {
        const scoreMinimo = parseFloat($('#filterScoreMin').val()) || 0;
        if (!this.currentData) return;
        
        const filtered = this.currentData.resultados.filter(r => r.score_total >= scoreMinimo);
        this.actualizarTablaResultados(filtered);
        
        // Actualizar estadísticas filtradas
        if (filtered.length !== this.currentData.resultados.length) {
            const totalCompatibles = filtered.length;
            const scorePromedio = totalCompatibles > 0 ?
                filtered.reduce((sum, r) => sum + r.score_total, 0) / totalCompatibles : 0;
            
            $('#totalCompatibles').text(totalCompatibles);
            $('#scorePromedio').text(scorePromedio.toFixed(1));
        }
    }
    
    guardarResultados() {
        if (!this.currentData || !this.currentRequerimientoId) {
            this.mostrarAlerta('No hay resultados para guardar.', 'warning');
            return;
        }
        
        const btn = $('#btnGuardarResultados');
        const originalText = btn.html();
        btn.prop('disabled', true).html('<i class="bi bi-hourglass-split me-2"></i> Guardando...');
        
        const data = {
            requerimiento_id: this.currentRequerimientoId,
            resultados: this.currentData.resultados
        };
        
        $.ajax({
            url: `/api/matching/${this.currentRequerimientoId}/guardar/`,
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(data),
            success: (response) => {
                this.mostrarAlerta(`Se guardaron ${response.total_guardados} resultados correctamente.`, 'success');
                btn.prop('disabled', false).html(originalText);
            },
            error: (xhr) => {
                const errorMsg = xhr.responseJSON?.error || 'Error desconocido';
                this.mostrarAlerta(`Error al guardar: ${errorMsg}`, 'danger');
                btn.prop('disabled', false).html(originalText);
            }
        });
    }
    
    guardarEnBaseDatos() {
        this.guardarResultados(); // Reutiliza la misma función
    }
    
    exportarPDF() {
        this.mostrarAlerta('Exportación a PDF en desarrollo.', 'info');
        // Implementación futura
    }
    
    exportarExcel() {
        this.mostrarAlerta('Exportación a Excel en desarrollo.', 'info');
        // Implementación futura
    }
    
    enviarCorreo() {
        if (!this.currentData || !this.currentRequerimientoId) {
            this.mostrarAlerta('No hay resultados para enviar.', 'warning');
            return;
        }
        
        this.mostrarAlerta('Envío de correo en desarrollo.', 'info');
        // Implementación futura
    }
    
    limpiarDashboard() {
        if (!confirm('¿Está seguro de que desea limpiar el dashboard y empezar de nuevo?')) {
            return;
        }
        
        // Limpiar selección
        $('#selectRequerimiento').val(null).trigger('change');
        
        // Ocultar paneles
        $('#panelEstadisticas, #panelGraficos, #panelResultados, #panelDescartadas, #panelAcciones').hide();
        
        // Limpiar contenido
        $('#resumenRequerimiento').empty().hide();
        $('#tbodyResultados').empty();
        $('#contenidoDescartadas').empty();
        
        // Resetear variables
        this.currentRequerimientoId = null;
        this.currentData = null;
        this.currentResults = [];
        
        // Resetear gráficos
        if (this.charts.distribucion) {
            this.charts.distribucion.data.datasets[0].data = [0, 0, 0, 0];
            this.charts.distribucion.update();
        }
        
        this.mostrarAlerta('Dashboard limpiado correctamente.', 'success');
    }
    
    verDetallePropiedad(index) {
        if (!this.currentData || !this.currentData.resultados[index]) return;
        
        const item = this.currentData.resultados[index];
        const propiedad = item.propiedad;
        const score = item.score_total;
        
        // Actualizar modal
        $('#modalPropiedadCodigo').text(propiedad.code);
        $('#modalScoreTotal').text(score.toFixed(1));
        $('#modalScoreBar').css('width', score + '%');
        
        // Determinar nivel de compatibilidad
        let nivel = 'Muy baja';
        let nivelClass = 'danger';
        if (score >= 80) {
            nivel = 'Alta';
            nivelClass = 'success';
        } else if (score >= 60) {
            nivel = 'Media';
            nivelClass = 'warning';
        } else if (score >= 40) {
            nivel = 'Baja';
            nivelClass = 'warning';
        }
        
        $('#modalNivelCompatibilidad').text(nivel).removeClass().addClass(`badge bg-${nivelClass}`);
        
        // Información de la propiedad
        $('#modalPropiedadInfo').html(`
            <div class="row">
                <div class="col-md-6">
                    <p><strong><i class="bi bi-geo-alt"></i> Dirección:</strong><br>${propiedad.real_address || 'No especificada'}</p>
                    <p><strong><i class="bi bi-building"></i> Distrito:</strong><br>${propiedad.district || 'No especificado'}</p>
                    <p><strong><i class="bi bi-arrows-fullscreen"></i> Área construida:</strong><br>${propiedad.built_area ? propiedad.built_area + ' m²' : 'No especificado'}</p>
                    <p><strong><i class="bi bi-door-closed"></i> Habitaciones:</strong><br>${propiedad.bedrooms || 'No especificado'}</p>
                </div>
                <div class="col-md-6">
                    <p><strong><i class="bi bi-droplet"></i> Baños:</strong><br>${propiedad.bathrooms || 'No especificado'}</p>
                    <p><strong><i class="bi bi-car-front"></i> Estacionamientos:</strong><br>${propiedad.garage_spaces || '0'}</p>
                    <p><strong><i class="bi bi-calendar"></i> Antigüedad:</strong><br>${propiedad.antiquity_years ? propiedad.antiquity_years + ' años' : 'No especificado'}</p>
                    <p><strong><i class="bi bi-elevator"></i> Ascensor:</strong><br>${propiedad.ascensor || 'No especificado'}</p>
                </div>
            </div>
            <div class="mt-3">
                <strong><i class="bi bi-card-text"></i> Descripción:</strong>
                <p class="text-muted">${propiedad.description || 'Sin descripción disponible.'}</p>
            </div>
        `);
        
        // Desglose del score
        let breakdownHtml = '';
        let camposCumplidos = 0;
        let camposParciales = 0;
        let camposNoCumplidos = 0;
        
        if (item.score_detalle) {
            for (const [campo, valor] of Object.entries(item.score_detalle)) {
                const porcentaje = (valor * 100).toFixed(0);
                let estado = 'parcial';
                if (valor >= 0.8) {
                    estado = 'cumplido';
                    camposCumplidos++;
                } else if (valor >= 0.5) {
                    estado = 'parcial';
                    camposParciales++;
                } else {
                    estado = 'no-cumplido';
                    camposNoCumplidos++;
                }
                
                breakdownHtml += `
                    <div class="score-breakdown mb-2">
                        <div class="d-flex justify-content-between align-items-center">
                            <span>${campo.replace('_', ' ').toUpperCase()}</span>
                            <span class="badge badge-score ${estado === 'cumplido' ? 'bg-success' : estado === 'parcial' ? 'bg-warning' : 'bg-danger'}">
                                ${porcentaje}%
                            </span>
                        </div>
                        <div class="progress" style="height: 8px;">
                            <div class="progress-bar ${estado === 'cumplido' ? 'bg-success' : estado === 'parcial' ? 'bg-warning' : 'bg-danger'}"
                                 role="progressbar" style="width: ${porcentaje}%"></div>
                        </div>
                    </div>
                `;
            }
        }
        
        $('#modalScoreBreakdown').html(breakdownHtml || '<p class="text-muted">No hay desglose disponible.</p>');
        $('#modalCamposCumplidos').text(camposCumplidos);
        $('#modalCamposParciales').text(camposParciales);
        $('#modalCamposNoCumplidos').text(camposNoCumplidos);
        
        // Mostrar modal
        const modal = new bootstrap.Modal(document.getElementById('modalDetallePropiedad'));
        modal.show();
    }
    
    mostrarAlerta(mensaje, tipo = 'info') {
        // Crear alerta temporal
        const alertId = 'alert-' + Date.now();
        const alertHtml = `
            <div id="${alertId}" class="alert alert-${tipo} alert-dismissible fade show position-fixed top-0 end-0 m-3" style="z-index: 9999; max-width: 400px;">
                <i class="bi bi-${tipo === 'success' ? 'check-circle' : tipo === 'warning' ? 'exclamation-triangle' : tipo === 'danger' ? 'x-circle' : 'info-circle'} me-2"></i>
                ${mensaje}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        
        $('body').append(alertHtml);
        
        // Auto-eliminar después de 5 segundos
        setTimeout(() => {
            $(`#${alertId}`).alert('close');
        }, 5000);
    }
}

// Inicializar dashboard cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', function() {
    window.matchingDashboard = new MatchingDashboard();
});