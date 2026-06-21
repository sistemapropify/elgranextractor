/* ═══════════════════════════════════════════════════════════════════════════════
   SKILLS METRICS — Propifai Intelligence
   JavaScript para la página de métricas globales
   ═══════════════════════════════════════════════════════════════════════════════ */

(function() {
    'use strict';

    document.addEventListener('DOMContentLoaded', function() {
        initMetricsCharts();
    });

    function initMetricsCharts() {
        // ─── Timeline chart (7 días) ───
        const timelineCanvas = document.getElementById('chart-timeline');
        if (timelineCanvas) {
            const labels = JSON.parse(timelineCanvas.dataset.labels || '[]');
            const values = JSON.parse(timelineCanvas.dataset.values || '[]');
            
            new Chart(timelineCanvas, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Ejecuciones',
                        data: values,
                        borderColor: '#58a6ff',
                        backgroundColor: 'rgba(88, 166, 255, 0.1)',
                        fill: true,
                        tension: 0.4,
                        pointRadius: 4,
                        pointBackgroundColor: '#58a6ff',
                        pointBorderColor: '#0d1117',
                        pointBorderWidth: 2,
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
                    },
                    interaction: {
                        intersect: false,
                        mode: 'index',
                    },
                }
            });
        }

        // ─── Ejecuciones por skill (bar chart) ───
        const skillBarCanvas = document.getElementById('chart-skill-bar');
        if (skillBarCanvas) {
            const labels = JSON.parse(skillBarCanvas.dataset.labels || '[]');
            const values = JSON.parse(skillBarCanvas.dataset.values || '[]');
            const colors = ['#58a6ff', '#3fb950', '#bc8cff', '#f0883e', '#39d2c0', '#d29922', '#f85149'];
            
            new Chart(skillBarCanvas, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Ejecuciones',
                        data: values,
                        backgroundColor: values.map((_, i) => colors[i % colors.length] + '33'),
                        borderColor: values.map((_, i) => colors[i % colors.length]),
                        borderWidth: 1,
                        borderRadius: 4,
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    indexAxis: 'y',
                    plugins: {
                        legend: { display: false },
                    },
                    scales: {
                        x: {
                            beginAtZero: true,
                            grid: { color: 'rgba(48, 54, 61, 0.5)' },
                            ticks: { color: '#8b949e', font: { size: 10 } },
                        },
                        y: {
                            grid: { display: false },
                            ticks: { color: '#8b949e', font: { size: 10 } },
                        }
                    }
                }
            });
        }

        // ─── Latencia por skill ───
        const latencyCanvas = document.getElementById('chart-latency');
        if (latencyCanvas) {
            const labels = JSON.parse(latencyCanvas.dataset.labels || '[]');
            const values = JSON.parse(latencyCanvas.dataset.values || '[]');
            
            new Chart(latencyCanvas, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Latencia (ms)',
                        data: values,
                        backgroundColor: 'rgba(57, 210, 192, 0.3)',
                        borderColor: '#39d2c0',
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
                            ticks: { color: '#8b949e', font: { size: 10 } },
                        }
                    }
                }
            });
        }

        // ─── Success rate por categoría ───
        const categoryCanvas = document.getElementById('chart-category');
        if (categoryCanvas) {
            const labels = JSON.parse(categoryCanvas.dataset.labels || '[]');
            const values = JSON.parse(categoryCanvas.dataset.values || '[]');
            const colors = ['#58a6ff', '#3fb950', '#bc8cff', '#f0883e', '#39d2c0'];
            
            new Chart(categoryCanvas, {
                type: 'doughnut',
                data: {
                    labels: labels,
                    datasets: [{
                        data: values,
                        backgroundColor: colors.slice(0, labels.length),
                        borderWidth: 0,
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '60%',
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

})();
