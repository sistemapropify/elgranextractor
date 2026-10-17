/* Shared facade camera for Google Maps cards; callers own access and layout. */
(() => {
    'use strict';

    const radians = degrees => degrees * Math.PI / 180;
    function point(value) {
        if (!value) return null;
        const rawLat = typeof value.lat === 'function' ? value.lat() : value.lat;
        const rawLng = typeof value.lng === 'function' ? value.lng() : value.lng;
        if (rawLat == null || rawLng == null || rawLat === '' || rawLng === '') return null;
        const lat = Number(rawLat), lng = Number(rawLng);
        return Number.isFinite(lat) && Number.isFinite(lng) && Math.abs(lat) <= 90 && Math.abs(lng) <= 180 ? {lat, lng} : null;
    }
    function distance(a, b) {
        const dLat = radians(b.lat - a.lat), dLng = radians(b.lng - a.lng);
        const h = Math.sin(dLat / 2) ** 2 + Math.cos(radians(a.lat)) * Math.cos(radians(b.lat)) * Math.sin(dLng / 2) ** 2;
        return 12742000 * Math.asin(Math.sqrt(Math.min(1, h)));
    }
    function heading(camera, target) {
        const delta = radians(target.lng - camera.lng), a = radians(camera.lat), b = radians(target.lat);
        return (Math.atan2(Math.sin(delta) * Math.cos(b), Math.cos(a) * Math.sin(b) - Math.sin(a) * Math.cos(b) * Math.cos(delta)) * 180 / Math.PI + 360) % 360;
    }

    function create(map, elements, options = {}) {
        const {section, preview: host, status: message, open, retry, date: imageDate} = elements;
        if (![section, host, message, open, retry, imageDate].every(Boolean) || typeof map.getStreetView !== 'function') return null;
        const targetLabel = options.targetLabel || 'el pin';
        const targetInstruction = options.targetInstruction || 'Sitúa el pin dentro del predio para orientar la cámara hacia su fachada.';
        let library, service, panorama, target = null, selected = null;
        let serial = 0, timer = null, deadline = null, disposed = false, suspended = false, ready = false;

        function status(text, busy = false, canRetry = false) {
            message.textContent = text;
            section.setAttribute('aria-busy', String(busy));
            retry.hidden = !canRetry;
        }
        function stop() {
            ++serial; clearTimeout(timer); clearTimeout(deadline); timer = deadline = null;
        }
        function unavailable(text) {
            ready = false; selected = null; host.hidden = true; open.hidden = true; imageDate.hidden = true;
            panorama?.setVisible(false);
            status(text, false, true);
        }
        async function mapsLibrary() {
            if (!library) library = Promise.resolve(google.maps.StreetViewService && google.maps.StreetViewPanorama ? google.maps : google.maps.importLibrary('streetView')).catch(error => { library = null; throw error; });
            return library;
        }
        function orient() {
            const pov = {heading: heading(selected.camera, target), pitch: 0};
            panorama.setPov(pov); panorama.setZoom(1);
            return pov;
        }
        function display(data, maps) {
            selected = {pano: data.location.pano, camera: point(data.location.latLng)};
            const date = typeof data.imageDate === 'string' && /^\d{4}-(0[1-9]|1[0-2])$/.test(data.imageDate) ? data.imageDate : null;
            imageDate.hidden = !date;
            if (date) {
                imageDate.dateTime = date;
                imageDate.textContent = ' · ' + new Intl.DateTimeFormat('es-PE', {month: 'long', year: 'numeric', timeZone: 'UTC'}).format(new Date(date + '-01T00:00:00Z'));
            }
            const alreadyLoaded = panorama && panorama.getPano() === selected.pano && panorama.getStatus() === 'OK';
            host.hidden = false;
            if (!panorama) {
                panorama = new maps.StreetViewPanorama(host, {
                    visible: false, disableDefaultUI: true, clickToGo: false,
                    linksControl: false, addressControl: false, panControl: false,
                    zoomControl: false, fullscreenControl: false, showRoadLabels: false,
                    motionTracking: false, motionTrackingControl: false,
                    scrollwheel: false, disableDoubleClickZoom: true,
                });
                panorama.addListener('status_changed', () => {
                    if (disposed || suspended || !selected || panorama.getPano() !== selected.pano) return;
                    const state = panorama.getStatus();
                    if (state === 'OK') {
                        clearTimeout(deadline); ready = true; open.hidden = false;
                        status('Vista orientada hacia ' + targetLabel + '.');
                    } else if (state) {
                        clearTimeout(deadline); unavailable('No se pudo mostrar Street View. Vuelve a intentarlo.');
                    }
                });
            }
            ready = false; open.hidden = true;
            panorama.setPano(selected.pano); orient(); panorama.setVisible(true);
            google.maps.event.trigger(panorama, 'resize');
            // Reusing the same panorama need not emit status_changed again.
            if (alreadyLoaded) {
                clearTimeout(deadline); ready = true; open.hidden = false; status('Vista orientada hacia ' + targetLabel + '.');
            }
        }
        async function lookup(stamp) {
            try {
                const maps = await mapsLibrary();
                if (stamp !== serial || disposed || suspended) return;
                service ||= new maps.StreetViewService();
                const location = {...target};
                let callbackReceived = false;
                const pending = service.getPanorama({location, radius: 50, preference: 'nearest', sources: ['outdoor']}, (data, state) => {
                    callbackReceived = true;
                    if (stamp !== serial || disposed || suspended) return;
                    const camera = point(data?.location?.latLng);
                    if (state !== 'OK' || !data?.location?.pano || !camera || distance(camera, target) > 50) {
                        clearTimeout(deadline);
                        unavailable(state === 'ZERO_RESULTS' || state === 'OK' ? 'No hay una toma de Street View a menos de 50 m de la ubicación seleccionada.' : 'No se pudo consultar Street View. Vuelve a intentarlo.');
                        return;
                    }
                    if (distance(camera, target) < 1) {
                        clearTimeout(deadline); unavailable(targetInstruction); return;
                    }
                    display(data, maps);
                });
                // Maps versions can return a rejected Promise in addition to the callback.
                pending?.catch(() => {
                    if (!callbackReceived && stamp === serial && !disposed && !suspended && !selected) {
                        clearTimeout(deadline); unavailable('No se pudo consultar Street View. Vuelve a intentarlo.');
                    }
                });
            } catch (error) {
                if (stamp === serial && !disposed && !suspended) {clearTimeout(deadline); unavailable('No se pudo consultar Street View. Vuelve a intentarlo.');}
            }
        }
        function queue(value, force = false) {
            const location = point(value);
            if (!location || disposed) return;
            const same = target && distance(target, location) < 2;
            target = location; section.hidden = false;
            if (same && !force && !suspended) {
                if (selected && ready) {orient(); google.maps.event.trigger(panorama, 'resize');}
                return;
            }
            suspended = false; stop(); selected = null; ready = false;
            panorama?.setVisible(false); host.hidden = true; open.hidden = true; imageDate.hidden = true;
            status('Buscando Street View hacia ' + targetLabel + '…', true);
            const stamp = serial;
            timer = setTimeout(() => {
                deadline = setTimeout(() => {
                    if (stamp !== serial) return;
                    stop(); unavailable('Street View tardó demasiado. Puedes volver a intentarlo.');
                }, 15000);
                lookup(stamp);
            }, 750);
        }
        function suspend() {
            stop(); suspended = true; ready = false; panorama?.setVisible(false);
        }
        function destroy() {
            suspend(); disposed = true; section.hidden = true; selected = target = null;
        }
        open.addEventListener('click', () => {
            if (!ready || !selected || disposed || suspended) return;
            const viewer = map.getStreetView();
            viewer.setOptions({motionTracking: false, motionTrackingControl: false});
            viewer.setPano(selected.pano); viewer.setPov(panorama.getPov()); viewer.setZoom(panorama.getZoom()); viewer.setVisible(true);
        });
        retry.addEventListener('click', () => {if (target) queue(target, true);});
        return {queue, suspend, destroy};
    }
    window.StreetFacadeView = {create};
})();
