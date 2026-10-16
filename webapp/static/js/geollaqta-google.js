/* Google Maps adapter. The data client has no dependency on this SDK. */
(function () {
    'use strict';
    window.GeollaqtaGoogleAdapter = {
        create(map) {
            return {
                createLayer: () => new google.maps.Data(),
                createLabels: () => window.GeollaqtaLabels?.create(map),
                pointIcon: opacity => ({path: google.maps.SymbolPath.CIRCLE, scale: 3,
                    fillOpacity: opacity, strokeColor: '#ffffff', strokeWeight: 1}),
                getView() {
                    const bounds = map.getBounds();
                    if (!bounds) return {zoom: map.getZoom(), bbox: null};
                    const sw = bounds.getSouthWest(), ne = bounds.getNorthEast();
                    return {zoom: map.getZoom(), bbox: [sw.lng(), sw.lat(), ne.lng(), ne.lat()]};
                },
                fitFeatures(features) {
                    const bounds=new google.maps.LatLngBounds();let count=0;
                    function visit(value){
                        if(!Array.isArray(value))return;
                        if(typeof value[0]==='number'&&typeof value[1]==='number'){bounds.extend({lng:value[0],lat:value[1]});count++;}
                        else value.forEach(visit);
                    }
                    features.forEach(feature=>visit(feature.geometry?.coordinates));
                    if(count)map.fitBounds(bounds,48);
                },
                focus(center, zoom) { map.setCenter(center); map.setZoom(zoom); },
                onIdle: callback => map.addListener('idle', callback)
            };
        }
    };
})();
