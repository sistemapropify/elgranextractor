/* One interpretation of the server result for cards, details and map labels. */
(function (root) {
  'use strict';
  const money = n => n == null ? '—' : new Intl.NumberFormat('es-PE', {
    style: 'currency', currency: 'USD', maximumFractionDigits: 0
  }).format(n);
  function property(record, result, excluded = new Set()) {
    if (!result) return {status:'pending', reason:'Análisis pendiente de actualización'};
    if (record.issues.length) return {status:'reference', reason:record.issues.join(' · ')};
    if (excluded.has(record.id)) return {status:'excluded', reason:'Desmarcada: no interviene en el cálculo'};
    if (record.kind === 'Terreno') {
      return {status:'land', offerUnit:record.price / record.land,
        selected:result.land_ids.includes(record.id)};
    }
    const detail = result.breakdown.find(row => row.id === record.id);
    if (!detail) return {status:'pending', reason:result.messages.join(' ') || 'Referencia de suelo pendiente'};
    return {status:detail.usable ? 'house' : 'review', landUnit:detail.land_unit,
      landValue:detail.land_value, remainder:detail.remainder, builtUnit:detail.built_unit,
      reason:detail.usable ? '' : 'Remanente no positivo: revisar precio, áreas o referencia de suelo'};
  }
  function marker(record, value, mode) {
    if (mode === 'price') return 'Anuncio ' + money(record.price);
    if (value.status === 'reference') return 'Solo referencia';
    if (value.status === 'excluded') return 'No seleccionada';
    if (value.status === 'pending') return 'Sin cálculo';
    if (value.status === 'land') return 'Suelo (oferta) ' + money(value.offerUnit) + '/m²';
    if (mode === 'improvements') return (value.status === 'review' ? 'Revisar: ' : 'Mejoras ') + money(value.builtUnit) + '/m²';
    return 'Suelo estim. ' + money(value.landUnit) + '/m²';
  }
  const api = {property, marker};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.ACMComponentsPresentation = api;
})(typeof window !== 'undefined' ? window : globalThis);
