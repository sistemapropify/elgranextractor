/* ACM role gate and bindings for the shared facade viewer. */
(() => {
    'use strict';
    function create(map) {
        if (!window.ACMPermissions?.cadastral_info || !window.StreetFacadeView) return null;
        const get = name => document.getElementById('cmp-street-' + name);
        return window.StreetFacadeView.create(map, {
            section: get('facade'), preview: get('preview'), status: get('status'),
            open: get('open'), retry: get('retry'), date: get('date')
        });
    }
    window.ACMStreetFacade = {create};
})();
