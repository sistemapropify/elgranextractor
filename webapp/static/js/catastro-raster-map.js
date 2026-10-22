(() => {
    'use strict';
    const CATALOG = '/catastro/api/maestro/raster/catalogo/';
    const isSatellite = map => ['satellite', 'hybrid'].includes(map.getMapTypeId());

    function offset(center, eastMetres, northMetres) {
        const metresPerLat = 111320;
        const metresPerLng = metresPerLat * Math.cos(center.lat * Math.PI / 180);
        return {
            lat: center.lat + northMetres / metresPerLat,
            lng: center.lng + eastMetres / metresPerLng,
        };
    }

    let PatchLayerClass = null;
    function patchLayerClass() {
        if (PatchLayerClass) return PatchLayerClass;
        PatchLayerClass = class extends google.maps.OverlayView {
        constructor(record) {
            super();
            this.record = record;
            this.element = null;
        }
        onAdd() {
            const element = document.createElement('div');
            element.className = 'catastro-raster-map-patch';
            const image = document.createElement('img');
            image.alt = this.record.name;
            image.draggable = false;
            image.src = this.record.image_url + '&v=' + encodeURIComponent(this.record.version_id);
            element.append(image);
            element.style.zIndex = '1';
            this.element = element;
            const overlayPane = this.getPanes().overlayShadow;
            const root = overlayPane.parentElement;
            // Put the photo in the base-tile pane (z=100). Google labels and
            // POIs are painted by the next pane (z=101), so they stay on top.
            const basePane = root
                ? Array.from(root.children).find(node => getComputedStyle(node).zIndex === '100')
                : null;
            (basePane || overlayPane).append(element);
        }
        onRemove() {
            this.element?.remove();
            this.element = null;
        }
        draw() {
            if (!this.element || !this.getProjection()) return;
            const state = this.record.state;
            const visible = isSatellite(this.getMap()) && state.visible !== false;
            this.element.hidden = !visible;
            if (!visible) return;
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
            const width = Math.hypot(rightPixel.x - leftPixel.x, rightPixel.y - leftPixel.y);
            const height = Math.hypot(bottomPixel.x - topPixel.x, bottomPixel.y - topPixel.y);
            this.element.style.left = (centerPixel.x - width / 2) + 'px';
            this.element.style.top = (centerPixel.y - height / 2) + 'px';
            this.element.style.width = width + 'px';
            this.element.style.height = height + 'px';
            this.element.style.transform = 'rotate(' + state.rotation_deg + 'deg)';
            this.element.style.opacity = state.opacity;
        }
        };
        return PatchLayerClass;
    }

    function init(map, options = {}) {
        if (map.__catastroRasterMap) return map.__catastroRasterMap;
        const catalog = options.catalogUrl || CATALOG;
        // ACM previously disabled the native basemap switch. Keep it available
        // for every role with cadastral access so the shared patch can be seen.
        map.setOptions({
            mapTypeControl: true,
            mapTypeControlOptions: {
                style: google.maps.MapTypeControlStyle.HORIZONTAL_BAR,
                position: google.maps.ControlPosition.TOP_RIGHT,
            },
        });
        const views = new Map();
        let loading = null;

        function render(records) {
            for (const view of views.values()) view.setMap(null);
            views.clear();
            const PatchLayer = patchLayerClass();
            for (const record of records) {
                const view = new PatchLayer(record);
                view.setMap(map);
                views.set(record.id, view);
            }
        }

        async function refresh() {
            if (loading) return loading;
            loading = fetch(catalog, {
                credentials: 'same-origin', cache: 'no-store',
                headers: {Accept: 'application/json'},
            }).then(async response => {
                const value = await response.json();
                if (!response.ok) throw Error(value.error || 'No se pudo cargar el mosaico satelital.');
                render(value.overlays || []);
                return value;
            }).finally(() => { loading = null; });
            return loading;
        }

        const controller = {
            refresh,
            redraw() { views.forEach(view => view.draw()); },
        };
        map.__catastroRasterMap = controller;
        map.addListener('maptypeid_changed', () => {
            if (isSatellite(map)) {
                refresh().then(() => controller.redraw()).catch(() => {});
            } else {
                controller.redraw();
            }
        });
        window.addEventListener('focus', () => {
            if (isSatellite(map)) refresh().then(() => controller.redraw()).catch(() => {});
        });
        refresh().catch(() => {});
        return controller;
    }

    window.CatastroRasterMap = {init};
})();
