from rest_framework import serializers
from .models import ZonaValor, PropiedadValoracion, EstadisticaZona, HistorialPrecioZona
from ingestas.models import PropiedadRaw


class ZonaValorSerializer(serializers.ModelSerializer):
    """Serializer para ZonaValor incluyendo cálculo de área y estadísticas."""
    
    parent_nombre = serializers.CharField(source='parent.nombre_zona', read_only=True)
    nivel_display = serializers.CharField(source='get_nivel_display', read_only=True)
    
    class Meta:
        model = ZonaValor
        fields = [
            'id', 'nombre_zona', 'descripcion', 'coordenadas',
            'area_total', 'precio_promedio_m2', 'desviacion_estandar_m2',
            'cantidad_propiedades_analizadas', 'fecha_creacion', 'fecha_actualizacion',
            'activo', 'color_fill', 'color_borde', 'opacidad',
            'nivel', 'nivel_display', 'parent', 'parent_nombre', 'codigo', 'nombre_oficial'
        ]
        read_only_fields = [
            'area_total', 'precio_promedio_m2', 'desviacion_estandar_m2',
            'cantidad_propiedades_analizadas', 'fecha_creacion', 'fecha_actualizacion',
            'nivel_display', 'parent_nombre'
        ]
    
    def validate_coordenadas(self, value):
        """Validar que las coordenadas formen un polígono válido o estén vacías."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Las coordenadas deben ser una lista de puntos.")
        
        # Permitir lista vacía para zonas jerárquicas sin polígono definido
        if len(value) == 0:
            return value
            
        if len(value) < 3:
            raise serializers.ValidationError("Un polígono debe tener al menos 3 puntos.")
        for point in value:
            if not isinstance(point, list) or len(point) != 2:
                raise serializers.ValidationError("Cada punto debe ser una lista [lat, lng].")
            lat, lng = point
            if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                raise serializers.ValidationError(f"Coordenadas inválidas: lat={lat}, lng={lng}")
        return value


class PropiedadValoracionSerializer(serializers.ModelSerializer):
    """Serializer para PropiedadValoracion."""
    
    propiedad_direccion = serializers.CharField(source='propiedad.direccion', read_only=True)
    propiedad_tipo = serializers.CharField(source='propiedad.tipo_propiedad', read_only=True)
    zona_nombre = serializers.CharField(source='zona.nombre_zona', read_only=True)
    
    class Meta:
        model = PropiedadValoracion
        fields = [
            'id', 'propiedad', 'propiedad_direccion', 'propiedad_tipo',
            'zona', 'zona_nombre', 'precio_m2', 'precio_venta', 'metros_cuadrados',
            'es_comparable', 'factor_ajuste', 'fecha_calculo', 'metodo_calculo'
        ]
        read_only_fields = ['fecha_calculo']


class EstadisticaZonaSerializer(serializers.ModelSerializer):
    """Serializer para EstadisticaZona."""
    
    class Meta:
        model = EstadisticaZona
        fields = [
            'id', 'zona', 'tipo_propiedad', 'cantidad_propiedades',
            'precio_promedio_m2', 'precio_mediano_m2', 'precio_minimo_m2',
            'precio_maximo_m2', 'desviacion_estandar', 'habitaciones_promedio',
            'banos_promedio', 'antiguedad_promedio', 'metros_cuadrados_promedio',
            'fecha_actualizacion'
        ]
        read_only_fields = ['fecha_actualizacion']


class HistorialPrecioZonaSerializer(serializers.ModelSerializer):
    """Serializer para HistorialPrecioZona."""
    
    class Meta:
        model = HistorialPrecioZona
        fields = [
            'id', 'zona', 'fecha_registro', 'precio_promedio_m2',
            'cantidad_propiedades', 'desviacion_estandar', 'fuente_datos'
        ]


class EstimacionRequestSerializer(serializers.Serializer):
    """Serializer para solicitud de estimación de precio."""
    
    lat = serializers.FloatField(required=True, min_value=-90, max_value=90)
    lng = serializers.FloatField(required=True, min_value=-180, max_value=180)
    metros_cuadrados = serializers.DecimalField(required=True, max_digits=10, decimal_places=2, min_value=1)
    habitaciones = serializers.IntegerField(required=False, min_value=0, default=0)
    banos = serializers.IntegerField(required=False, min_value=0, default=0)
    antiguedad = serializers.IntegerField(required=False, min_value=0, default=0)
    tipo_propiedad = serializers.ChoiceField(
        required=False,
        choices=['casa', 'departamento', 'terreno', 'local', 'oficina', 'otro'],
        default='casa'
    )
    
    def validate(self, data):
        """Validación adicional."""
        if data['metros_cuadrados'] <= 0:
            raise serializers.ValidationError("Los metros cuadrados deben ser positivos.")
        return data


class EstimacionResponseSerializer(serializers.Serializer):
    """Serializer para respuesta de estimación de precio."""
    
    precio_estimado = serializers.DecimalField(max_digits=15, decimal_places=2)
    rango_min = serializers.DecimalField(max_digits=15, decimal_places=2)
    rango_max = serializers.DecimalField(max_digits=15, decimal_places=2)
    nivel_confianza = serializers.FloatField(min_value=0, max_value=1)
    zona = serializers.CharField()
    comparables_utilizados = serializers.IntegerField()
    precio_base_m2 = serializers.DecimalField(max_digits=15, decimal_places=2)
    detalles = serializers.DictField(required=False)


class PuntoEnPoligonoRequestSerializer(serializers.Serializer):
    """Serializer para verificar si un punto está dentro de un polígono."""
    
    lat = serializers.FloatField(required=True)
    lng = serializers.FloatField(required=True)
    zona_id = serializers.IntegerField(required=False)


class ZonaEstadisticasSerializer(serializers.Serializer):
    """Serializer para estadísticas detalladas de una zona."""
    
    zona = ZonaValorSerializer()
    estadisticas_por_tipo = EstadisticaZonaSerializer(many=True)
    historial_precios = HistorialPrecioZonaSerializer(many=True)
    propiedades_recientes = PropiedadValoracionSerializer(many=True)