/* One interpretation of the server result for cards, details and map labels. */
(function (root) {
  'use strict';
  const money = n => n == null ? '—' : new Intl.NumberFormat('es-PE', {
    style: 'currency', currency: 'USD', maximumFractionDigits: 0
  }).format(n);
  function offer(record) {
    const sale = record.operation === 'Venta' && record.operation_status !== 'review';
    const rent = record.operation === 'Alquiler';
    const land = record.kind === 'Terreno';
    const area = Number(land ? record.land : record.built);
    const price = record.price == null ? NaN : Number(record.price);
    return {
      operation: sale ? 'Venta' : rent ? 'Alquiler' : 'Operación por confirmar',
      totalLabel: sale ? 'Precio de venta total' : rent ? 'Importe de alquiler anunciado' : 'Importe anunciado · operación por confirmar',
      unitLabel: land ? 'Precio por m² de terreno' : 'Precio por m² construido',
      unit: Number.isFinite(price) && price > 0 && Number.isFinite(area) && area > 0 ? price / area : null,
      areaBasis: land ? 'terreno' : 'construida'
    };
  }
  function property(record, result, excluded = new Set()) {
    if (!result) return {status:'pending', reason:'Análisis pendiente de actualización'};
    if (result.reference_mode) {
      const detail = result.breakdown.find(row => row.id === record.id);
      return {status:excluded.has(record.id)?'excluded':'reference', referenceUsed:!!detail?.reference_used&&!excluded.has(record.id),
        offerUnit:detail?.offer_unit, adjustedTotal:detail?.adjusted_total,
        reason:record.issues.join(' · ')||'Referencia de mercado'};
    }
    if (record.issues.length) return {status:'reference', reason:record.issues.join(' · ')};
    if (excluded.has(record.id)) return {status:'excluded', reason:'Desmarcada: no interviene en el cálculo'};
    if (record.kind === 'Terreno') {
      return {status:'land', offerUnit:record.price / record.land,
        selected:result.land_ids.includes(record.id)};
    }
    const detail = result.breakdown.find(row => row.id === record.id);
    const nearestReference = {status:'reference', referenceOnly:true,
      reason:'Solo referencia: fuera de los comparables más cercanos usados para valorar'};
    if (!detail) {
      if (result.model === 'built' || result.valuation_mode === 'land_only') return nearestReference;
      return {status:'pending', reason:result.messages.join(' ') || 'Referencia de suelo pendiente'};
    }
    if (detail.method === 'built') {
      if (detail.reference_only || detail.usable === false ||
          (Array.isArray(result.house_ids) && !result.house_ids.includes(record.id))) return nearestReference;
      return {status:'area', offerUnit:detail.offer_unit, adjustedTotal:detail.adjusted_total};
    }
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
    if (mode === 'price') return 'Anuncio · ' + offer(record).totalLabel + ' ' + money(record.price);
    if (value.referenceUsed) return 'Referencia ' + money(value.offerUnit) + '/m²';
    if (value.status === 'reference') return 'Solo referencia';
    if (value.status === 'excluded') return 'No seleccionada';
    if (value.status === 'pending') return 'Sin cálculo';
    if (value.status === 'land') return 'Suelo (oferta) ' + money(value.offerUnit) + '/m²';
    if (value.status === 'area') return 'Oferta ' + money(value.offerUnit) + '/m² construido';
    if (mode === 'improvements') return (value.status === 'review' ? 'Revisar: ' : 'Mejoras ') + money(value.builtUnit) + '/m²';
    return 'Suelo estim. ' + money(value.landUnit) + '/m²';
  }
  const parkingNames = {
    lineal_techada:'Lineal techada', lineal_no_techada:'Lineal no techada',
    paralela_techada:'Paralela techada', paralela_no_techada:'Paralela no techada'
  };
  function comparisonFeatures(record) {
    const output = {floor:'', parking:'', type:'', parkingTitle:'', typeTitle:''};
    if (record.kind === 'Departamento') {
      const floor = record.floor_label ?? record.floor;
      output.floor = floor == null || floor === '' ? '—' : String(floor);
    }
    if (!['Casa','Departamento'].includes(record.kind)) return output;
    const types = (Array.isArray(record.parking_types) ? record.parking_types : [])
      .filter(key => Object.prototype.hasOwnProperty.call(parkingNames,key)).map(key => parkingNames[key]);
    const conflict = record.parking_status === 'conflict';
    output.parking = conflict ? '—' : record.parking_has === true ? 'Sí' : record.parking_has === false ? 'No' : '—';
    output.type = !conflict && record.parking_has === true && types.length ? types.join(' + ') : '—';
    output.parkingTitle = conflict ? 'Cochera: datos contradictorios; por confirmar' :
      record.parking_has === true ? 'Tiene cochera' : record.parking_has === false ? 'Sin cochera' : 'Cochera: sin información';
    output.typeTitle = output.type !== '—' ? output.type : record.parking_has === false && !conflict ?
      'No aplica: sin cochera' : 'Tipo de cochera: sin información';
    return output;
  }
  function numbering(records, orderedComparables) {
    const ids = [...new Set([...orderedComparables, ...records].map(row => String(row.id)))];
    return new Map(ids.map((id, index) => [id, index + 1]));
  }
  function marker(record, value, mode, compact = false) {
    if (compact) {
      const unit = offer(record).unit;
      const amount = unit == null ? '—' : '$' + Number(unit).toLocaleString('es-PE', {maximumFractionDigits:0});
      const similarity = record.overall_similarity == null ? '' : ' - (' + Number(record.overall_similarity).toLocaleString('es-PE', {maximumFractionDigits:1}) + '%)';
      return amount + '/m²' + similarity;
    }

    const similarity = record.overall_similarity == null ? '' : ' · Sim ' + Number(record.overall_similarity).toLocaleString('es-PE', {maximumFractionDigits:1}) + '%';
    return precision(record).short + ' · ' + markerValue(record, value, mode) + similarity;
  }
  function group(record, value) {
    if (value.status === 'land' && value.selected) return 'land';
    if (value.status === 'house' || value.status === 'area') return 'property';
    return record.kind === 'Terreno' ? 'other_reference' : 'property_reference';
  }
  function comparisonRows(records, params, result, excluded = new Set()) {
    const targetType = result?.valuation_mode === 'land_only' ? 'Terreno' : params.property_type;
    if (result?.reference_mode) return records.filter(record => record.kind === targetType && result.reference_display_ids.includes(record.id) && inMapRadius(record, params, result, 'property_reference'));
    const targetGroup = targetType === 'Terreno' ? 'land' : 'property';
    const usedIds = targetType === 'Terreno' ? result?.land_ids : result?.house_ids;
    return records.filter(record => record.kind === targetType &&
      (!Array.isArray(usedIds) || usedIds.includes(record.id)) &&
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
  const api = {comparisonFeatures, numbering, offer, property, marker, precision, group, comparisonRows, mapRadius, inMapRadius, mapRings};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.ACMComponentsPresentation = api;
})(typeof window !== 'undefined' ? window : globalThis);
