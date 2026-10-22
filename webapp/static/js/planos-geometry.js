/* GeoJSON input validation; no CAD interpretation or coordinate guessing. */
(function(root){
  'use strict';
  const depths={Point:0,MultiPoint:1,LineString:1,MultiLineString:2,Polygon:2,MultiPolygon:3};
  function normalize(value){
    if(!value||value.type!=='FeatureCollection'||!Array.isArray(value.features)||!value.features.length)throw Error('El archivo debe contener una colección GeoJSON con elementos.');
    if(value.features.length>25000)throw Error('El plano supera 25.000 elementos. Divídelo por capas para abrirlo en esta versión.');
    if(value.crs&&!/CRS84|EPSG(?::|::|\/0\/|%3A)4326$/i.test(String(value.crs.properties?.name||'')))throw Error('Convierte el archivo a WGS84 (EPSG:4326) antes de abrirlo.');
    let vertices=0;
    function coordinates(values,depth){
      if(!Array.isArray(values)||!values.length)throw Error('El plano contiene geometrías vacías.');
      if(depth){values.forEach(item=>coordinates(item,depth-1));return;}
      if(values.length<2||!values.every(Number.isFinite)||Math.abs(values[0])>180||Math.abs(values[1])>90)throw Error('Las coordenadas no son longitud / latitud WGS84. Revisa la georreferenciación.');
      if(++vertices>300000)throw Error('El plano supera 300.000 vértices. Simplifica o divide sus capas.');
    }
    const features=value.features.map((feature,index)=>{
      if(!feature||feature.type!=='Feature'||!feature.geometry||!Object.hasOwn(depths,feature.geometry.type))throw Error('El plano contiene un tipo de geometría no compatible.');
      const geometry=feature.geometry;
      coordinates(geometry.coordinates,depths[geometry.type]);
      const lines=geometry.type==='LineString'?[geometry.coordinates]:geometry.type==='MultiLineString'?geometry.coordinates:[];
      if(lines.some(line=>line.length<2))throw Error('Una línea debe contener al menos dos puntos.');
      const rings=geometry.type==='Polygon'?geometry.coordinates:geometry.type==='MultiPolygon'?geometry.coordinates.flat():[];
      if(rings.some(ring=>ring.length<4||ring[0][0]!==ring.at(-1)[0]||ring[0][1]!==ring.at(-1)[1]))throw Error('El plano contiene un polígono abierto o incompleto.');
      const properties=feature.properties&&typeof feature.properties==='object'&&!Array.isArray(feature.properties)?feature.properties:{};
      return {type:'Feature',id:index,geometry,properties:{...properties}};
    });
    return {type:'FeatureCollection',features};
  }
  function layerName(feature){const p=feature.properties;return String(p.capa??p.Layer??p.layer??p.CAPA??'Sin capa').slice(0,180)||'Sin capa';}
  function positions(geometry){const result=[];function visit(item){if(typeof item[0]==='number'){result.push(item);return;}item.forEach(visit);}visit(geometry.coordinates);return result;}
  const api={normalize,layerName,positions};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.PlanosGeometry=api;
})(typeof window==='undefined'?{}:window);
