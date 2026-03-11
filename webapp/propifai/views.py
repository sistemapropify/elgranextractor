from django.shortcuts import render
from django.views.generic import ListView
from django.db.models import Q
from .models import PropifaiProperty

class ListaPropiedadesPropifyView(ListView):
    """Vista para mostrar solo propiedades de la base de datos Propify."""
    model = PropifaiProperty
    template_name = 'propifai/lista_propiedades_propify_rediseno.html'
    context_object_name = 'propiedades'
    paginate_by = 12
    
    def get_queryset(self):
        """Aplicar filtros basados en parámetros GET."""
        queryset = super().get_queryset()
        
        # Obtener parámetros de filtro de la URL
        tipo_propiedad = self.request.GET.get('tipo_propiedad')
        departamento = self.request.GET.get('departamento')
        precio_min = self.request.GET.get('precio_min')
        precio_max = self.request.GET.get('precio_max')
        habitaciones = self.request.GET.get('habitaciones')
        banios = self.request.GET.get('banios')
        
        # Aplicar filtros si existen
        if tipo_propiedad:
            queryset = queryset.filter(tipo_propiedad__icontains=tipo_propiedad)
        
        if departamento:
            queryset = queryset.filter(department__icontains=departamento)
        
        if precio_min:
            try:
                precio_min_float = float(precio_min)
                queryset = queryset.filter(price__gte=precio_min_float)
            except (ValueError, TypeError):
                pass
        
        if precio_max:
            try:
                precio_max_float = float(precio_max)
                queryset = queryset.filter(price__lte=precio_max_float)
            except (ValueError, TypeError):
                pass
        
        if habitaciones:
            try:
                habitaciones_int = int(habitaciones)
                queryset = queryset.filter(bedrooms=habitaciones_int)
            except (ValueError, TypeError):
                pass
        
        if banios:
            try:
                banios_int = int(banios)
                queryset = queryset.filter(bathrooms=banios_int)
            except (ValueError, TypeError):
                pass
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtener TODAS las propiedades (sin paginación) para el mapa y conteo
        todas_las_propiedades = PropifaiProperty.objects.all()
        
        # Aplicar los mismos filtros a todas las propiedades para el mapa
        queryset_filtrado = self.get_queryset()
        
        # Calcular propiedades con coordenadas válidas
        propiedades_con_coordenadas = 0
        for propiedad in todas_las_propiedades:
            # Extraer coordenadas del campo coordinates
            if propiedad.coordinates:
                propiedades_con_coordenadas += 1
        
        # Agregar información adicional al contexto
        context['total_propiedades'] = todas_las_propiedades.count()
        context['propiedades_con_coordenadas'] = propiedades_con_coordenadas
        context['titulo'] = 'Propiedades Propify'
        
        # Obtener valores únicos para los filtros
        context['departamentos'] = PropifaiProperty.objects.values_list('department', flat=True).distinct().order_by('department')
        
        # Convertir TODAS las propiedades a formato compatible para el mapa
        todas_propiedades_compatibles = []
        for propiedad in todas_las_propiedades:
            # Extraer coordenadas del campo coordinates (formato: "lat,lng")
            lat = None
            lng = None
            if propiedad.coordinates:
                try:
                    coords = propiedad.coordinates.split(',')
                    if len(coords) >= 2:
                        lat = float(coords[0].strip())
                        lng = float(coords[1].strip())
                except (ValueError, AttributeError):
                    pass
            
            # Obtener nombres mapeados de ubicación
            departamento_nombre = propiedad.departamento_nombre if hasattr(propiedad, 'departamento_nombre') else propiedad.department
            provincia_nombre = propiedad.provincia_nombre if hasattr(propiedad, 'provincia_nombre') else propiedad.province
            distrito_nombre = propiedad.distrito_nombre if hasattr(propiedad, 'distrito_nombre') else propiedad.district
            ubicacion_completa = propiedad.ubicacion_completa if hasattr(propiedad, 'ubicacion_completa') else f"{distrito_nombre}, {provincia_nombre}, {departamento_nombre}"
            
            # Crear diccionario compatible con el nuevo template
            propiedad_dict = {
                'id': propiedad.id,
                'id_externo': propiedad.id,
                'es_externo': True,
                'es_propify': True,
                'tipo': 'Propiedad',  # Valor por defecto
                'tipo_propiedad': 'Propiedad',  # Para filtros
                'precio': float(propiedad.price) if propiedad.price else None,
                'precio_usd': float(propiedad.price) if propiedad.price else None,
                'departamento': propiedad.department,  # Índice original
                'departamento_nombre': departamento_nombre,  # Nombre mapeado
                'provincia': propiedad.province,  # Índice original
                'provincia_nombre': provincia_nombre,  # Nombre mapeado
                'distrito': propiedad.district,  # Índice original
                'distrito_nombre': distrito_nombre,  # Nombre mapeado
                'ubicacion_completa': ubicacion_completa,  # Ubicación completa formateada
                'latitud': lat,
                'longitud': lng,
                'lat': lat,
                'lng': lng,
                'habitaciones': propiedad.bedrooms,
                'banios': propiedad.bathrooms,
                'area_construida': float(propiedad.built_area) if propiedad.built_area else None,
                'area_terreno': float(propiedad.land_area) if propiedad.land_area else None,
                'imagen_url': propiedad.imagen_url,
                'primera_imagen': propiedad.primera_imagen_url,
                'imagen_principal': propiedad.imagen_url,
                'url_propiedad': None,
                'fuente': 'Propify DB',
                'fecha_publicacion': propiedad.created_at,
                'fecha_ingesta': propiedad.created_at,
                'area': float(propiedad.built_area) if propiedad.built_area else float(propiedad.land_area) if propiedad.land_area else None,
                'titulo': f"{propiedad.title or 'Propiedad'} en {departamento_nombre or propiedad.department or ''}",
                'codigo': propiedad.code,
                'direccion': propiedad.real_address or propiedad.exact_address,
                'descripcion': propiedad.description,
            }
            todas_propiedades_compatibles.append(propiedad_dict)
        
        # Convertir solo las propiedades de la página actual para la lista
        propiedades_pagina_compatibles = []
        for propiedad in context['object_list']:
            # Extraer coordenadas
            lat = None
            lng = None
            if propiedad.coordinates:
                try:
                    coords = propiedad.coordinates.split(',')
                    if len(coords) >= 2:
                        lat = float(coords[0].strip())
                        lng = float(coords[1].strip())
                except (ValueError, AttributeError):
                    pass
            
            # Obtener nombres mapeados de ubicación
            departamento_nombre = propiedad.departamento_nombre if hasattr(propiedad, 'departamento_nombre') else propiedad.department
            provincia_nombre = propiedad.provincia_nombre if hasattr(propiedad, 'provincia_nombre') else propiedad.province
            distrito_nombre = propiedad.distrito_nombre if hasattr(propiedad, 'distrito_nombre') else propiedad.district
            ubicacion_completa = propiedad.ubicacion_completa if hasattr(propiedad, 'ubicacion_completa') else f"{distrito_nombre}, {provincia_nombre}, {departamento_nombre}"
            
            propiedad_dict = {
                'id': propiedad.id,
                'id_externo': propiedad.id,
                'es_externo': True,
                'es_propify': True,
                'tipo': 'Propiedad',
                'tipo_propiedad': 'Propiedad',
                'precio': float(propiedad.price) if propiedad.price else None,
                'precio_usd': float(propiedad.price) if propiedad.price else None,
                'departamento': propiedad.department,  # Índice original
                'departamento_nombre': departamento_nombre,  # Nombre mapeado
                'provincia': propiedad.province,  # Índice original
                'provincia_nombre': provincia_nombre,  # Nombre mapeado
                'distrito': propiedad.district,  # Índice original
                'distrito_nombre': distrito_nombre,  # Nombre mapeado
                'ubicacion_completa': ubicacion_completa,  # Ubicación completa formateada
                'latitud': lat,
                'longitud': lng,
                'lat': lat,
                'lng': lng,
                'habitaciones': propiedad.bedrooms,
                'banios': propiedad.bathrooms,
                'area_construida': float(propiedad.built_area) if propiedad.built_area else None,
                'area_terreno': float(propiedad.land_area) if propiedad.land_area else None,
                'imagen_url': propiedad.imagen_url,
                'primera_imagen': propiedad.primera_imagen_url,
                'imagen_principal': propiedad.imagen_url,
                'url_propiedad': None,
                'fuente': 'Propify DB',
                'fecha_publicacion': propiedad.created_at,
                'fecha_ingesta': propiedad.created_at,
                'area': float(propiedad.built_area) if propiedad.built_area else float(propiedad.land_area) if propiedad.land_area else None,
                'titulo': f"{propiedad.title or 'Propiedad'} en {departamento_nombre or propiedad.department or ''}",
                'codigo': propiedad.code,
                'direccion': propiedad.real_address or propiedad.exact_address,
                'descripcion': propiedad.description,
            }
            propiedades_pagina_compatibles.append(propiedad_dict)
        
        # Pasar ambas listas al contexto
        context['propiedades'] = propiedades_pagina_compatibles  # Para la lista paginada
        context['propiedades_compatibles'] = propiedades_pagina_compatibles  # Para compatibilidad
        context['todas_las_propiedades'] = todas_propiedades_compatibles  # Para el mapa
        
        # Pasar parámetros actuales para mantener filtros en la paginación
        context['parametros_filtro'] = self.request.GET.copy()
        if 'page' in context['parametros_filtro']:
            del context['parametros_filtro']['page']
        
        return context

def lista_propiedades_propify_simple(request):
    """Vista simple para propiedades Propify."""
    propiedades = PropifaiProperty.objects.all()
    
    # Convertir a formato compatible
    propiedades_compatibles = []
    for propiedad in propiedades:
        lat = propiedad.latitude
        lng = propiedad.longitude
        
        propiedad_dict = {
            'id': propiedad.id,
            'id_externo': propiedad.id,
            'es_externo': True,
            'es_propify': True,
            'tipo': propiedad.tipo_propiedad,
            'tipo_propiedad': propiedad.tipo_propiedad,
            'precio': float(propiedad.price) if propiedad.price else None,
            'precio_usd': float(propiedad.price) if propiedad.price else None,
            'departamento': propiedad.department,
            'provincia': propiedad.province,
            'distrito': propiedad.district,
            'latitud': lat,
            'longitud': lng,
            'lat': lat,
            'lng': lng,
            'habitaciones': propiedad.bedrooms,
            'banios': propiedad.bathrooms,
            'area_construida': float(propiedad.built_area) if propiedad.built_area else None,
            'area_terreno': float(propiedad.land_area) if propiedad.land_area else None,
            'imagen_url': propiedad.imagen_url,  # Usar la propiedad imagen_url del modelo
            'primera_imagen': propiedad.primera_imagen_url,  # Usar primera_imagen_url para primera imagen
            'imagen_principal': propiedad.imagen_url,  # Usar imagen_url para imagen principal
            'url_propiedad': None,
            'fuente': 'Propify DB',
            'fecha_publicacion': propiedad.created_at,
            'fecha_ingesta': propiedad.created_at,
            'area': float(propiedad.built_area) if propiedad.built_area else float(propiedad.land_area) if propiedad.land_area else None,
            'titulo': f"{propiedad.title or 'Propiedad'} en {propiedad.department or ''}",
            'codigo': propiedad.code,
            'direccion': propiedad.real_address or propiedad.exact_address,
            'descripcion': propiedad.description,
        }
        propiedades_compatibles.append(propiedad_dict)
    
    context = {
        'propiedades': propiedades_compatibles,  # Usar la versión compatible
        'propiedades_compatibles': propiedades_compatibles,
        'total_propiedades': len(propiedades_compatibles),
        'titulo': 'Propiedades Propify',
    }
    
    return render(request, 'propifai/lista_propiedades_propify_simple.html', context)


def vista_propiedades_simple_html(request):
    """Vista simple HTML para propiedades Propify."""
    propiedades = PropifaiProperty.objects.all()
    
    # Convertir a formato compatible
    propiedades_compatibles = []
    for propiedad in propiedades:
        lat = propiedad.latitude
        lng = propiedad.longitude
        
        propiedad_dict = {
            'id': propiedad.id,
            'tipo_propiedad': propiedad.tipo_propiedad,
            'precio_usd': float(propiedad.price) if propiedad.price else None,
            'departamento': propiedad.department,
            'provincia': propiedad.province,
            'distrito': propiedad.district,
            'lat': lat,
            'lng': lng,
            'habitaciones': propiedad.bedrooms,
            'banios': propiedad.bathrooms,
            'area_construida': float(propiedad.built_area) if propiedad.built_area else None,
            'area_terreno': float(propiedad.land_area) if propiedad.land_area else None,
            'codigo': propiedad.code,
            'direccion': propiedad.real_address or propiedad.exact_address,
            'descripcion': propiedad.description,
        }
        propiedades_compatibles.append(propiedad_dict)
    
    context = {
        'propiedades': propiedades_compatibles,
        'total_count': len(propiedades_compatibles),
    }
    
    return render(request, 'propifai/propiedades_simple.html', context)


def api_propiedades_json(request):
    """API JSON para propiedades Propify."""
    from django.http import JsonResponse
    propiedades = PropifaiProperty.objects.all()
    
    # Convertir a formato compatible
    propiedades_compatibles = []
    for propiedad in propiedades:
        lat = propiedad.latitude
        lng = propiedad.longitude
        
        propiedad_dict = {
            'id': propiedad.id,
            'tipo_propiedad': propiedad.tipo_propiedad,
            'precio_usd': float(propiedad.price) if propiedad.price else None,
            'departamento': propiedad.department,
            'provincia': propiedad.province,
            'distrito': propiedad.district,
            'lat': lat,
            'lng': lng,
            'habitaciones': propiedad.bedrooms,
            'banios': propiedad.bathrooms,
            'area_construida': float(propiedad.built_area) if propiedad.built_area else None,
            'area_terreno': float(propiedad.land_area) if propiedad.land_area else None,
            'codigo': propiedad.code,
            'direccion': propiedad.real_address or propiedad.exact_address,
            'descripcion': propiedad.description,
        }
        propiedades_compatibles.append(propiedad_dict)
    
    return JsonResponse({
        'properties': propiedades_compatibles,
        'total_count': len(propiedades_compatibles),
        'success': True,
    })
