(() => {
    'use strict';
    const uploadForm = document.getElementById('master-raster-upload');
    const list = document.getElementById('master-raster-list');
    if (!uploadForm || !list) return;
    const status = document.getElementById('master-raster-status');
    const editor = document.getElementById('master-raster-editor');
    const activeName = document.getElementById('master-raster-active-name');
    const latInput = document.getElementById('master-raster-lat');
    const lngInput = document.getElementById('master-raster-lng');
    const widthInput = document.getElementById('master-raster-width');
    const heightInput = document.getElementById('master-raster-height');
    const rotationInput = document.getElementById('master-raster-rotation');
    const opacityInput = document.getElementById('master-raster-opacity');
    const saveButton = document.getElementById('master-raster-save');
    const cancelButton = document.getElementById('master-raster-cancel');
    const csrf = uploadForm.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    let map = null;
    let district = '';
    let overlays = [];
    let active = null;
    let draft = null;
    let loadToken = 0;
    const views = new Map();

    const say = (message, error = false) => {
        status.textContent = message;
        status.dataset.error = String(error);
    };
    const clamp = (value, low, high) => Math.min(high, Math.max(low, Number(value)));
    const clone = value => JSON.parse(JSON.stringify(value));
    const number = value => Number(value).toLocaleString('es-PE', {maximumFractionDigits: 1});

    function useSatellitePatchMode() {
        if (!map || !overlays.some(record => record.state.visible !== false)) return;
        if (map.getMapTypeId() !== 'satellite') map.setMapTypeId('satellite');
        document.getElementById('master-satellite')?.setAttribute('aria-pressed', 'true');
    }

    function offset(center, eastMetres, northMetres) {
        const metresPerLat = 111320;
        const metresPerLng = metresPerLat * Math.cos(center.lat * Math.PI / 180);
        return {
            lat: center.lat + northMetres / metresPerLat,
            lng: center.lng + eastMetres / metresPerLng,
        };
    }

    let DroneOverlayClass = null;
    function droneOverlayClass() {
        if (DroneOverlayClass) return DroneOverlayClass;
        DroneOverlayClass = class extends google.maps.OverlayView {
        constructor(record) {
            super();
            this.record = record;
            this.state = clone(record.state);
            this.editing = false;
            this.element = null;
        }

        onAdd() {
            const wrapper = document.createElement('div');
            wrapper.className = 'master-raster-image-layer';
            wrapper.dataset.overlayId = this.record.id;
            const image = document.createElement('img');
            image.alt = this.record.name;
            image.draggable = false;
            image.src = this.record.image_url + '?ubigeo=' + encodeURIComponent(this.record.ubigeo) +
                '&v=' + encodeURIComponent(this.record.version_id);
            wrapper.append(image);
            this.image = image;
            wrapper.style.zIndex = '1';
            this.element = wrapper;
            const overlayPane = this.getPanes().overlayShadow;
            const root = overlayPane.parentElement;
            const basePane = root
                ? Array.from(root.children).find(node => getComputedStyle(node).zIndex === '100')
                : null;
            (basePane || overlayPane).append(wrapper);
        }

        onRemove() {
            this.element?.remove();
            this.element = null;
        }

        setEditing(value) {
            this.editing = Boolean(value);
            this.element?.classList.toggle('editing', this.editing);
            this.draw();
        }

        update(state) {
            this.state = clone(state);
            this.draw();
        }

        centerPointerPixel() {
            const projection = this.getProjection();
            if (!projection) return null;
            return projection.fromLatLngToContainerPixel(new google.maps.LatLng(this.state.center));
        }

        draw() {
            if (!this.element || !this.getProjection()) return;
            const state = this.state;
            const angle = state.rotation_deg * Math.PI / 180;
            const right = {east: Math.cos(angle), north: -Math.sin(angle)};
            const up = {east: Math.sin(angle), north: Math.cos(angle)};
            const projection = this.getProjection();
            const left = offset(state.center, -right.east * state.width_m / 2,
                -right.north * state.width_m / 2);
            const rightPoint = offset(state.center, right.east * state.width_m / 2,
                right.north * state.width_m / 2);
            const top = offset(state.center, up.east * state.height_m / 2,
                up.north * state.height_m / 2);
            const bottom = offset(state.center, -up.east * state.height_m / 2,
                -up.north * state.height_m / 2);
            const centerPixel = projection.fromLatLngToDivPixel(new google.maps.LatLng(state.center));
            const leftPixel = projection.fromLatLngToDivPixel(new google.maps.LatLng(left));
            const rightPixel = projection.fromLatLngToDivPixel(new google.maps.LatLng(rightPoint));
            const topPixel = projection.fromLatLngToDivPixel(new google.maps.LatLng(top));
            const bottomPixel = projection.fromLatLngToDivPixel(new google.maps.LatLng(bottom));
            const width = Math.max(1, Math.hypot(rightPixel.x - leftPixel.x, rightPixel.y - leftPixel.y));
            const height = Math.max(1, Math.hypot(bottomPixel.x - topPixel.x, bottomPixel.y - topPixel.y));
            this.element.hidden = !state.visible;
            this.element.style.left = (centerPixel.x - width / 2) + 'px';
            this.element.style.top = (centerPixel.y - height / 2) + 'px';
            this.element.style.width = width + 'px';
            this.element.style.height = height + 'px';
            this.element.style.transform = 'rotate(' + state.rotation_deg + 'deg)';
            this.image.style.opacity = state.opacity;
            this.element.classList.toggle('editing', this.editing);
            this.element.querySelectorAll('.master-raster-handle,.master-raster-rotate').forEach(
                handle => { handle.hidden = !this.editing; });
        }

        gestureStart(event, target) {
            if (!this.editing) return null;
            event.preventDefault();
            event.stopPropagation();
            target.setPointerCapture(event.pointerId);
            const rect = map.getDiv().getBoundingClientRect();
            return {
                pointerId: event.pointerId,
                startPoint: new google.maps.Point(event.clientX - rect.left, event.clientY - rect.top),
                startState: clone(this.state),
                target,
            };
        }

        beginMove(event, target) {
            const gesture = this.gestureStart(event, target);
            if (!gesture) return;
            const projection = this.getProjection();
            const startCenter = projection.fromContainerPixelToLatLng(gesture.startPoint);
            map.setOptions({gestureHandling: 'none'});
            const move = current => {
                const rect = map.getDiv().getBoundingClientRect();
                const point = new google.maps.Point(current.clientX - rect.left, current.clientY - rect.top);
                const currentCenter = projection.fromContainerPixelToLatLng(point);
                this.state.center = {
                    lat: gesture.startState.center.lat + currentCenter.lat() - startCenter.lat(),
                    lng: gesture.startState.center.lng + currentCenter.lng() - startCenter.lng(),
                };
                syncDraftFromView();
                this.draw();
            };
            this.captureGesture(gesture, move);
        }

        beginResize(event, target) {
            const gesture = this.gestureStart(event, target);
            if (!gesture) return;
            const center = this.centerPointerPixel();
            const rect = map.getDiv().getBoundingClientRect();
            const startDistance = Math.max(5, Math.hypot(
                gesture.startPoint.x - center.x, gesture.startPoint.y - center.y));
            map.setOptions({gestureHandling: 'none'});
            const move = current => {
                const point = new google.maps.Point(current.clientX - rect.left, current.clientY - rect.top);
                const ratio = clamp(Math.hypot(point.x - center.x, point.y - center.y) / startDistance, .1, 10);
                this.state.width_m = clamp(gesture.startState.width_m * ratio, 5, 10000);
                this.state.height_m = clamp(gesture.startState.height_m * ratio, 5, 10000);
                syncDraftFromView();
                this.draw();
            };
            this.captureGesture(gesture, move);
        }

        beginRotate(event, target) {
            const gesture = this.gestureStart(event, target);
            if (!gesture) return;
            const center = this.centerPointerPixel();
            const startAngle = Math.atan2(gesture.startPoint.x - center.x,
                -(gesture.startPoint.y - center.y)) * 180 / Math.PI;
            const rect = map.getDiv().getBoundingClientRect();
            map.setOptions({gestureHandling: 'none'});
            const move = current => {
                const point = new google.maps.Point(current.clientX - rect.left, current.clientY - rect.top);
                const angle = Math.atan2(point.x - center.x, -(point.y - center.y)) * 180 / Math.PI;
                this.state.rotation_deg = ((gesture.startState.rotation_deg + angle - startAngle) % 360 + 360) % 360;
                syncDraftFromView();
                this.draw();
            };
            this.captureGesture(gesture, move);
        }

        captureGesture(gesture, move) {
            const end = () => {
                gesture.target.removeEventListener('pointermove', move);
                gesture.target.removeEventListener('pointerup', end);
                gesture.target.removeEventListener('pointercancel', end);
                map.setOptions({gestureHandling: 'auto'});
            };
            gesture.target.addEventListener('pointermove', move);
            gesture.target.addEventListener('pointerup', end);
            gesture.target.addEventListener('pointercancel', end);
        }
        };
        return DroneOverlayClass;
    }

    function syncEditor() {
        if (!draft) return;
        latInput.value = draft.center.lat.toFixed(9);
        lngInput.value = draft.center.lng.toFixed(9);
        widthInput.value = Number(draft.width_m.toFixed(1));
        heightInput.value = Number(draft.height_m.toFixed(1));
        rotationInput.value = Number(draft.rotation_deg.toFixed(1));
        opacityInput.value = Math.round(draft.opacity * 100);
        const current = active ? views.get(active.id) : null;
        current?.setEditing(!draft.locked);
        current?.update(draft);
    }

    function syncDraftFromView() {
        const current = active ? views.get(active.id) : null;
        if (!current || !draft) return;
        draft = clone(current.state);
        syncEditor();
    }

    function editOverlay(id) {
        active = overlays.find(item => item.id === id) || null;
        if (!active) return;
        draft = clone(active.state);
        draft.locked = false;
        activeName.textContent = active.name;
        editor.hidden = false;
        for (const [key, view] of views) view.setEditing(key === id && !draft.locked);
        syncEditor();
        if (map) {
            map.panTo(active.state.center);
            if (map.getZoom() < 16) map.setZoom(17);
        }
        requestAnimationFrame(() => editor.scrollIntoView({block: 'nearest', behavior: 'smooth'}));
        useSatellitePatchMode();
        say('Edita los casilleros de latitud, longitud, tamaño, rotación u opacidad y luego fija el parche.');
    }

    function numericInput(input, key) {
        input.addEventListener('change', () => {
            if (!draft) return;
            draft[key] = Number(input.value);
            const current = views.get(active.id);
            current?.update(draft);
        });
    }
    latInput.addEventListener('change', () => {
        if (!draft) return;
        draft.center.lat = Number(latInput.value);
        views.get(active.id)?.update(draft);
    });
    lngInput.addEventListener('change', () => {
        if (!draft) return;
        draft.center.lng = Number(lngInput.value);
        views.get(active.id)?.update(draft);
    });
    numericInput(widthInput, 'width_m');
    numericInput(heightInput, 'height_m');
    numericInput(rotationInput, 'rotation_deg');
    opacityInput.addEventListener('change', () => {
        if (!draft) return;
        draft.opacity = Number(opacityInput.value) / 100;
        views.get(active.id)?.update(draft);
    });
    function changeDraft(mutator) {
        if (!draft || !active) return;
        mutator(draft);
        syncEditor();
    }
    document.getElementById('master-raster-scale-down').addEventListener('click', () =>
        changeDraft(value => {
            value.width_m = clamp(value.width_m * .98, 5, 10000);
            value.height_m = clamp(value.height_m * .98, 5, 10000);
        }));
    document.getElementById('master-raster-scale-up').addEventListener('click', () =>
        changeDraft(value => {
            value.width_m = clamp(value.width_m * 1.02, 5, 10000);
            value.height_m = clamp(value.height_m * 1.02, 5, 10000);
        }));
    document.getElementById('master-raster-move-up').addEventListener('click', () =>
        changeDraft(value => { value.center = offset(value.center, 0, 1); }));
    document.getElementById('master-raster-move-down').addEventListener('click', () =>
        changeDraft(value => { value.center = offset(value.center, 0, -1); }));
    document.getElementById('master-raster-move-left').addEventListener('click', () =>
        changeDraft(value => { value.center = offset(value.center, -1, 0); }));
    document.getElementById('master-raster-move-right').addEventListener('click', () =>
        changeDraft(value => { value.center = offset(value.center, 1, 0); }));
    document.getElementById('master-raster-rotate-left').addEventListener('click', () =>
        changeDraft(value => { value.rotation_deg = (value.rotation_deg - 1 + 360) % 360; }));
    document.getElementById('master-raster-rotate-right').addEventListener('click', () =>
        changeDraft(value => { value.rotation_deg = (value.rotation_deg + 1) % 360; }));
    cancelButton.addEventListener('click', () => {
        if (!active) return;
        draft = clone(active.state);
        draft.locked = true;
        syncEditor();
        say('Ajuste descartado.');
    });
    saveButton.addEventListener('click', async () => {
        if (!active || !draft) return;
        saveButton.disabled = true;
        say('Guardando calibración…');
        try {
            draft.locked = true;
            const response = await fetch('/catastro/api/maestro/raster/' +
                encodeURIComponent(active.id) + '/calibracion/', {
                method: 'POST', credentials: 'same-origin',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf, 'Accept': 'application/json'},
                body: JSON.stringify({ubigeo: district, state: draft}),
            });
            const value = await response.json();
            if (!response.ok) throw Error(value.error || 'No se pudo fijar la capa.');
            await loadOverlays();
            say('Capa fijada y guardada como nueva versión del Catastro Maestro.');
        } catch (error) {
            say(error.message, true);
        } finally {
            saveButton.disabled = false;
        }
    });

    function createView(record) {
        if (!map || views.has(record.id)) return;
        const Overlay = droneOverlayClass();
        const view = new Overlay(record);
        view.setMap(map);
        views.set(record.id, view);
        if (active?.id === record.id && draft) view.update(draft);
    }

    function renderList() {
        list.replaceChildren();
        if (!overlays.length) {
            const empty = document.createElement('p');
            empty.className = 'master-help';
            empty.textContent = 'Todavía no hay fotografías aéreas en este distrito.';
            list.append(empty);
            return;
        }
        for (const record of overlays) {
            const row = document.createElement('article');
            row.className = 'master-raster-item';
            const label = document.createElement('label');
            const check = document.createElement('input');
            check.type = 'checkbox';
            check.checked = record.state.visible !== false;
            const copy = document.createElement('span');
            const title = document.createElement('strong');
            title.textContent = record.name;
            const meta = document.createElement('small');
            meta.textContent = number(record.state.width_m) + ' × ' + number(record.state.height_m) +
                ' m · ' + number(record.state.rotation_deg) + '°';
            copy.append(title, meta);
            label.append(check, copy);
            check.addEventListener('change', () => {
                const view = views.get(record.id);
                record.state.visible = check.checked;
                if (view) {
                    view.state.visible = check.checked;
                    view.draw();
                }
            });
            const actions = document.createElement('div');
            actions.className = 'master-raster-item-actions';
            const adjust = document.createElement('button');
            adjust.type = 'button';
            adjust.textContent = 'Ajustar';
            adjust.addEventListener('click', () => editOverlay(record.id));
            actions.append(adjust);
            row.append(label, actions);
            list.append(row);
            createView(record);
        }
    }

    async function loadOverlays(focusId = null) {
        if (!district) return;
        const token = ++loadToken;
        try {
            const query=district==='all'?'':'?ubigeo='+encodeURIComponent(district);
            const response = await fetch('/catastro/api/maestro/raster/'+query,
                {credentials: 'same-origin', headers: {Accept: 'application/json'}});
            const value = await response.json();
            if (!response.ok) throw Error(value.error || 'No se pudieron cargar las capas satelitales.');
            if (token !== loadToken || district !== document.getElementById('master-district').value) return;
            for (const view of views.values()) view.setMap(null);
            views.clear();
            overlays = value.overlays || [];
            active = null;
            draft = null;
            editor.hidden = true;
            renderList();
            useSatellitePatchMode();
            if (focusId) editOverlay(focusId);
        } catch (error) {
            say(error.message, true);
        }
    }

    uploadForm.addEventListener('submit', async event => {
        event.preventDefault();
        if (district === 'all') {
            say('Selecciona un distrito concreto para cargar una fotografía aérea.', true);
            return;
        }
        if (!district) {
            say('Selecciona un distrito antes de cargar la imagen.', true);
            return;
        }
        const button = uploadForm.querySelector('button[type=submit]');
        const data = new FormData(uploadForm);
        data.set('ubigeo', district);
        button.disabled = true;
        say('Archivando fotografía y creando la huella inicial…');
        try {
            const response = await fetch('/catastro/api/maestro/raster/', {
                method: 'POST', credentials: 'same-origin',
                headers: {'X-CSRFToken': csrf, Accept: 'application/json'}, body: data,
            });
            const value = await response.json();
            if (!response.ok) throw Error(value.error || 'No se pudo cargar la capa.');
            uploadForm.reset();
            await loadOverlays(value.overlay.id);
            say('Parche incorporado al satélite. Ajusta su posición y pulsa «Fijar parche satelital».');
        } catch (error) {
            say(error.message, true);
        } finally {
            button.disabled = false;
        }
    });

    window.addEventListener('catastro-master-ready', event => {
        map = event.detail.map;
        for (const record of overlays) createView(record);
    });
    window.addEventListener('catastro-master-district', event => {
        district = event.detail.ubigeo;
        loadOverlays();
    });
    if (window.CatastroMasterMap?.getMap()) {
        map = window.CatastroMasterMap.getMap();
        for (const record of overlays) createView(record);
    }
})();
