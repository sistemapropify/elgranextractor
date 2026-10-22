(() => {
    'use strict';
    const dialog = document.getElementById('master-data-model');
    if (!dialog) return;
    const open = document.getElementById('master-model-open');
    const close = document.getElementById('master-model-close');
    const copy = document.getElementById('master-model-copy');
    const status = document.getElementById('master-model-copy-status');

    open?.addEventListener('click', () => {
        status.textContent = '';
        if (typeof dialog.showModal === 'function') dialog.showModal();
        else dialog.setAttribute('open', '');
    });
    close?.addEventListener('click', () => dialog.close?.());
    dialog.addEventListener('click', event => {
        if (event.target === dialog) dialog.close?.();
    });
    copy?.addEventListener('click', async () => {
        const target = document.getElementById(copy.dataset.copyTarget);
        const sql = target?.textContent || '';
        try {
            await navigator.clipboard.writeText(sql);
            status.textContent = 'Consulta copiada.';
        } catch (_) {
            const range = document.createRange();
            range.selectNodeContents(target);
            const selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(range);
            status.textContent = 'La consulta quedó seleccionada; usa Ctrl+C para copiarla.';
        }
    });
})();
