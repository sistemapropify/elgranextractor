/**
 * Dashboard de Análisis Temporal - JavaScript
 * Maneja gráficos, filtros AJAX, procesamiento asíncrono y visualización de datos.
 */

document.addEventListener('DOMContentLoaded', function() {
    // Variables globales
    let charts = {};
    let currentData = null;
    const apiUrl = '/requerimientos/api/analisis-temporal/';
    const progressApiUrl = '/requerimientos/api/analisis-progreso/';
    
    // Variables para procesamiento asíncrono
    let currentTaskId = null;
    let progressInterval = null;
    let backgroundMode = false;
    let taskStartTime = null;
    
    // Inicializar
    initDatePickers();
    loadDashboardData();
    setupEventListeners();
    
    // ─────────────────────────────────────────────
    //  INICIALIZACIÓN
    // ─────────────────────────────────────────────
    
    function initDatePickers() {
        if (typeof flatpickr !== 'undefined') {
            flatpickr("#fecha_inicio", { dateFormat: "Y-m-d", locale: "es" });
            flatpickr("#fecha_fin", { dateFormat: "Y-m-d", locale: "es" });
        }
    }
    
    function setupEventListeners() {
        const filtersForm = document.getElementById('filtersForm');
        if (filtersForm) {
            filtersForm.addEventListener('submit', function(e) {
                e.preventDefault();
                loadDashboardData();
            });
        }
        
        const btnReset = document.getElementById('btnResetFilters');
        if (btnReset) {
            btnReset.addEventListener('click', function() {
                document.getElementById('fecha_inicio').value = '';
                document.getElementById('fecha_fin').value = '';
                document.getElementById('condicion').value = '';
                document.getElementById('tipo_propiedad').value = '';
                document.getElementById('distrito').value = '';
                loadDashboardData();
            });
        }
        
        const btnLast30 = document.getElementById('btnLast30Days');
        if (btnLast30) {
            btnLast30.addEventListener('click', function() {
                const end = new Date();
                const start = new Date();
                start.setDate(start.getDate() - 30);
                document.getElementById('fecha_inicio').value = formatDate(start);
                document.getElementById('fecha_fin').value = formatDate(end);
                loadDashboardData();
            });
        }
        
        document.getElementById('btnExportExcel')?.addEventListener('click', exportToExcel);
        document.getElementById('btnExportPDF')?.addEventListener('click', exportToPDF);
        
        document.querySelectorAll('[data-chart-type]').forEach(btn => {
            btn.addEventListener('click', function() {
                const chartType = this.getAttribute('data-chart-type');
                document.querySelectorAll('[data-chart-type]').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                if (charts.tendencia && currentData) {
                    updateChartType(charts.tendencia, chartType);
                }
            });
        });
        
        document.getElementById('btnCancelProcessing')?.addEventListener('click', cancelProcessing);
        document.getElementById('btnContinueBackground')?.addEventListener('click', continueInBackground);
    }
    
    // ─────────────────────────────────────────────
    //  CARGA DE DATOS VÍA AJAX (SÍNCRONO/ASÍNCRONO)
    // ─────────────────────────────────────────────
    
    function loadDashboardData() {
        if (progressInterval) {
            clearInterval(progressInterval);
            progressInterval = null;
        }
        
        currentTaskId = null;
        backgroundMode = false;
        taskStartTime = new Date();
        
        showProgressOverlay(true);
        updateProgress(0, 'Iniciando análisis temporal...', 'Preparando datos');
        
        const params = new URLSearchParams();
        const fechaInicio = document.getElementById('fecha_inicio').value;
        const fechaFin = document.getElementById('fecha_fin').value;
        const condicion = document.getElementById('condicion').value;
        const tipoPropiedad = document.getElementById('tipo_propiedad').value;
        const distrito = document.getElementById('distrito').value;
        
        if (fechaInicio) params.append('fecha_inicio', fechaInicio);
        if (fechaFin) params.append('fecha_fin', fechaFin);
        if (condicion) params.append('condicion', condicion);
        if (tipoPropiedad) params.append('tipo_propiedad', tipoPropiedad);
        if (distrito) params.append('distrito', distrito);
        
        const useAsync = shouldUseAsyncMode(fechaInicio, fechaFin);
        
        if (useAsync) {
            params.append('async', 'true');
            startAsyncProcessing(params);
        } else {
            params.append('async', 'false');
            startSyncProcessing(params);
        }
    }
    
    function shouldUseAsyncMode(fechaInicio, fechaFin) {
        if (!fechaInicio || !fechaFin) return true;
        const start = new Date(fechaInicio);
        const end = new Date(fechaFin);
        const monthsDiff = (end.getFullYear() - start.getFullYear()) * 12 + (end.getMonth() - start.getMonth());
        return monthsDiff > 6;
    }
    
    function startSyncProcessing(params) {
        updateProgress(10, 'Obteniendo datos de la base de datos...', 'Consultando requerimientos');
        
        fetch(`${apiUrl}?${params.toString()}`)
            .then(response => {
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    updateProgress(80, 'Procesando datos y generando visualizaciones...', 'Renderizando gráficos');
                    currentData = data;
                    updateDashboard(data);
                    updateProgress(100, 'Análisis completado exitosamente', 'Finalizando');
                    setTimeout(() => showProgressOverlay(false), 1000);
                } else if (data.task_id) {
                    currentTaskId = data.task_id;
                    startProgressPolling();
                } else {
                    throw new Error('API returned unsuccessful response');
                }
            })
            .catch(error => {
                console.error('Error loading dashboard data:', error);
                showError('No se pudieron cargar los datos. Por favor, intente nuevamente.');
                showProgressOverlay(false);
            });
    }
    
    function startAsyncProcessing(params) {
        updateProgress(5, 'Iniciando procesamiento asíncrono...', 'Creando tarea en segundo plano');
        
        fetch(`${apiUrl}?${params.toString()}`)
            .then(response => {
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                return response.json();
            })
            .then(data => {
                if (data.task_id) {
                    currentTaskId = data.task_id;
                    updateProgress(15, 'Tarea creada exitosamente', `ID: ${data.task_id.substring(0, 8)}...`);
                    startProgressPolling();
                } else if (data.success) {
                    updateProgress(80, 'Procesando datos...', 'Renderizando gráficos');
                    currentData = data;
                    updateDashboard(data);
                    updateProgress(100, 'Análisis completado', 'Finalizando');
                    setTimeout(() => showProgressOverlay(false), 1000);
                } else {
                    throw new Error('API returned unexpected response');
                }
            })
            .catch(error => {
                console.error('Error starting async processing:', error);
                showError('No se pudo iniciar el procesamiento. Por favor, intente nuevamente.');
                showProgressOverlay(false);
            });
    }
    
    function startProgressPolling() {
        if (!currentTaskId) return;
        
        updateProgress(20, 'Procesando en segundo plano...', 'Puede continuar navegando');
        
        progressInterval = setInterval(() => checkTaskProgress(), 2000);
        checkTaskProgress();
    }
    
    function checkTaskProgress() {
        if (!currentTaskId) {
            clearInterval(progressInterval);
            return;
        }
        
        fetch(`${progressApiUrl}${currentTaskId}/`)
            .then(response => {
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                return response.json();
            })
            .then(data => {
                if (data.status === 'SUCCESS') {
                    clearInterval(progressInterval);
                    updateProgress(100, 'Análisis completado exitosamente', 'Cargando resultados...');
                    
                    if (data.result) {
                        currentData = data.result;
                        updateDashboard(data.result);
                    }
                    
                    setTimeout(() => {
                        if (!backgroundMode) showProgressOverlay(false);
                    }, 1500);
                    
                } else if (data.status === 'PROGRESS') {
                    const progress = data.progress || 0;
                    const currentStep = data.current_step || 'Procesando';
                    const message = data.message || 'Analizando datos...';
                    
                    updateProgress(progress, message, currentStep);
                    updateEstimatedTime(progress);
                    
                } else if (data.status === 'FAILURE') {
                    clearInterval(progressInterval);
                    showError(`Error en el procesamiento: ${data.error || 'Error desconocido'}`);
                    showProgressOverlay(false);
                    
                } else if (data.status === 'PENDING') {
                    updateProgress(25, 'Tarea en cola de procesamiento...', 'Esperando recursos');
                }
            })
            .catch(error => console.error('Error checking task progress:', error));
    }
    
    function updateProgress(percentage, message, step) {
        const progressBar = document.getElementById('progressBar');
        const progressText = document.getElementById('progressText');
        const progressMessage = document.getElementById('progressMessage');
        const currentStep = document.getElementById('currentStep');
        
        if (progressBar) {
            progressBar.style.width = `${percentage}%`;
            progressBar.setAttribute('aria-valuenow', percentage);
        }
        if (progressText) progressText.textContent = `${percentage}%`;
        if (progressMessage) progressMessage.textContent = message;
        if (currentStep) currentStep.textContent = step;
    }
    
    function updateEstimatedTime(progress) {
        if (!taskStartTime || progress <= 0) return;
        
        const elapsed = (new Date() - taskStartTime) / 1000;
        const estimatedTotal = (elapsed / progress) * 100;
        const remaining = estimatedTotal - elapsed;
        
        const estimatedTimeElem = document.getElementById('estimatedTime');
        if (estimatedTimeElem) {
            if (remaining > 60) {
                estimatedTimeElem.textContent = `Tiempo restante: ${Math.round(remaining / 60)} minutos`;
            } else if (remaining > 0) {
                estimatedTimeElem.textContent = `Tiempo restante: ${Math.round(remaining)} segundos`;
            } else {
                estimatedTimeElem.textContent = 'Finalizando...';
            }
        }
    }
    
    function cancelProcessing() {
        if (confirm('¿Está seguro de cancelar el procesamiento? Los datos procesados hasta ahora se perderán.')) {
            if (progressInterval) clearInterval(progressInterval);
            showProgressOverlay(false);
            currentTaskId = null;
        }
    }
    
    function continueInBackground() {
        backgroundMode = true;
        showProgressOverlay(false);
        showNotification('El análisis continúa en segundo plano. Se le notificará cuando esté listo.', 'info');
        
        if (currentTaskId && !progressInterval) {
            progressInterval = setInterval(() => checkTaskProgress(), 3000);
        }
    }
    
    function showProgressOverlay(show) {
        const overlay = document.getElementById('loadingOverlay');
        if (overlay) overlay.style.display = show ? 'flex' : 'none';
        
        if (!show && backgroundMode && currentTaskId) showMiniProgressIndicator();
    }
    
    function showMiniProgressIndicator() {
        let miniIndicator = document.getElementById('miniProgressIndicator');
        if (!miniIndicator) {
            miniIndicator = document.createElement('div');
            miniIndicator.id = 'miniProgressIndicator';
            miniIndicator.className = 'mini-progress-indicator';
            miniIndicator.innerHTML = `
                <div class="d-flex align-items-center">
                    <div class="spinner-border spinner-border-sm text-primary me-2" role="status"></div>
                    <span class="small">Procesando análisis...</span>
                    <button class="btn btn-sm btn-link ms-2" id="btnShowProgress">Ver progreso</button>
                </div>
            `;
            document.body.appendChild(miniIndicator);
            
            document.getElementById('btnShowProgress')?.addEventListener('click', () => {
                showProgressOverlay(true);
                backgroundMode = false;
                miniIndicator.remove();
            });
        }
    }
    
    // ─────────────────────────────────────────────
    //  ACTUALIZACIÓN DE LA INTERFAZ
    // ─────────────────────────────────────────────
    
    function updateDashboard(data) {
        updateKPIs(data);
        updateInsights(data.insights);
        renderCharts(data);
        renderHeatmap(data.distritos_mes);
        renderTiposPropiedadTable(data.tipos_mes);
        
        if (backgroundMode) {
            showNotification('¡Análisis temporal completado! Los resultados están listos.', 'success');
            backgroundMode = false;
            const miniIndicator = document.getElementById('miniProgressIndicator');
            if (miniIndicator) miniIndicator.remove();
        }
    }
    
    function updateKPIs(data) {
        const total = data.metricas.totales.reduce((a, b) => a + b, 0);
        const crecimiento = data.metricas.crecimiento?.slice(-1)[0] || 0;
        const tendencia = data.metricas.tendencia;
        
        document.getElementById('kpiTotal').textContent = total.toLocaleString();
        document.getElementById('kpiTotalChange').textContent = `${tendencia} ${total > 0 ? 'vs período anterior' : ''}`;
        
        const crecimientoElem = document.getElementById('kpiCrecimiento');
        const cambioElem = document.getElementById('kpiTendencia');
        if (crecimiento) {
            crecimientoElem.textContent = `${crecimiento > 0 ? '+' : ''}${crecimiento.toFixed(1)}%`;
            crecimientoElem.className = `kpi-value ${crecimiento > 0 ? 'change-positive' : crecimiento < 0 ? 'change-negative' : 'change-neutral'}`;
            cambioElem.textContent = tendencia;
        } else {
            crecimientoElem.textContent = '--';
            cambioElem.textContent = 'Sin datos';
        }
        
        if (data.presupuesto_mes.promedio.length > 0) {
            const avg = data.presupuesto_mes.promedio.slice(-1)[0];
            document.getElementById('kpiPresupuesto').textContent = `$${Math.round(avg).toLocaleString()}`;
        }
        
        if (data.distritos_mes.distritos.length > 0) {
            const distritos = data.distritos_mes.distritos;
            const datos = data.distritos_mes.data;
            let maxDistrito = '';
            let maxTotal = 0;
            
            distritos.forEach(distrito => {
                const total = Object.values(datos[distrito]).reduce((a, b) => a + b, 0);
                if (total > maxTotal) {
                    maxTotal = total;
                    maxDistrito = distrito;
                }
            });
            
            if (maxDistrito) {
                document.getElementById('kpiDistrito').textContent = maxDistrito;
            }
        }
    }
    
    function updateInsights(insights) {
        const container = document.getElementById('insightsContainer');
        if (!insights || insights.length === 0) {
            container.innerHTML = '<p class="text-muted text-center">No hay insights disponibles para los filtros seleccionados.</p>';
            return;
        }
        
        let html = '';
        insights.forEach(insight => {
            html += `
                <div class="insight-card ${insight.tipo} p-3 mb-2 rounded">
                    <div class="d-flex align-items-start">
                        <div class="fs-4 me-2">${insight.icono}</div>
                        <div>
                            <h6 class="mb-1">${insight.titulo}</h6>
                            <p class="mb-0 small text-muted">${insight.descripcion}</p>
                        </div>
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html;
    }
    
    // ─────────────────────────────────────────────
    //  RENDERIZADO DE GRÁFICOS
    // ─────────────────────────────────────────────
    
    function renderCharts(data) {
        renderTendenciaChart(data);
        renderDistribucionTipoChart(data);
        renderPresupuestoChart(data);
        renderCaracteristicasChart(data);
    }
    
    function renderTendenciaChart(data) {
        const ctx = document.getElementById('chartTendenciaMensual').getContext('2d');
        const meses = data.datos_mes.map(item => new Date(item.mes).toLocaleDateString('es-ES', { month: 'short', year: 'numeric' }));
        const totales = data.datos_mes.map(item => item.total);
        const compra = data.datos_mes.map(item => item.compra);
        const alquiler = data.datos_mes.map(item => item.alquiler);
        
        if (charts.tendencia) charts.tendencia.destroy();
        
        charts.tendencia = new Chart(ctx, {
            type: 'line',
            data: {
                labels: meses,
                datasets: [
                    {
                        label: 'Total Requerimientos',
                        data: totales,
                        borderColor: '#2c3e50',
                        backgroundColor: 'rgba(44, 62, 80, 0.1)',
                        borderWidth: 3,
                        fill: true,
                        tension: 0.3
                    },
                    {
                        label: 'Compra',
                        data: compra,
                        borderColor: '#27ae60',
                        backgroundColor: 'rgba(39, 174, 96, 0.1)',
                        borderWidth: 2,
                        borderDash: [5, 5],
                        tension: 0.3
                    },
                    {
                        label: 'Alquiler',
                        data: alquiler,
                        borderColor: '#e74c3c',
                        backgroundColor: 'rgba(231, 76, 60, 0.1)',
                        borderWidth: 2,
                        borderDash: [5, 5],
                        tension: 0.3
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Cantidad de Requerimientos'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Mes'
                        }
                    }
                }
            }
        });
    }
    
    function renderDistribucionTipoChart(data) {
        const ctx = document.getElementById('chartDistribucionTipo').getContext('2d');
        
        // Calcular totales por tipo para el último mes
        const ultimoMes = data.tipos_mes.meses.length - 1;
        const tipos = data.tipos_mes.tipos;
        const valores = tipos.map(tipo => data.tipos_mes.data[tipo][ultimoMes] || 0);
        
        // Colores
        const backgroundColors = [
            '#3498db', '#2ecc71', '#e74c3c', '#f39c12', '#9b59b6', '#1abc9c'
        ];
        
        if (charts.distribucion) charts.distribucion.destroy();
        
        charts.distribucion = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: tipos.map(t => {
                    const labels = {
                        'departamento': 'Departamento',
                        'casa': 'Casa',
                        'terreno': 'Terreno',
                        'oficina': 'Oficina',
                        'local_comercial': 'Local Comercial'
                    };
                    return labels[t] || t;
                }),
                datasets: [{
                    data: valores,
                    backgroundColor: backgroundColors,
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right',
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const label = context.label || '';
                                const value = context.raw;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = total > 0 ? Math.round((value / total) * 100) : 0;
                                return `${label}: ${value} (${percentage}%)`;
                            }
                        }
                    }
                }
            }
        });
    }
    
    function renderPresupuestoChart(data) {
        const ctx = document.getElementById('chartPresupuesto').getContext('2d');
        const meses = data.presupuesto_mes.meses.map(m => {
            const [year, month] = m.split('-');
            return new Date(year, month-1).toLocaleDateString('es-ES', { month: 'short', year: 'numeric' });
        });
        
        if (charts.presupuesto) charts.presupuesto.destroy();
        
        charts.presupuesto = new Chart(ctx, {
            type: 'line',
            data: {
                labels: meses,
                datasets: [
                    {
                        label: 'Promedio',
                        data: data.presupuesto_mes.promedio,
                        borderColor: '#3498db',
                        backgroundColor: 'rgba(52, 152, 219, 0.1)',
                        borderWidth: 3,
                        fill: true,
                        tension: 0.3
                    },
                    {
                        label: 'Mediano',
                        data: data.presupuesto_mes.mediano,
                        borderColor: '#2ecc71',
                        backgroundColor: 'rgba(46, 204, 113, 0.1)',
                        borderWidth: 2,
                        borderDash: [5, 5],
                        tension: 0.3
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                    }
                },
                scales: {
                    y: {
                        beginAtZero: false,
                        title: {
                            display: true,
                            text: 'Presupuesto (USD)'
                        },
                        ticks: {
                            callback: function(value) {
                                return '$' + value.toLocaleString();
                            }
                        }
                    }
                }
            }
        });
    }
    
    function renderCaracteristicasChart(data) {
        const ctx = document.getElementById('chartCaracteristicas').getContext('2d');
        const meses = data.caracteristicas_mes.meses.map(m => {
            const [year, month] = m.split('-');
            return new Date(year, month-1).toLocaleDateString('es-ES', { month: 'short' });
        });
        
        const caracteristicas = data.caracteristicas_mes.caracteristicas;
        const datasets = caracteristicas.map((car, index) => {
            const colors = ['#3498db', '#2ecc71', '#e74c3c', '#f39c12', '#9b59b6'];
            const labels = {
                'cochera_si': 'Cochera',
                'ascensor_si': 'Ascensor',
                'amueblado_si': 'Amueblado',
                'habitaciones_3+': '3+ Habitaciones',
                'banos_2+': '2+ Baños'
            };
            
            return {
                label: labels[car] || car,
                data: data.caracteristicas_mes.data[car],
                borderColor: colors[index % colors.length],
                backgroundColor: 'transparent',
                borderWidth: 2,
                tension: 0.3
            };
        });
        
        if (charts.caracteristicas) charts.caracteristicas.destroy();
        
        charts.caracteristicas = new Chart(ctx, {
            type: 'line',
            data: {
                labels: meses,
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Cantidad de Requerimientos'
                        }
                    }
                }
            }
        });
    }
    
    function updateChartType(chart, newType) {
        chart.config.type = newType;
        chart.update();
    }
    
    // ─────────────────────────────────────────────
    //  RENDERIZADO DE TABLAS
    // ─────────────────────────────────────────────
    
    function renderHeatmap(distritosData) {
        const table = document.getElementById('heatmapTable');
        const thead = table.querySelector('thead');
        const tbody = table.querySelector('tbody');
        
        // Limpiar tabla
        thead.innerHTML = '<tr><th>Distrito</th></tr>';
        tbody.innerHTML = '';
        
        if (!distritosData.distritos.length || !distritosData.meses.length) {
            tbody.innerHTML = '<tr><td colspan="100%" class="text-center py-4 text-muted">No hay datos para mostrar</td></tr>';
            return;
        }
        
        // Crear encabezados de meses
        distritosData.meses.forEach(mes => {
            const th = document.createElement('th');
            th.textContent = mes;
            thead.querySelector('tr').appendChild(th);
        });
        
        // Crear filas de distritos
        distritosData.distritos.forEach(distrito => {
            const tr = document.createElement('tr');
            const tdDistrito = document.createElement('td');
            tdDistrito.textContent = distrito;
            tdDistrito.style.fontWeight = '600';
            tr.appendChild(tdDistrito);
            
            // Crear celdas para cada mes
            distritosData.meses.forEach(mes => {
                const td = document.createElement('td');
                const valor = distritosData.data[distrito][mes] || 0;
                td.textContent = valor;
                td.className = 'heatmap-cell';
                
                // Asignar clase de color basada en el valor
                if (valor === 0) {
                    td.classList.add('heatmap-0');
                } else if (valor <= 5) {
                    td.classList.add('heatmap-1');
                } else if (valor <= 10) {
                    td.classList.add('heatmap-2');
                } else if (valor <= 20) {
                    td.classList.add('heatmap-3');
                } else if (valor <= 50) {
                    td.classList.add('heatmap-4');
                } else {
                    td.classList.add('heatmap-5');
                }
                
                tr.appendChild(td);
            });
            
            tbody.appendChild(tr);
        });
    }
    
    function renderTiposPropiedadTable(tiposData) {
        const tbody = document.querySelector('#tablaTiposPropiedad tbody');
        tbody.innerHTML = '';
        
        if (!tiposData.meses.length) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4 text-muted">No hay datos para mostrar</td></tr>';
            return;
        }
        
        // Crear filas para cada mes
        tiposData.meses.forEach((mes, index) => {
            const tr = document.createElement('tr');
            
            // Celda de mes
            const tdMes = document.createElement('td');
            tdMes.textContent = mes;
            tdMes.style.fontWeight = '600';
            tr.appendChild(tdMes);
            
            // Calcular totales por tipo para este mes
            let totalMes = 0;
            tiposData.tipos.forEach(tipo => {
                const td = document.createElement('td');
                const valor = tiposData.data[tipo][index] || 0;
                td.textContent = valor;
                totalMes += valor;
                tr.appendChild(td);
            });
            
            // Celda de total
            const tdTotal = document.createElement('td');
            tdTotal.textContent = totalMes;
            tdTotal.style.fontWeight = '600';
            tdTotal.style.backgroundColor = '#f8f9fa';
            tr.appendChild(tdTotal);
            
            tbody.appendChild(tr);
        });
    }
    
    // ─────────────────────────────────────────────
    //  FUNCIONES DE UTILIDAD
    // ─────────────────────────────────────────────
    
    function showNotification(message, type = 'info') {
        // Implementación simple de notificación
        const alertClass = type === 'success' ? 'alert-success' :
                          type === 'error' ? 'alert-danger' : 'alert-info';
        
        const notification = document.createElement('div');
        notification.className = `alert ${alertClass} alert-dismissible fade show position-fixed`;
        notification.style.cssText = 'top: 20px; right: 20px; z-index: 10000; min-width: 300px;';
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(notification);
        
        // Auto-remover después de 5 segundos
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 5000);
    }
    
    function showError(message) {
        showNotification('Error: ' + message, 'error');
    }
    
    function formatDate(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }
    
    function exportToExcel() {
        // En una implementación real, redirigir a una vista de exportación
        const params = new URLSearchParams(getCurrentFilters());
        window.location.href = '/requerimientos/exportar-excel/?' + params.toString();
    }
    
    function exportToPDF() {
        const params = new URLSearchParams(getCurrentFilters());
        window.location.href = '/requerimientos/exportar-pdf/?' + params.toString();
    }
    
    function getCurrentFilters() {
        return {
            fecha_inicio: document.getElementById('fecha_inicio').value,
            fecha_fin: document.getElementById('fecha_fin').value,
            condicion: document.getElementById('condicion').value,
            tipo_propiedad: document.getElementById('tipo_propiedad').value,
            distrito: document.getElementById('distrito').value
        };
    }
    
    // Estilos para el mini indicador de progreso
    const style = document.createElement('style');
    style.textContent = `
        .mini-progress-indicator {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: white;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            padding: 10px 15px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            z-index: 9998;
        }
    `;
    document.head.appendChild(style);
});
