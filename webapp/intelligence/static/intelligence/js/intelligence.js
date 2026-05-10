/* Intelligence Layer - Main JavaScript Module */

(function() {
    'use strict';

    // Inicializar cuando el DOM esté listo
    document.addEventListener('DOMContentLoaded', function() {
        console.log('Intelligence Layer loaded');
        initializeNavigation();
        initializeTooltips();
    });

    /**
     * Inicializar navegación activa
     */
    function initializeNavigation() {
        const navItems = document.querySelectorAll('.nav-item');
        const currentPath = window.location.pathname;

        navItems.forEach(item => {
            const href = item.getAttribute('href');
            if (href && currentPath.includes(href)) {
                item.classList.add('active');
            }
        });
    }

    /**
     * Inicializar tooltips (si existen)
     */
    function initializeTooltips() {
        const tooltips = document.querySelectorAll('[data-tooltip]');
        tooltips.forEach(tooltip => {
            tooltip.addEventListener('mouseenter', function() {
                // Tooltips basados en CSS via ::after
            });
        });
    }

    /**
     * Utilidad para hacer llamadas AJAX
     */
    window.Intelligence = {
        /**
         * Realizar una llamada AJAX segura
         */
        ajax: function(url, options = {}) {
            const method = options.method || 'GET';
            const headers = options.headers || {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            };

            // Agregar CSRF token si existe
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
            if (csrfToken) {
                headers['X-CSRFToken'] = csrfToken;
            }

            const config = {
                method: method,
                headers: headers,
                credentials: 'same-origin'
            };

            if (options.data && method !== 'GET') {
                config.body = JSON.stringify(options.data);
            }

            return fetch(url, config)
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .catch(error => {
                    console.error('AJAX Error:', error);
                    throw error;
                });
        },

        /**
         * Mostrar una notificación
         */
        notify: function(message, type = 'info') {
            const alertDiv = document.createElement('div');
            alertDiv.className = `sd-alert sd-alert-${type}`;
            alertDiv.textContent = message;
            document.body.appendChild(alertDiv);

            setTimeout(() => alertDiv.remove(), 5000);
        },

        /**
         * Formato de números
         */
        formatNumber: function(num) {
            return new Intl.NumberFormat('es-PE').format(num);
        },

        /**
         * Formato de porcentaje
         */
        formatPercent: function(value) {
            return (value * 100).toFixed(2) + '%';
        }
    };

    // Exportar para uso global
    window.Intelligence = window.Intelligence || {};
})();
