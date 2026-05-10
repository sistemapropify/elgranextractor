/* ═══════════════════════════════════════════════════════════════════════════════
   SKILLS DASHBOARD — Propifai Intelligence
   JavaScript para el dashboard principal y detail
   ═══════════════════════════════════════════════════════════════════════════════ */

(function() {
    'use strict';

    // ─── Inicialización ───
    document.addEventListener('DOMContentLoaded', function() {
        initCharts();
        initAutoRefresh();
        initTooltips();
        initSkillActions();
    });

    // ─── Charts con Chart.js ───
    function initCharts() {
        // Chart de ejecuciones por hora
        const hourlyCanvas = document.getElementById('chart-hourly');
        if (hourlyCanvas) {
            const labels = JSON.parse(hourlyCanvas.dataset.labels || '[]');
            const values = JSON.parse(hourlyCanvas.dataset.values || '[]');
            
            new Chart(hourlyCanvas, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Ejecuciones',
                        data: values,
                        backgroundColor: 'rgba(88, 166, 255, 0.3)',
                        borderColor: '#58a6ff',
                        borderWidth: 1,
                        borderRadius: 4,
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                    },
                    scales: {
                        x: {
                            grid: { color: 'rgba(48, 54, 61, 0.5)' },
                            ticks: { color: '#8b949e', font: { size: 10 } },
                        },
                        y: {
                            beginAtZero: true,
                            grid: { color: 'rgba(48, 54, 61, 0.5)' },
                            ticks: { 
                                color: '#8b949e', 
                                font: { size: 10 },
                                stepSize: 1,
                            },
                        }
                    }
                }
            });
        }

        // Donut chart: success vs error
        const donutCanvas = document.getElementById('chart-donut');
        if (donutCanvas) {
            const successRate = parseFloat(donutCanvas.dataset.successRate || '0');
            const errorRate = 100 - successRate;
            
            new Chart(donutCanvas, {
                type: 'doughnut',
                data: {
                    labels: ['Éxito', 'Error'],
                    datasets: [{
                        data: [successRate, errorRate],
                        backgroundColor: ['#3fb950', '#f85149'],
                        borderWidth: 0,
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '70%',
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                color: '#8b949e',
                                padding: 12,
                                font: { size: 11 },
                            }
                        }
                    }
                }
            });
        }

        // Cache hit rate chart
        const cacheCanvas = document.getElementById('chart-cache');
        if (cacheCanvas) {
            const hitRate = parseFloat(cacheCanvas.dataset.hitRate || '0');
            const missRate = 100 - hitRate;
            
            new Chart(cacheCanvas, {
                type: 'doughnut',
                data: {
                    labels: ['Cache Hit', 'Cache Miss'],
                    datasets: [{
                        data: [hitRate, missRate],
                        backgroundColor: ['#39d2c0', '#30363d'],
                        borderWidth: 0,
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '70%',
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                color: '#8b949e',
                                padding: 12,
                                font: { size: 11 },
                            }
                        }
                    }
                }
            });
        }
    }

    // ─── Auto-refresh cada 30 segundos ───
    function initAutoRefresh() {
        const refreshBtn = document.getElementById('sd-refresh-btn');
        if (!refreshBtn) return;

        let isRefreshing = false;
        let refreshInterval = null;

        // Función para refrescar datos via API
        function doRefresh() {
            if (isRefreshing) return;
            isRefreshing = true;
            
            const icon = refreshBtn.querySelector('i');
            if (icon) icon.className = 'bi bi-arrow-repeat sd-spin';
            
            fetch('/intelligence/skills/api/stats/')
                .then(r => {
                    if (!r.ok) throw new Error('HTTP ' + r.status);
                    return r.json();
                })
                .then(data => {
                    updateKPIs(data);
                    if (icon) icon.className = 'bi bi-arrow-repeat';
                })
                .catch(err => {
                    console.error('Error refreshing:', err);
                    if (icon) icon.className = 'bi bi-arrow-repeat';
                })
                .finally(() => {
                    isRefreshing = false;
                });
        }

        // Click manual
        refreshBtn.addEventListener('click', function(e) {
            e.preventDefault();
            doRefresh();
            showToast('Actualizando datos…', 'success');
        });

        // Auto-refresh cada 30 segundos
        refreshInterval = setInterval(doRefresh, 30000);

        // Limpiar intervalo si la página se descarga
        window.addEventListener('beforeunload', function() {
            if (refreshInterval) clearInterval(refreshInterval);
        });

        // Refrescar inmediatamente al cargar (con pequeño delay para que carguen los charts)
        setTimeout(doRefresh, 500);
    }

    // ─── Actualizar KPIs ───
    function updateKPIs(data) {
        const kpiMapping = {
            'kpi-skills': data.skills_count,
            'kpi-active': data.active_count,
            'kpi-today': data.total_executions_today,
            'kpi-total': data.total_executions_all,
            'kpi-latency': data.avg_latency_ms ? data.avg_latency_ms.toFixed(1) + ' ms' : '0 ms',
            'kpi-success-rate': data.success_rate + '%',
            'kpi-cache-rate': data.cache_hit_rate + '%',
        };

        Object.entries(kpiMapping).forEach(([id, value]) => {
            const el = document.getElementById(id);
            if (el) el.textContent = value;
        });
    }

    // ─── Tooltips ───
    function initTooltips() {
        document.querySelectorAll('[data-toggle="tooltip"]').forEach(el => {
            el.addEventListener('mouseenter', function() {
                const tooltip = document.createElement('div');
                tooltip.className = 'sd-tooltip-content';
                tooltip.textContent = this.dataset.title || '';
                this.appendChild(tooltip);
            });
            el.addEventListener('mouseleave', function() {
                const tooltip = this.querySelector('.sd-tooltip-content');
                if (tooltip) tooltip.remove();
            });
        });
    }

    // ─── Acciones de skills (toggle, clear cache) ───
    function initSkillActions() {
        // Confirmar acciones destructivas
        document.querySelectorAll('[data-confirm]').forEach(el => {
            el.addEventListener('click', function(e) {
                if (!confirm(this.dataset.confirm)) {
                    e.preventDefault();
                }
            });
        });

        // Toggle active state via AJAX
        document.querySelectorAll('.sd-toggle-skill').forEach(el => {
            el.addEventListener('click', function(e) {
                e.preventDefault();
                const url = this.href;
                const skillName = this.dataset.skill;
                
                fetch(url, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCSRFToken(),
                    },
                })
                .then(r => {
                    if (r.ok) {
                        showToast(`Skill "${skillName}" actualizada`, 'success');
                        setTimeout(() => location.reload(), 500);
                    } else {
                        showToast('Error al actualizar skill', 'error');
                    }
                })
                .catch(err => {
                    showToast('Error de conexión', 'error');
                });
            });
        });

        // Clear cache via AJAX
        document.querySelectorAll('.sd-clear-cache').forEach(el => {
            el.addEventListener('click', function(e) {
                e.preventDefault();
                const url = this.href;
                const skillName = this.dataset.skill;
                
                fetch(url, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCSRFToken(),
                    },
                })
                .then(r => {
                    if (r.ok) {
                        showToast(`Cache de "${skillName}" limpiado`, 'success');
                    } else {
                        showToast('Error al limpiar cache', 'error');
                    }
                })
                .catch(err => {
                    showToast('Error de conexión', 'error');
                });
            });
        });
    }

    // ─── Toast notifications ───
    function showToast(message, type) {
        const container = document.getElementById('sd-toast-container');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `sd-alert sd-alert-${type}`;
        toast.innerHTML = `<i class="bi ${type === 'success' ? 'bi-check-circle' : 'bi-exclamation-circle'}"></i> ${message}`;
        toast.style.marginBottom = '8px';
        toast.style.animation = 'slideIn 0.3s ease';
        
        container.appendChild(toast);
        
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transition = 'opacity 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    // ─── CSRF Token ───
    function getCSRFToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) return meta.content;
        
        const cookie = document.cookie.split(';').find(c => c.trim().startsWith('csrftoken='));
        return cookie ? cookie.split('=')[1] : '';
    }

})();
