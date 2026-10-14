/* Google Maps adapter. The data client has no dependency on this SDK. */
(function () {
    'use strict';
    window.GeollaqtaGoogleAdapter = {
        create(map) {
            return {
                createLayer: () => new google.maps.Data(),
                pointIcon: opacity => ({path: google.maps.SymbolPath.CIRCLE, scale: 3,
                    fillOpacity: opacity, strokeColor: '#ffffff', strokeWeight: 1}),
                getView() {
                    const bounds = map.getBounds();
                    if (!bounds) return {zoom: map.getZoom(), bbox: null};
                    const sw = bounds.getSouthWest(), ne = bounds.getNorthEast();
                    return {zoom: map.getZoom(), bbox: [sw.lng(), sw.lat(), ne.lng(), ne.lat()]};
                },
                focus(center, zoom) { map.setCenter(center); map.setZoom(zoom); },
                onIdle: callback => map.addListener('idle', callback)
            };
        }
    };
})();
