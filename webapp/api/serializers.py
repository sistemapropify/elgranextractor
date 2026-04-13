"""
Serializers para la API REST del sistema de monitoreo web.

Este módulo define los serializers para convertir modelos Django
en representaciones JSON y viceversa.
"""

from rest_framework import serializers
from django.utils import timezone

from semillas.models import FuenteWeb
from captura.models import CapturaCruda, EventoDeteccion
from ingestas.models import PropiedadRaw
from propifai.models import PropifaiProperty


class FuenteWebSerializer(serializers.ModelSerializer):
    """Serializer para el modelo FuenteWeb."""
    
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    categoria_display = serializers.CharField(source='get_categoria_display', read_only=True)
    tipo_fuente_display = serializers.CharField(source='get_tipo_fuente_display', read_only=True)
    
    # Campos calculados
    tasa_exito = serializers.SerializerMethodField()
    tiempo_desde_ultima_captura = serializers.SerializerMethodField()
    necesita_revision = serializers.SerializerMethodField()
    
    class Meta:
        model = FuenteWeb
        fields = [
            'id', 'nombre', 'url', 'descripcion', 'categoria', 'categoria_display',
            'tipo_fuente', 'tipo_fuente_display', 'frecuencia_revision_minutos',
            'activa', 'estado', 'estado_display', 'descubierta_automaticamente',
            'contador_exitos', 'contador_errores', 'tiempo_respuesta_promedio',
            'ultima_captura_exitosa', 'ultimo_intento_captura',
            'fecha_creacion', 'fecha_actualizacion', 'fecha_descubrimiento',
            'tasa_exito', 'tiempo_desde_ultima_captura', 'necesita_revision',
            'metadatos_descubrimiento',
        ]
        read_only_fields = [
            'id', 'contador_exitos', 'contador_errores', 'tiempo_respuesta_promedio',
            'ultima_captura_exitosa', 'ultimo_intento_captura',
            'fecha_creacion', 'fecha_actualizacion', 'fecha_descubrimiento',
            'tasa_exito', 'tiempo_desde_ultima_captura', 'necesita_revision',
        ]
    
    def get_tasa_exito(self, obj):
        """Calcula la tasa de éxito de capturas."""
        total = obj.contador_exitos + obj.contador_errores
        if total == 0:
            return 0.0
        return (obj.contador_exitos / total) * 100
    
    def get_tiempo_desde_ultima_captura(self, obj):
        """Calcula el tiempo desde la última captura exitosa."""
        if not obj.ultima_captura_exitosa:
            return None
        
        delta = timezone.now() - obj.ultima_captura_exitosa.fecha_captura
        return {
            'dias': delta.days,
            'horas': delta.seconds // 3600,
            'minutos': (delta.seconds % 3600) // 60,
            'segundos': delta.seconds % 60,
            'total_segundos': delta.total_seconds(),
        }
    
    def get_necesita_revision(self, obj):
        """Determina si la fuente necesita revisión."""
        if not obj.activa or obj.estado != 'activa':
            return False
        
        if not obj.ultima_captura_exitosa:
            return True
        
        delta = timezone.now() - obj.ultima_captura_exitosa.fecha_captura
        frecuencia_segundos = obj.frecuencia_revision_minutos * 60
        
        return delta.total_seconds() >= frecuencia_segundos
    
    def validate_url(self, value):
        """Valida que la URL sea válida y accesible."""
        # Validación básica de URL
        if not value.startswith(('http://', 'https://')):
            raise serializers.ValidationError("La URL debe comenzar con http:// o https://")
        
        # Aquí se podría agregar validación más avanzada
        # como verificar que el dominio exista, etc.
        
        return value
    
    def validate_frecuencia_revision_minutos(self, value):
        """Valida la frecuencia de revisión."""
        if value < 5:
            raise serializers.ValidationError("La frecuencia mínima es 5 minutos")
        if value > 1440:  # 24 horas
            raise serializers.ValidationError("La frecuencia máxima es 1440 minutos (24 horas)")
        
        return value


class CapturaCrudaSerializer(serializers.ModelSerializer):
    """Serializer para el modelo CapturaCruda."""
    
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    fuente_nombre = serializers.CharField(source='fuente.nombre', read_only=True)
    fuente_url = serializers.CharField(source='fuente.url', read_only=True)
    
    # Campos calculados
    resumen_contenido = serializers.SerializerMethodField()
    tamaño_kb = serializers.SerializerMethodField()
    
    class Meta:
        model = CapturaCruda
        fields = [
            'id', 'fuente', 'fuente_nombre', 'fuente_url', 'fecha_captura',
            'estado', 'estado_display', 'status_code', 'content_type',
            'content_length', 'encoding', 'contenido_html', 'hash_sha256',
            'hash_simplificado', 'num_palabras', 'num_lineas', 'num_links',
            'tiempo_respuesta_ms', 'tamaño_bytes', 'tamaño_kb',
            'mensaje_error', 'stack_trace', 'resumen_contenido',
        ]
        read_only_fields = [
            'id', 'fecha_captura', 'hash_sha256', 'hash_simplificado',
            'num_palabras', 'num_lineas', 'num_links', 'tamaño_bytes',
            'resumen_contenido', 'tamaño_kb',
        ]
    
    def get_resumen_contenido(self, obj):
        """Genera un resumen del contenido HTML."""
        return obj.generar_resumen(max_length=200)
    
    def get_tamaño_kb(self, obj):
        """Convierte el tamaño a kilobytes."""
        if obj.tamaño_bytes:
            return obj.tamaño_bytes / 1024
        return 0
    
    def validate(self, data):
        """Valida los datos de la captura."""
        # Si es una captura exitosa, debe tener contenido HTML
        if data.get('estado') == 'exito' and not data.get('contenido_html'):
            raise serializers.ValidationError(
                "Las capturas exitosas deben tener contenido HTML"
            )
        
        return data


class PropiedadRawSerializer(serializers.ModelSerializer):
    """Serializer para el modelo PropiedadRaw."""
    
    # Campos calculados
    lat = serializers.SerializerMethodField()
    lng = serializers.SerializerMethodField()
    precio_m2 = serializers.SerializerMethodField()
    precio_m2_final = serializers.SerializerMethodField()
    imagen_url = serializers.SerializerMethodField()
    
    class Meta:
        model = PropiedadRaw
        fields = [
            'id', 'fuente_excel', 'fecha_ingesta', 'tipo_propiedad', 'subtipo_propiedad',
            'condicion', 'propiedad_verificada', 'precio_usd', 'descripcion', 'portal',
            'url_propiedad', 'coordenadas', 'departamento', 'provincia', 'distrito',
            'area_terreno', 'area_construida', 'numero_pisos', 'numero_habitaciones',
            'numero_banos', 'lat', 'lng', 'precio_m2', 'precio_m2_final', 'imagen_url'
        ]
    
    def get_lat(self, obj):
        """Extrae latitud de coordenadas."""
        if obj.coordenadas:
            try:
                parts = obj.coordenadas.split(',')
                if len(parts) >= 2:
                    return float(parts[0].strip())
            except (ValueError, AttributeError):
                pass
        return None
    
    def get_lng(self, obj):
        """Extrae longitud de coordenadas."""
        if obj.coordenadas:
            try:
                parts = obj.coordenadas.split(',')
                if len(parts) >= 2:
                    return float(parts[1].strip())
            except (ValueError, AttributeError):
                pass
        return None
    
    def get_precio_m2(self, obj):
        """Calcula precio por m² de construcción."""
        from acm.utils import calcular_precio_m2
        precio_info = calcular_precio_m2(obj)
        return precio_info.get('precio_m2')
    
    def get_precio_m2_final(self, obj):
        """Calcula precio final por m²."""
        from acm.utils import calcular_precio_m2
        precio_info = calcular_precio_m2(obj)
        return precio_info.get('precio_m2_final')
    
    def get_imagen_url(self, obj):
        """Obtiene URL de la primera imagen."""
        if hasattr(obj, 'primera_imagen'):
            return obj.primera_imagen()
        return None


class PropifaiPropertySerializer(serializers.ModelSerializer):
    """Serializer para el modelo PropifaiProperty."""
    
    # Campos calculados
    lat = serializers.SerializerMethodField()
    lng = serializers.SerializerMethodField()
    precio_m2 = serializers.SerializerMethodField()
    precio_m2_final = serializers.SerializerMethodField()
    tipo_propiedad = serializers.SerializerMethodField()
    
    class Meta:
        model = PropifaiProperty
        fields = [
            'id', 'code', 'codigo_unico_propiedad', 'title', 'description',
            'antiquity_years', 'delivery_date', 'price', 'maintenance_fee', 'has_maintenance',
            'floors', 'bedrooms', 'bathrooms', 'half_bathrooms', 'garage_spaces',
            'land_area', 'built_area', 'front_measure', 'depth_measure',
            'real_address', 'exact_address', 'coordinates', 'department', 'province', 'district',
            'urbanization', 'amenities', 'zoning', 'created_at', 'updated_at',
            'is_active', 'is_ready_for_sale', 'is_draft', 'is_project',
            'project_name', 'ascensor', 'availability_status', 'unit_location',
            'lat', 'lng', 'precio_m2', 'precio_m2_final', 'tipo_propiedad'
        ]
    
    def get_lat(self, obj):
        """Usa la propiedad latitude del modelo."""
        return obj.latitude
    
    def get_lng(self, obj):
        """Usa la propiedad longitude del modelo."""
        return obj.longitude
    
    def get_precio_m2(self, obj):
        """Calcula precio por m²."""
        if obj.price and obj.built_area and float(obj.built_area) > 0:
            try:
                return float(obj.price) / float(obj.built_area)
            except (ValueError, ZeroDivisionError):
                pass
        return None
    
    def get_precio_m2_final(self, obj):
        """Para Propifai, precio_m2_final es igual a precio_m2."""
        return self.get_precio_m2(obj)
    
    def get_tipo_propiedad(self, obj):
        """Determina tipo de propiedad."""
        if hasattr(obj, 'tipo_propiedad'):
            return obj.tipo_propiedad or 'Propiedad'
        elif obj.title:
            titulo_lower = obj.title.lower()
            if any(tipo in titulo_lower for tipo in ['casa', 'house']):
                return 'Casa'
            elif any(tipo in titulo_lower for tipo in ['departamento', 'apartamento', 'apartment']):
                return 'Departamento'
            elif any(tipo in titulo_lower for tipo in ['terreno', 'land', 'lote']):
                return 'Terreno'
            elif any(tipo in titulo_lower for tipo in ['oficina', 'office', 'local']):
                return 'Oficina'
        return 'Propiedad'


class EventoDeteccionSerializer(serializers.ModelSerializer):
    """Serializer para el modelo EventoDeteccion."""
    
    tipo_cambio_display = serializers.CharField(source='get_tipo_cambio_display', read_only=True)
    severidad_display = serializers.CharField(source='get_severidad_display', read_only=True)
    fuente_nombre = serializers.CharField(source='fuente.nombre', read_only=True)
    captura_anterior_id = serializers.IntegerField(source='captura_anterior.id', read_only=True)
    captura_nueva_id = serializers.IntegerField(source='captura_nueva.id', read_only=True)
    
    # Campos calculados
    es_significativo = serializers.SerializerMethodField()
    tiempo_desde_deteccion = serializers.SerializerMethodField()
    
    class Meta:
        model = EventoDeteccion
        fields = [
            'id', 'fuente', 'fuente_nombre', 'captura_anterior', 'captura_anterior_id',
            'captura_nueva', 'captura_nueva_id', 'fecha_deteccion',
            'tipo_cambio', 'tipo_cambio_display', 'severidad', 'severidad_display',
            'similitud_porcentaje', 'diferencia_palabras', 'diferencia_lineas',
            'diferencia_enlaces', 'hash_anterior', 'hash_nuevo',
            'resumen_cambio', 'fragmentos_cambiados', 'contexto_anterior',
            'contexto_nuevo', 'analizado_por_ia', 'etiquetas_automaticas',
            'es_significativo', 'tiempo_desde_deteccion',
        ]
        read_only_fields = [
            'id', 'fecha_deteccion', 'similitud_porcentaje', 'diferencia_palabras',
            'diferencia_lineas', 'diferencia_enlaces', 'hash_anterior', 'hash_nuevo',
            'resumen_cambio', 'es_significativo', 'tiempo_desde_deteccion',
        ]
    
    def get_es_significativo(self, obj):
        """Determina si el cambio es significativo."""
        return obj.severidad in ['alto', 'critico']
    
    def get_tiempo_desde_deteccion(self, obj):
        """Calcula el tiempo desde la detección."""
        delta = timezone.now() - obj.fecha_deteccion
        
        return {
            'dias': delta.days,
            'horas': delta.seconds // 3600,
            'minutos': (delta.seconds % 3600) // 60,
            'segundos': delta.seconds % 60,
            'total_segundos': delta.total_seconds(),
        }


class EstadisticasSerializer(serializers.Serializer):
    """Serializer para estadísticas del sistema."""
    
    total_fuentes = serializers.IntegerField()
    fuentes_activas = serializers.IntegerField()
    fuentes_inactivas = serializers.IntegerField()
    fuentes_error = serializers.IntegerField()
    
    total_capturas = serializers.IntegerField()
    capturas_exitosas = serializers.IntegerField()
    capturas_error = serializers.IntegerField()
    tasa_exito_capturas = serializers.FloatField()
    
    total_eventos = serializers.IntegerField()
    eventos_significativos = serializers.IntegerField()
    tasa_eventos_significativos = serializers.FloatField()
    
    capturas_ultimas_24h = serializers.IntegerField()
    eventos_ultimas_24h = serializers.IntegerField()
    
    tamaño_total_mb = serializers.FloatField()
    tamaño_promedio_kb = serializers.FloatField()
    
    fuentes_por_categoria = serializers.DictField(child=serializers.IntegerField())
    eventos_por_severidad = serializers.DictField(child=serializers.IntegerField())
    
    fecha_generacion = serializers.DateTimeField()


class TareaCelerySerializer(serializers.Serializer):
    """Serializer para información de tareas Celery."""
    
    id = serializers.CharField()
    nombre = serializers.CharField()
    estado = serializers.CharField()
    resultado = serializers.DictField(required=False)
    fecha_creacion = serializers.DateTimeField()
    fecha_finalizacion = serializers.DateTimeField(required=False)
    tiempo_ejecucion = serializers.FloatField(required=False)


class DescubrimientoRequestSerializer(serializers.Serializer):
    """Serializer para solicitudes de descubrimiento."""
    
    categoria = serializers.CharField(required=False)
    consulta = serializers.CharField(required=False)
    url_sitio = serializers.CharField(required=False)
    url_sitemap = serializers.CharField(required=False)
    limite = serializers.IntegerField(default=20, min_value=1, max_value=100)
    
    def validate(self, data):
        """Valida que al menos un método de descubrimiento esté especificado."""
        metodos = ['categoria', 'consulta', 'url_sitio', 'url_sitemap']
        if not any(data.get(metodo) for metodo in metodos):
            raise serializers.ValidationError(
                "Debe especificar al menos un método de descubrimiento "
                "(categoria, consulta, url_sitio o url_sitemap)"
            )
        
        return data