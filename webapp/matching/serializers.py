"""
Serializers para la app de matching.
"""

from rest_framework import serializers
from requerimientos.models import Requerimiento
from propifai.models import PropifaiProperty
from .models import MatchResult


class PropiedadSimpleSerializer(serializers.ModelSerializer):
    """Serializer simplificado para propiedades."""
    
    precio_formateado = serializers.CharField(read_only=True)
    tipo_propiedad = serializers.CharField(read_only=True)
    
    class Meta:
        model = PropifaiProperty
        fields = [
            'id', 'code', 'title', 'district', 'price', 'precio_formateado',
            'bedrooms', 'bathrooms', 'built_area', 'antiquity_years',
            'garage_spaces', 'ascensor', 'real_address', 'tipo_propiedad'
        ]


class RequerimientoSimpleSerializer(serializers.ModelSerializer):
    """Serializer simplificado para requerimientos."""
    
    distritos_lista = serializers.ListField(read_only=True)
    presupuesto_display = serializers.CharField(read_only=True)
    es_urgente = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Requerimiento
        fields = [
            'id', 'agente', 'condicion', 'tipo_propiedad', 'distritos',
            'distritos_lista', 'presupuesto_monto', 'presupuesto_moneda',
            'presupuesto_forma_pago', 'presupuesto_display', 'habitaciones',
            'banos', 'cochera', 'ascensor', 'amueblado', 'area_m2',
            'piso_preferencia', 'caracteristicas_extra', 'es_urgente'
        ]


class MatchResultSerializer(serializers.ModelSerializer):
    """Serializer para resultados de matching."""
    
    propiedad = PropiedadSimpleSerializer(read_only=True)
    requerimiento = RequerimientoSimpleSerializer(read_only=True)
    es_compatible = serializers.BooleanField(read_only=True)
    nivel_compatibilidad = serializers.CharField(read_only=True)
    
    class Meta:
        model = MatchResult
        fields = [
            'id', 'requerimiento', 'propiedad', 'score_total',
            'score_detalle', 'fase_eliminada', 'porcentaje_compatibilidad',
            'ejecutado_en', 'notificado_al_agente', 'notificado_en',
            'ranking', 'es_compatible', 'nivel_compatibilidad'
        ]
        read_only_fields = ['ejecutado_en', 'notificado_en']


class MatchingResultSerializer(serializers.Serializer):
    """
    Serializer para resultados de matching en tiempo real (no persistidos).
    """
    
    propiedad = PropiedadSimpleSerializer()
    score_total = serializers.DecimalField(max_digits=5, decimal_places=2)
    score_detalle = serializers.DictField()
    fase_eliminada = serializers.CharField(allow_null=True)
    porcentaje_compatibilidad = serializers.DecimalField(max_digits=5, decimal_places=2)
    ranking = serializers.IntegerField(required=False)
    
    class Meta:
        fields = [
            'propiedad', 'score_total', 'score_detalle',
            'fase_eliminada', 'porcentaje_compatibilidad', 'ranking'
        ]


class MatchingEstadisticasSerializer(serializers.Serializer):
    """
    Serializer para estadísticas del matching.
    """
    
    total_evaluadas = serializers.IntegerField()
    total_descartadas = serializers.IntegerField()
    total_compatibles = serializers.IntegerField()
    descartadas_por_campo = serializers.DictField()
    score_promedio = serializers.DecimalField(max_digits=5, decimal_places=2)
    propiedad_top = MatchingResultSerializer(allow_null=True)
    
    class Meta:
        fields = [
            'total_evaluadas', 'total_descartadas', 'total_compatibles',
            'descartadas_por_campo', 'score_promedio', 'propiedad_top'
        ]


class EjecutarMatchingSerializer(serializers.Serializer):
    """
    Serializer para solicitar ejecución de matching.
    """
    
    requerimiento_id = serializers.IntegerField()
    limite_propiedades = serializers.IntegerField(
        required=False,
        default=100,
        help_text='Límite de propiedades a evaluar (para performance)'
    )
    score_minimo = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        default=0,
        help_text='Score mínimo para incluir en resultados'
    )
    
    def validate_requerimiento_id(self, value):
        """Valida que el requerimiento exista."""
        try:
            Requerimiento.objects.get(id=value)
        except Requerimiento.DoesNotExist:
            raise serializers.ValidationError(f"Requerimiento con ID {value} no existe.")
        return value


class GuardarMatchingSerializer(serializers.Serializer):
    """
    Serializer para guardar resultados de matching.
    """
    
    requerimiento_id = serializers.IntegerField()
    resultados = MatchingResultSerializer(many=True)
    
    def validate_requerimiento_id(self, value):
        """Valida que el requerimiento exista."""
        try:
            Requerimiento.objects.get(id=value)
        except Requerimiento.DoesNotExist:
            raise serializers.ValidationError(f"Requerimiento con ID {value} no existe.")
        return value