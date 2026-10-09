/* Selección de oficinas Remax y tarjeta movible del mapa. */
(() => {
    'use strict';
    function agency(property) {
        const label = String(property.agency || '').replace(/\s+/g, ' ').trim();
        const key = label.replace(/^RE\s*\/?\s*MAX\b[\s:.-]*/i, '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
        return {key: key || '__unknown__', label: label || 'Sin agencia informada'};
    }
    function init(onChange) {
        const card = document.getElementById('remax-agencies-card');
        const host = document.getElementById('map-container');
        const handle = document.getElementById('remax-agencies-handle');
        const list = document.getElementById('remax-agencies-list');
        const status = document.getElementById('remax-agencies-status');
        const source = document.querySelector('[name="property-source"][value="remax"]');
        const master = document.getElementById('toggle-propify-properties');
        if (!card || !host || !source || !master) return null;
        const excluded = new Set();
        let groups = [], position = null, drag = null, frame = 0, busy = false;
        function fit() {
            if (card.hidden) return;
            const x = position ? position.x : host.clientWidth - card.offsetWidth - 8;
            const y = position ? position.y : host.clientHeight - card.offsetHeight - 32;
            position = {x: Math.max(8, Math.min(Math.max(8, host.clientWidth - card.offsetWidth - 8), x)),
                y: Math.max(8, Math.min(Math.max(8, host.clientHeight - card.offsetHeight - 8), y))};
            card.style.left = position.x + 'px'; card.style.top = position.y + 'px';
        }
        function schedule() {
            if (!frame) frame = requestAnimationFrame(() => {frame = 0; fit();});
        }
        function sync() {
            card.hidden = !source.checked || !master.checked;
            schedule();
        }
        function render() {
            list.replaceChildren();
            for (const group of groups) {
                const label = document.createElement('label');
                const input = document.createElement('input'); input.type = 'checkbox'; input.checked = !excluded.has(group.key); input.dataset.agency = group.key;
                const text = document.createElement('span'); text.textContent = group.label;
                const count = document.createElement('small'); count.textContent = group.count;
                input.addEventListener('change', () => {
                    if (input.checked) excluded.delete(group.key); else excluded.add(group.key);
                    refreshStatus(); onChange();
                });
                label.append(input, text, count); list.append(label);
            }
            refreshStatus(); sync();
        }
        function refreshStatus(message) {
            const selected = groups.filter(group => !excluded.has(group.key)).length;
            status.textContent = message || (busy ? 'Cargando agencias…' : groups.length ? selected + ' de ' + groups.length + ' seleccionadas' : 'No hay propiedades Remax cargadas.');
        }
        function update(properties) {
            busy = false;
            const byKey = new Map();
            for (const property of properties.filter(row => row.source_key === 'remax')) {
                const item = agency(property);
                if (!byKey.has(item.key)) byKey.set(item.key, {...item, count: 0});
                byKey.get(item.key).count++;
            }
            groups = [...byKey.values()].sort((a, b) => a.key === '__unknown__' ? 1 : b.key === '__unknown__' ? -1 : a.label.localeCompare(b.label, 'es', {sensitivity:'base'}));
            render();
        }
        for (const [id, selected] of [['remax-agencies-all', true], ['remax-agencies-none', false]]) {
            document.getElementById(id).addEventListener('click', () => {
                if (selected) excluded.clear(); else groups.forEach(group => excluded.add(group.key));
                render(); onChange();
            });
        }
        source.addEventListener('change', sync); master.addEventListener('change', sync);
        handle.addEventListener('pointerdown', event => {
            if (event.button !== 0 || event.target.closest('button')) return;
            event.preventDefault(); fit(); handle.focus(); handle.setPointerCapture(event.pointerId);
            drag = {x:event.clientX, y:event.clientY, left:position.x, top:position.y};
        });
        handle.addEventListener('pointermove', event => {
            if (!drag) return;
            position = {x:drag.left + event.clientX - drag.x, y:drag.top + event.clientY - drag.y}; fit();
        });
        function stop(event) {
            drag = null;
            if (handle.hasPointerCapture(event.pointerId)) handle.releasePointerCapture(event.pointerId);
        }
        ['pointerup','pointercancel','lostpointercapture'].forEach(type => handle.addEventListener(type, stop));
        handle.addEventListener('keydown', event => {
            const offsets = {ArrowLeft:[-10,0],ArrowRight:[10,0],ArrowUp:[0,-10],ArrowDown:[0,10]};
            if (!offsets[event.key] || event.target !== handle) return;
            event.preventDefault(); fit(); position.x += offsets[event.key][0]; position.y += offsets[event.key][1]; fit();
        });
        const observer = new ResizeObserver(schedule); observer.observe(host); observer.observe(card);
        sync();
        return {update, sync, accepts: property => property.source_key !== 'remax' || !excluded.has(agency(property).key),
            loading: () => {busy = true; refreshStatus(); sync();}, failed: () => {busy = false; refreshStatus('No se pudieron cargar las agencias.'); sync();}};
    }
    window.RemaxAgencies = {init};
})();
