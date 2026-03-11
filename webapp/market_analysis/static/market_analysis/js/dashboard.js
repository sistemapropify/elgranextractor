// Módulo Dashboard - JavaScript para visualización de calidad de datos

// Variables globales
let localTypeChart = null;
let propifaiTypeChart = null;
let comparisonChart = null;
let trendChart = null;

// Inicializar dashboard
function initDashboard() {
    // Cargar datos iniciales
    loadDashboardData();
    
    // Configurar eventos
    setupDashboardEvents();
}

// Cargar datos del dashboard desde la API
async function loadDashboardData() {
    try {
        showDashboardLoading(true);
        
        const response = await fetch('/market-analysis/api/dashboard-stats/');
        const data = await response.json();
        
        if (data.success) {
            updateKPIs(data.summary);
            updateQualityMetrics(data.quality_metrics);
            updatePropertyTypeCharts(data.property_type_distribution);
            updateComparisonChart(data.quality_metrics);
            updateTrendChart(data.trends);
            updateRecommendations(data);
        } else {
            showDashboardError('Error al cargar datos: ' + (data.error || 'Desconocido'));
        }
    } catch (error) {
        showDashboardError('Error de conexión: ' + error.message);
    } finally {
        showDashboardLoading(false);
    }
}

// Actualizar KPIs principales
function updateKPIs(summary) {
    document.getElementById('kpiTotalProperties').textContent = summary.total_properties.toLocaleString();
    document.getElementById('kpiLocalCount').textContent = summary.total_local.toLocaleString();
    document.getElementById('kpiPropifaiCount').textContent = summary.total_propifai.toLocaleString();
    
    // Calcular porcentaje de datos completos (aproximado)
    const totalProperties = summary.total_properties;
    const problematic = summary.problematic_total;
    const completeCount = totalProperties - problematic;
    const completePercentage = totalProperties > 0 ? Math.round((completeCount / totalProperties) * 100) : 0;
    
    document.getElementById('kpiCompleteData').textContent = completePercentage + '%';
    document.getElementById('kpiCompleteCount').textContent = completeCount.toLocaleString();
    document.getElementById('kpiTotalCount').textContent = totalProperties.toLocaleString();
    
    document.getElementById('kpiProblematic').textContent = summary.problematic_total.toLocaleString();
    document.getElementById('kpiProblematicCount').textContent = summary.problematic_total.toLocaleString();
    
    // Calcular calidad promedio
    const avgQuality = Math.max(0, 100 - (summary.problematic_total / totalProperties * 100));
    document.getElementById('kpiAvgQuality').textContent = Math.round(avgQuality) + '%';
    
    // Actualizar badge de calidad
    const qualityBadge = document.getElementById('kpiQualityBadge');
    qualityBadge.className = 'quality-badge ';
    
    if (avgQuality >= 90) {
        qualityBadge.classList.add('quality-excellent');
        qualityBadge.textContent = 'Excelente';
    } else if (avgQuality >= 70) {
        qualityBadge.classList.add('quality-good');
        qualityBadge.textContent = 'Buena';
    } else if (avgQuality >= 50) {
        qualityBadge.classList.add('quality-fair');
        qualityBadge.textContent = 'Regular';
    } else {
        qualityBadge.classList.add('quality-poor');
        qualityBadge.textContent = 'Mala';
    }
    
    // Actualizar puntuación general
    document.getElementById('overallScore').textContent = Math.round(avgQuality);
    document.getElementById('overallProgress').style.width = avgQuality + '%';
    
    const overallBadge = document.getElementById('overallBadge');
    overallBadge.className = 'quality-badge ';
    
    if (avgQuality >= 90) {
        overallBadge.classList.add('quality-excellent');
        overallBadge.textContent = 'Excelente';
        document.getElementById('overallDescription').textContent = 'Datos de alta calidad y completitud';
    } else if (avgQuality >= 70) {
        overallBadge.classList.add('quality-good');
        overallBadge.textContent = 'Buena';
        document.getElementById('overallDescription').textContent = 'Datos aceptables con algunas áreas de mejora';
    } else if (avgQuality >= 50) {
        overallBadge.classList.add('quality-fair');
        overallBadge.textContent = 'Regular';
        document.getElementById('overallDescription').textContent = 'Datos requieren atención y limpieza';
    } else {
        overallBadge.classList.add('quality-poor');
        overallBadge.textContent = 'Mala';
        document.getElementById('overallDescription').textContent = 'Datos de baja calidad, requiere acción inmediata';
    }
}

// Actualizar métricas de calidad
function updateQualityMetrics(metrics) {
    // Métricas locales
    const local = metrics.local;
    
    document.getElementById('localCoordsPct').textContent = local.coordinates.percentage + '%';
    document.getElementById('localCoordsBar').style.width = local.coordinates.percentage + '%';
    document.getElementById('localCoordsCount').textContent = local.coordinates.count.toLocaleString();
    document.getElementById('localCoordsTotal').textContent = local.coordinates.total.toLocaleString();
    
    document.getElementById('localPricePct').textContent = local.price.percentage + '%';
    document.getElementById('localPriceBar').style.width = local.price.percentage + '%';
    document.getElementById('localPriceCount').textContent = local.price.count.toLocaleString();
    document.getElementById('localPriceTotal').textContent = local.price.total.toLocaleString();
    
    document.getElementById('localAreaPct').textContent = local.area.percentage + '%';
    document.getElementById('localAreaBar').style.width = local.area.percentage + '%';
    document.getElementById('localAreaCount').textContent = local.area.count.toLocaleString();
    document.getElementById('localAreaTotal').textContent = local.area.total.toLocaleString();
    
    document.getElementById('localTypePct').textContent = local.type.percentage + '%';
    document.getElementById('localTypeBar').style.width = local.type.percentage + '%';
    document.getElementById('localTypeCount').textContent = local.type.count.toLocaleString();
    document.getElementById('localTypeTotal').textContent = local.type.total.toLocaleString();
    
    // Métricas Propifai
    const propifai = metrics.propifai;
    
    document.getElementById('propifaiCoordsPct').textContent = propifai.coordinates.percentage + '%';
    document.getElementById('propifaiCoordsBar').style.width = propifai.coordinates.percentage + '%';
    document.getElementById('propifaiCoordsCount').textContent = propifai.coordinates.count.toLocaleString();
    document.getElementById('propifaiCoordsTotal').textContent = propifai.coordinates.total.toLocaleString();
    
    document.getElementById('propifaiPricePct').textContent = propifai.price.percentage + '%';
    document.getElementById('propifaiPriceBar').style.width = propifai.price.percentage + '%';
    document.getElementById('propifaiPriceCount').textContent = propifai.price.count.toLocaleString();
    document.getElementById('propifaiPriceTotal').textContent = propifai.price.total.toLocaleString();
    
    document.getElementById('propifaiAreaPct').textContent = propifai.area.percentage + '%';
    document.getElementById('propifaiAreaBar').style.width = propifai.area.percentage + '%';
    document.getElementById('propifaiAreaCount').textContent = propifai.area.count.toLocaleString();
    document.getElementById('propifaiAreaTotal').textContent = propifai.area.total.toLocaleString();
    
    document.getElementById('propifaiTypePct').textContent = propifai.type.percentage + '%';
    document.getElementById('propifaiTypeBar').style.width = propifai.type.percentage + '%';
    document.getElementById('propifaiTypeCount').textContent = propifai.type.count.toLocaleString();
    document.getElementById('propifaiTypeTotal').textContent = propifai.type.total.toLocaleString();
}

// Actualizar gráficos de distribución por tipo
function updatePropertyTypeCharts(distribution) {
    // Destruir gráficos anteriores si existen
    if (localTypeChart) localTypeChart.destroy();
    if (propifaiTypeChart) propifaiTypeChart.destroy();
    
    // Gráfico para propiedades locales
    const localCtx = document.getElementById('localTypeChart').getContext('2d');
    const localLabels = distribution.local.map(item => item.tipo_propiedad || 'Sin tipo');
    const localData = distribution.local.map(item => item.count);
    
    localTypeChart = new Chart(localCtx, {
        type: 'doughnut',
        data: {
            labels: localLabels,
            datasets: [{
                data: localData,
                backgroundColor: [
                    '#10b981', '#3b82f6', '#8b5cf6', '#ef4444', '#f59e0b',
                    '#84cc16', '#06b6d4', '#8b5cf6', '#ec4899', '#64748b'
                ],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        boxWidth: 12,
                        font: {
                            size: 10
                        }
                    }
                },
                title: {
                    display: false
                }
            }
        }
    });
    
    // Gráfico para propiedades Propifai
    const propifaiCtx = document.getElementById('propifaiTypeChart').getContext('2d');
    const propifaiLabels = distribution.propifai.map(item => item.tipo_propiedad || 'Sin tipo');
    const propifaiData = distribution.propifai.map(item => item.count);
    
    propifaiTypeChart = new Chart(propifaiCtx, {
        type: 'doughnut',
        data: {
            labels: propifaiLabels,
            datasets: [{
                data: propifaiData,
                backgroundColor: [
                    '#10b981', '#3b82f6', '#8b5cf6', '#ef4444', '#f59e0b',
                    '#84cc16', '#06b6d4', '#8b5cf6', '#ec4899', '#64748b'
                ],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        boxWidth: 12,
                        font: {
                            size: 10
                        }
                    }
                },
                title: {
                    display: false
                }
            }
        }
    });
}

// Actualizar gráfico de comparación
function updateComparisonChart(metrics) {
    // Destruir gráfico anterior si existe
    if (comparisonChart) comparisonChart.destroy();
    
    const ctx = document.getElementById('comparisonChart').getContext('2d');
    
    const categories = ['Coordenadas', 'Precio', 'Área', 'Tipo'];
    const localData = [
        metrics.local.coordinates.percentage,
        metrics.local.price.percentage,
        metrics.local.area.percentage,
        metrics.local.type.percentage
    ];
    
    const propifaiData = [
        metrics.propifai.coordinates.percentage,
        metrics.propifai.price.percentage,
        metrics.propifai.area.percentage,
        metrics.propifai.type.percentage
    ];
    
    comparisonChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: categories,
            datasets: [
                {
                    label: 'Propiedades Locales',
                    data: localData,
                    backgroundColor: '#10b981',
                    borderColor: '#0da271',
                    borderWidth: 1
                },
                {
                    label: 'Propiedades Propifai',
                    data: propifaiData,
                    backgroundColor: '#3b82f6',
                    borderColor: '#2563eb',
                    borderWidth: 1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    title: {
                        display: true,
                        text: 'Porcentaje (%)'
                    }
                }
            },
            plugins: {
                legend: {
                    position: 'top',
                },
                title: {
                    display: true,
                    text: 'Comparación de Calidad entre Fuentes'
                }
            }
        }
    });
}

// Actualizar gráfico de tendencias
function updateTrendChart(trends) {
    // Destruir gráfico anterior si existe
    if (trendChart) trendChart.destroy();
    
    const ctx = document.getElementById('trendChart').getContext('2d');
    
    const months = trends.local.map(item => item.month);
    const localTrendData = trends.local.map(item => item.count);
    const propifaiTrendData = trends.propifai.map(item => item.count);
    
    trendChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: months,
            datasets: [
                {
                    label: 'Propiedades Locales',
                    data: localTrendData,
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                },
                {
                    label: 'Propiedades Propifai',
                    data: propifaiTrendData,
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Número de Propiedades'
                    }
                }
            },
            plugins: {
                legend: {
                    position: 'top',
                },
                title: {
                    display: true,
                    text: 'Tendencias de Ingesta (Últimos 6 meses)'
                }
            }
        }
    });
}

// Actualizar recomendaciones
function updateRecommendations(data) {
    const recommendationsList = document.getElementById('recommendationsList');
    const localMetrics = data.quality_metrics.local;
    const propifaiMetrics = data.quality_metrics.propifai;
    
    let recommendations = [];
    
    // Analizar métricas locales
    if (localMetrics.coordinates.percentage < 80) {
        recommendations.push({
            icon: 'bi-geo-alt',
            color: 'text-warning',
            text: `Mejorar coordenadas en propiedades locales (${localMetrics.coordinates.percentage}% completas)`,
            priority: 'high'
        });
    }
    
    if (localMetrics.price.percentage < 85) {
        recommendations.push({
            icon: 'bi-currency-dollar',
            color: 'text-warning',
            text: `Completar precios en propiedades locales (${localMetrics.price.percentage}% completos)`,
            priority: 'medium'
        });
    }
    
    if (propifaiMetrics.coordinates.percentage < 75) {
        recommendations.push({
            icon: 'bi-cloud',
            color: 'text-info',
            text: `Verificar coordenadas en Propifai (${propifaiMetrics.coordinates.percentage}% completas)`,
            priority: 'medium'
        });
    }
    
    // Si hay muchas propiedades problemáticas
    if (data.summary.problematic_total > data.summary.total_properties * 0.3) {
        recommendations.push({
            icon: 'bi-exclamation-triangle',
            color: 'text-danger',
            text: `Alto número de propiedades problemáticas (${data.summary.problematic_total})`,
            priority: 'high'
        });
    }
    
    // Si la calidad general es baja
    const avgQuality = Math.max(0, 100 - (data.summary.problematic_total / data.summary.total_properties * 100));
    if (avgQuality < 60) {
        recommendations.push({
            icon: 'bi-clipboard-check',
            color: 'text-danger',
            text: 'Calidad general de datos requiere atención urgente',
            priority: 'high'
        });
    }
    
    // Si no hay recomendaciones críticas
    if (recommendations.length === 0) {
        recommendations.push({
            icon: 'bi-check-circle',
            color: 'text-success',
            text: 'Datos en buen estado. Continuar con el monitoreo regular.',
            priority: 'low'
        });
    }
    
    // Ordenar por prioridad
    recommendations.sort((a, b) => {
        const priorityOrder = { high: 0, medium: 1, low: 2 };
        return priorityOrder[a.priority] - priorityOrder[b.priority];
    });
    
    // Generar HTML
    let html = '';
    recommendations.forEach(rec => {
        html += `
            <div class="list-group-item px-0 py-2 border-0">
                <div class="d-flex align-items-center">
                    <i class="bi ${rec.icon} ${rec.color} me-2"></i>
                    <div class="small">${rec.text}</div>
                </div>
            </div>
        `;
    });
    
    recommendationsList.innerHTML = html;
}

// Configurar eventos del dashboard
function setupDashboardEvents() {
    // Botón de refrescar
    document.getElementById('btnRefreshDashboard').addEventListener('click', () => {
        loadDashboardData();
    });
    
    // Botón de exportar reporte
    document.getElementById('btnExportReport').addEventListener('click', () => {
        exportDashboardReport();
    });
    
    // Tabs
    const tabTriggers = document.querySelectorAll('#sourceTabs button[data-bs-toggle="tab"]');
    tabTriggers.forEach(tab => {
        tab.addEventListener('shown.bs.tab', function(event) {
            // Redimensionar gráficos cuando se cambia de tab
            setTimeout(() => {
                if (localTypeChart) localTypeChart.resize();
                if (propifaiTypeChart) propifaiTypeChart.resize();
                if (comparisonChart) comparisonChart.resize();
                if (trendChart) trendChart.resize();
            }, 100);
        });
    });
}

// Exportar reporte del dashboard
function exportDashboardReport() {
    // En una implementación real, esto generaría un PDF o Excel
    alert('Función de exportación de reporte en desarrollo. Por ahora, usa la función de imprimir del navegador (Ctrl+P).');
    
    // Opción: abrir ventana de impresión
    // window.print();
}

// Mostrar/ocultar loading
function showDashboardLoading(show) {
    const refreshBtn = document.getElementById('btnRefreshDashboard');
    if (show) {
        refreshBtn.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i>Cargando...';
        refreshBtn.disabled = true;
    } else {
        refreshBtn.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i>Actualizar';
        refreshBtn.disabled = false;
    }
}

// Mostrar error
function showDashboardError(message) {
    console.error('Dashboard Error:', message);
    
    // Mostrar notificación
    const alertDiv = document.createElement('div');
    alertDiv.className = 'alert alert-danger alert-dismissible fade show position-fixed top-0 end-0 m-3';
    alertDiv.style.zIndex = '9999';
    alertDiv.innerHTML = `
        <strong>Error:</strong> ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(alertDiv);
    
    // Auto-eliminar después de 5 segundos
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', function() {
    // Cargar Chart.js si no está cargado
    if (typeof Chart === 'undefined') {
        console.warn('Chart.js no está cargado. Cargando...');
        loadChartJS();
    } else {
        initDashboard();
    }
});

// Cargar Chart.js dinámicamente si es necesario
function loadChartJS() {
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/chart.js';
    script.onload = initDashboard;
    script.onerror = function() {
        showDashboardError('No se pudo cargar Chart.js. Los gráficos no estarán disponibles.');
    };
    document.head.appendChild(script);
}

// Exportar para uso global
window.initDashboard = initDashboard;