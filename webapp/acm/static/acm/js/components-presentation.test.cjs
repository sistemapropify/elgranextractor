const assert = require('node:assert/strict');
const {property, marker, precision, group, comparisonRows, mapRadius, inMapRadius, mapRings} = require('./components-presentation.js');
const house = {id:'a', precision:'exacta', kind:'Casa', price:350000, land:150, built:200, issues:[]};
const result = {land_ids:['land'], messages:[], breakdown:[{id:'a', land_unit:2000,
  land_value:300000, remainder:50000, built_unit:250, usable:true}]};
const detail = property(house,result);
assert.equal(detail.landUnit,2000);
assert.equal(detail.remainder,50000);
assert.equal(detail.builtUnit,250);
assert.match(marker(house,detail,'land'),/2[,.]000/);
assert.match(marker(house,detail,'improvements'),/250/);
assert.doesNotMatch(marker(house,detail,'land'),/1[,.]750/);
assert.equal(property({...house,issues:['Falta terreno']},result).status,'reference');
assert.equal(property(house,result,new Set(['a'])).status,'excluded');
assert.equal(marker(house,property(house,null),'land'),'Exa · Sin cálculo');
assert.equal(property(house,{...result,breakdown:[],messages:['Suelo insuficiente']}).status,'pending');
const updated=property(house,{...result,breakdown:[{...result.breakdown[0],land_unit:1800,land_value:270000,remainder:80000,built_unit:400}]});
assert.equal(updated.remainder,80000);
assert.match(marker(house,updated,'improvements'),/400/);
console.log('Presentation: house breakdown, map labels, references and recalculation verified.');

assert.equal(precision(house).short,'Exa');
const approximate={...house,precision:'aproximada',issues:['Ubicación no exacta']};
assert.equal(marker(approximate,property(approximate,result),'land'),'Apx · Solo referencia');
assert.match(marker(approximate,property(approximate,result),'price'),/^Apx · Anuncio/);
assert.equal(precision({...house,precision:null}).short,'S/d');
assert.equal(group(house,detail),'property');
const land={...house,id:'land',kind:'Terreno',built:null};
assert.equal(group(land,{status:'land',selected:true}),'land');
assert.equal(group(land,{status:'land',selected:false}),'other_reference');
assert.equal(group(approximate,property(approximate,result)),'property_reference');

// Reference layers must never add their records to the comparable card or report.
const referenceHouse={...house,id:'reference'};
const mixedResult={...result,breakdown:[...result.breakdown,
  {id:'reference',usable:true,reference_only:true,recommended:false}]};
assert.equal(group(referenceHouse,property(referenceHouse,mixedResult)),'property_reference');
assert.deepEqual(comparisonRows([house,referenceHouse,approximate,land],
  {property_type:'Casa'},mixedResult).map(row=>row.id),['a']);
assert.deepEqual(comparisonRows([house,referenceHouse],{property_type:'Casa'},
  mixedResult,new Set(['a'])),[]);
const apartment={...house,id:'apartment',kind:'Departamento'};
const apartmentReference={...apartment,id:'apartment-reference',issues:['Ubicación no exacta']};
const apartmentResult={...result,breakdown:[{id:'apartment',method:'built',offer_unit:1750}]};
assert.deepEqual(comparisonRows([apartment,apartmentReference,house],
  {property_type:'Departamento'},apartmentResult).map(row=>row.id),['apartment']);
const outerLand={...land,id:'outer-land'};
assert.deepEqual(comparisonRows([land,outerLand,house],{property_type:'Terreno'},
  result).map(row=>row.id),['land']);
console.log('Comparable cards: only used houses, apartments and lands; references and exclusions omitted.');

const apartmentParams={property_type:'Departamento',radius:500};
assert.equal(inMapRadius({...apartment,distance:499},apartmentParams,result,'property'),true);
assert.equal(inMapRadius({...apartment,distance:501},apartmentParams,result,'property'),false);
assert.equal(inMapRadius({...apartment,distance:501},apartmentParams,result,'property_reference'),false);
assert.equal(inMapRadius({...apartment,distance:null},apartmentParams,result,'property'),false);
assert.equal(mapRings(apartmentParams,{land_radius:2000},new Set(['property','land'])).length,1);
const houseParams={property_type:'Casa',radius:500},expandedResult={land_radius:1000};
assert.equal(mapRadius(houseParams,expandedResult,'land'),1000);
assert.equal(inMapRadius({...land,distance:900},houseParams,expandedResult,'land'),true);
assert.equal(inMapRadius({...land,distance:1100},houseParams,expandedResult,'land'),false);
assert.equal(inMapRadius({...outerLand,distance:900},houseParams,expandedResult,'other_reference'),false);
assert.equal(mapRings(houseParams,expandedResult,new Set(['property'])).length,1);
assert.deepEqual(mapRings(houseParams,expandedResult,new Set(['land'])).map(r=>r.radius),[500,1000]);
assert.equal(mapRings({property_type:'Terreno',radius:500},expandedResult,new Set(['land'])).length,1);
console.log('Map radii: target and reference pins stay in the selected radius; house soil uses its own labelled circle.');
