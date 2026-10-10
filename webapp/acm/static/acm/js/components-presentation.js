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
    if (detail.method === 'built') return {status:'area', offerUnit:detail.offer_unit, adjustedTotal:detail.adjusted_total};
    return {status:detail.reference_only ? 'reference' : detail.usable ? 'house' : 'review', landUnit:detail.land_unit,
      landValue:detail.land_value, remainder:detail.remainder, builtUnit:detail.built_unit,
      targetEstimate:detail.target_estimate,
      landAdjustment:detail.land_adjustment, builtAdjustment:detail.built_adjustment,
      weightedContribution:detail.weighted_contribution,
      recommended:!!detail.recommended, similarityWeight:detail.similarity_weight,
      referenceOnly:!!detail.reference_only,
      landSimilarity:detail.land_similarity, builtSimilarity:detail.built_similarity,
      distanceSimilarity:detail.distance_similarity, overallSimilarity:detail.overall_similarity,
      reason:detail.reference_only ? (result.recommended_ids?.length>1?'Solo referencia: fuera del grupo propuesto y aceptado; no interviene en el precio final':'Solo referencia: no es la casa elegida; compara sus superficies y similitudes con la marcada en verde') : detail.usable ? '' : 'Remanente no positivo: revisar precio, áreas o referencia de suelo'};
  }
  function precision(record) {
    if (record.precision === 'exacta') return {short:'Exa', label:'Ubicación exacta', kind:'exact'};
    if (record.precision === 'aproximada') return {short:'Apx', label:'Ubicación aproximada · solo referencia', kind:'approximate'};
    return {short:'S/d', label:'Precisión sin informar · solo referencia', kind:'unknown'};
  }
  function markerValue(record, value, mode) {
    if (mode === 'price') return 'Anuncio ' + money(record.price);
    if (value.status === 'reference') return 'Solo referencia';
    if (value.status === 'excluded') return 'No seleccionada';
    if (value.status === 'pending') return 'Sin cálculo';
    if (value.status === 'land') return 'Suelo (oferta) ' + money(value.offerUnit) + '/m²';
    if (value.status === 'area') return 'Oferta ' + money(value.offerUnit) + '/m² construido';
    if (mode === 'improvements') return (value.status === 'review' ? 'Revisar: ' : 'Mejoras ') + money(value.builtUnit) + '/m²';
    return 'Suelo estim. ' + money(value.landUnit) + '/m²';
  }
  function marker(record, value, mode) {
    const similarity = record.overall_similarity == null ? '' : ' · Sim ' + Number(record.overall_similarity).toLocaleString('es-PE', {maximumFractionDigits:1}) + '%';
    return precision(record).short + ' · ' + markerValue(record, value, mode) + similarity;
  }
  function group(record, value) {
    if (value.status === 'land' && value.selected) return 'land';
    if (value.status === 'house' || value.status === 'area') return 'property';
    return record.kind === 'Terreno' ? 'other_reference' : 'property_reference';
  }
  function comparisonRows(records, params, result, excluded = new Set()) {
    const targetGroup = params.property_type === 'Terreno' ? 'land' : 'property';
    return records.filter(record => record.kind === params.property_type &&
      group(record, property(record, result, excluded)) === targetGroup);
  }
  function mapRadius(params, result, layer) {
    return params.property_type === 'Casa' && layer === 'land'
      ? (result?.land_radius || params.radius) : params.radius;
  }
  function inMapRadius(record, params, result, layer) {
    return Number.isFinite(record.distance) && record.distance <= mapRadius(params, result, layer);
  }
  function mapRings(params, result, layers = new Set()) {
    const rings = [{radius:params.radius, color:'#00bfff', label:'Radio de comparables'}];
    if (params.property_type === 'Casa' && layers.has('land') && result?.land_radius && result.land_radius !== params.radius) {
      rings.push({radius:result.land_radius, color:'#ffb347', label:'Radio de suelo'});
    }
    return rings;
  }
  const api = {property, marker, precision, group, comparisonRows, mapRadius, inMapRadius, mapRings};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.ACMComponentsPresentation = api;
})(typeof window !== 'undefined' ? window : globalThis);
