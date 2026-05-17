from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

from .utils import haversine, calcular_precio_m2, calcular_promedio_ponderado
from ingestas.models import PropiedadRaw


def _tipo_desde_titulo(titulo):
    t = (titulo or '').lower()
    if any(k in t for k in ['casa', 'house']):
        return 'Casa'
    if any(k in t for k in ['departamento', 'apartamento', 'apartment']):
        return 'Departamento'
    if any(k in t for k in ['terreno', 'land', 'lote']):
        return 'Terreno'
    if any(k in t for k in ['oficina', 'office', 'local']):
        return 'Oficina'
    return 'Propiedad'


class CalcularACMAPIView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data
        propiedades = data.get('propiedades', [])
        area_m2 = data.get('area_m2')

        if not propiedades:
            return Response({'error': 'propiedades es requerido y no puede estar vacío'}, status=status.HTTP_400_BAD_REQUEST)
        if area_m2 is None:
            return Response({'error': 'area_m2 es requerido'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            area_m2 = float(area_m2)
        except (ValueError, TypeError):
            return Response({'error': 'area_m2 debe ser un número'}, status=status.HTTP_400_BAD_REQUEST)

        stats = calcular_promedio_ponderado(propiedades)

        if stats['total'] == 0:
            return Response({'error': 'Ninguna propiedad tiene precio_m2 válido'}, status=status.HTTP_400_BAD_REQUEST)

        promedio_ponderado = stats['promedio_ponderado']
        valor_comercial = area_m2 * promedio_ponderado

        return Response({
            'precio_min_m2': round(stats['min'], 2),
            'precio_max_m2': round(stats['max'], 2),
            'precio_promedio_m2': round(stats['promedio_simple'], 2),
            'precio_promedio_ponderado_m2': round(promedio_ponderado, 2),
            'valor_comercial': round(valor_comercial, 2),
            'precio_venta_sugerido': round(valor_comercial * 0.9499, 2),
            'valor_realizacion': round(valor_comercial * 0.90, 2),
            'num_comparables': stats['total'],
        })


class ComparablesAPIView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):
        lat = request.data.get('lat')
        lng = request.data.get('lng')

        if lat is None or lng is None:
            return Response({'error': 'lat y lng son requeridos'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            lat = float(lat)
            lng = float(lng)
        except (ValueError, TypeError):
            return Response({'error': 'Coordenadas inválidas'}, status=status.HTTP_400_BAD_REQUEST)

        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            return Response({'error': 'Coordenadas fuera de rango'}, status=status.HTTP_400_BAD_REQUEST)

        radio = float(request.data.get('radio', 500))
        tipo_propiedad = request.data.get('tipo_propiedad', '').strip()

        comparables = []

        # Propiedades locales 
        qs = PropiedadRaw.objects.exclude(coordenadas__isnull=True).exclude(coordenadas='')
        if tipo_propiedad:
            qs = qs.filter(Q(tipo_propiedad__iexact=tipo_propiedad))

        for prop in qs:
            if prop.lat is None or prop.lng is None:
                continue
            distancia = haversine(lat, lng, prop.lat, prop.lng)
            if distancia > radio:
                continue
            precio_m2_info = calcular_precio_m2(prop)
            if not precio_m2_info.get('precio_m2') and not precio_m2_info.get('precio_m2_final'):
                continue
            comparables.append({
                'id': prop.id,
                'lat': prop.lat,
                'lng': prop.lng,
                'tipo': prop.tipo_propiedad or 'No especificado',
                'precio': float(prop.precio_usd) if prop.precio_usd else None,
                'precio_final': float(prop.precio_final_venta) if prop.precio_final_venta else None,
                'metros_construccion': float(prop.area_construida) if prop.area_construida else None,
                'metros_terreno': float(prop.area_terreno) if prop.area_terreno else None,
                'habitaciones': prop.numero_habitaciones,
                'banos': prop.numero_banos,
                'distrito': prop.distrito or '',
                'provincia': prop.provincia or '',
                'departamento': prop.departamento or '',
                'imagen_url': prop.primera_imagen(),
                'precio_m2': precio_m2_info.get('precio_m2'),
                'precio_m2_final': precio_m2_info.get('precio_m2_final'),
                'distancia_metros': round(distancia, 2),
                'fuente': 'local',
            })

        # Propiedades Propifai
        try:
            from propifai.models import PropifaiProperty
            from propifai.mapeo_ubicaciones import DEPARTAMENTOS, PROVINCIAS, DISTRITOS

            for prop in PropifaiProperty.objects.using('propifai').all():
                if prop.latitude is None or prop.longitude is None:
                    continue
                distancia = haversine(lat, lng, float(prop.latitude), float(prop.longitude))
                if distancia > radio:
                    continue
                tipo_val = _tipo_desde_titulo(prop.title)
                if tipo_propiedad and tipo_val.lower() != tipo_propiedad.lower():
                    continue
                if not prop.price:
                    continue
                area = (
                    float(prop.built_area) if prop.built_area and float(prop.built_area) > 0
                    else float(prop.land_area) if prop.land_area and float(prop.land_area) > 0
                    else None
                )
                precio_m2 = float(prop.price) / area if area else None
                comparables.append({
                    'id': prop.id,
                    'lat': float(prop.latitude),
                    'lng': float(prop.longitude),
                    'tipo': tipo_val,
                    'precio': float(prop.price),
                    'precio_final': float(prop.price),
                    'metros_construccion': float(prop.built_area) if prop.built_area else None,
                    'metros_terreno': float(prop.land_area) if prop.land_area else None,
                    'habitaciones': prop.bedrooms,
                    'banos': prop.bathrooms,
                    'distrito': DISTRITOS.get(str(prop.district), '') if prop.district else '',
                    'provincia': PROVINCIAS.get(str(prop.province), '') if prop.province else '',
                    'departamento': DEPARTAMENTOS.get(str(prop.department), '') if prop.department else '',
                    'imagen_url': prop.imagen_url,
                    'precio_m2': precio_m2,
                    'precio_m2_final': precio_m2,
                    'distancia_metros': round(distancia, 2),
                    'fuente': 'propifai',
                    'codigo': prop.code,
                    'titulo': prop.title,
                })
        except Exception:
            pass

        comparables.sort(key=lambda x: x['distancia_metros'])
        return Response({'total': len(comparables), 'comparables': comparables})
