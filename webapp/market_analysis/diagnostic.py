#!/usr/bin/env python
"""
Endpoint de diagnóstico para verificar la lógica de terrenos.
"""
from django.http import JsonResponse
from django.views import View
from ingestas.models import PropiedadRaw
from propifai.models import PropifaiProperty

class DiagnosticView(View):
    def get(self, request):
        """Verifica la lógica de cálculo de terrenos"""
        # Probar con un terreno conocido
        terreno = PropiedadRaw.objects.filter(
            tipo_propiedad__icontains='terreno',
            coordenadas__isnull=False
        ).exclude(coordenadas='').first()
        
        if not terreno:
            return JsonResponse({'error': 'No se encontraron terrenos'}, status=404)
        
        # Simular lógica de heatmap_view
        tipo_propiedad = (terreno.tipo_propiedad or '').lower().strip()
        es_terreno = any(term in tipo_propiedad for term in [
            'terreno', 'terrenos', 'lote', 'parcela', 'parcel',
            'land', 'lot', 'plot', 'ground', 'solar', 'vacant'
        ])
        
        area = None
        if es_terreno:
            if terreno.area_terreno and terreno.area_terreno > 0:
                area = float(terreno.area_terreno)
        else:
            if terreno.area_construida and terreno.area_construida > 0:
                area = float(terreno.area_construida)
            elif terreno.area_terreno and terreno.area_terreno > 0:
                area = float(terreno.area_terreno)
        
        precio_m2 = None
        if area and terreno.precio_usd and terreno.precio_usd > 0:
            precio_m2 = float(terreno.precio_usd) / area
        
        return JsonResponse({
            'id': terreno.id,
            'tipo_propiedad': terreno.tipo_propiedad,
            'es_terreno_detectado': es_terreno,
            'area_construida': terreno.area_construida,
            'area_terreno': terreno.area_terreno,
            'area_usada': area,
            'precio_usd': terreno.precio_usd,
            'precio_m2_calculado': precio_m2,
            'logica_correcta': es_terreno and area == terreno.area_terreno
        })