"""
Serializers para la app de matching.
"""

from rest_framework import serializers
from requerimientos.models import Requerimiento
from propifai.models import PropifaiProperty
from .models import MatchResult


class PropiedadSimpleSerializer(serializers.ModelSerializer):
    """Serializer simplificado para propiedades.
    
    NOTA: El precio se envía como 'price' (valor raw de BD) + 'currency_id' (1=USD, 2=PEN).
    El frontend debe usar formatPrice(price, currency_id) para mostrar correctamente.
    NO usar 'precio_formateado' del modelo porque fuerza S/. siempre.
    """
    
    tipo_propiedad = serializers.CharField(read_only=True)
    currency_symbol = serializers.SerializerMethodField()
    
    class Meta:
        model = PropifaiProperty
        fields = [
            'id', 'code', 'title', 'district', 'price',
            'bedrooms', 'bathrooms', 'built_area', 'antiquity_years',
            'garage_spaces', 'ascensor', 'real_address', 'tipo_propiedad',
            'imagen_url', 'currency_id', 'currency_symbol'
        ]
    
    def get_currency_symbol(self, obj):
        """Retorna el símbolo de moneda según currency_id."""
        if obj.currency_id == 1:
            return '$'
        elif obj.currency_id == 2:
            return 'S/'
        return ''


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
            'piso_preferencia', 'caracteristicas_extra', 'es_urgente',
            # Campos para WhatsApp
            'requerimiento', 'fecha', 'hora', 'agente_telefono',
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
    
    score_total = serializers.DecimalField(max_digits=5, decimal_places=2)
    score_detalle = serializers.DictField()
    fase_eliminada = serializers.CharField(allow_null=True)
    porcentaje_compatibilidad = serializers.DecimalField(max_digits=5, decimal_places=2)
    ranking = serializers.IntegerField(required=False)
    propiedad_id = serializers.IntegerField()
    propiedad_dict = serializers.DictField()
    
    def to_representation(self, instance):
        ret = super().to_representation(instance)
        prop_dict = instance.get('propiedad_dict', {})
        prop_id = prop_dict.get('id')
        # Build image URL from property_media (ruta relativa + Azure Storage base)
        image_url = None
        file_path = prop_dict.get('file')  # from property_media join
        if file_path:
            base_url = "https://propifymedia01.blob.core.windows.net/media"
            if file_path.startswith('/'):
                file_path = file_path[1:]
            image_url = f"{base_url}/{file_path}"
        # Fallback: construir desde code
        if not image_url and prop_dict.get('code'):
            base_url = "https://propifymedia01.blob.core.windows.net/media"
            image_url = f"{base_url}/{prop_dict['code']}.jpg"
        
        ret['propiedad'] = {
            'id': prop_id,
            'code': prop_dict.get('code'),
            'title': prop_dict.get('title'),
            'district': str(prop_dict.get('district_id') or ''),
            'price': prop_dict.get('price'),
            'currency_id': prop_dict.get('currency_id'),
            'bedrooms': prop_dict.get('bedrooms'),
            'bathrooms': prop_dict.get('bathrooms'),
            'built_area': prop_dict.get('built_area'),
            'antiquity_years': prop_dict.get('antiquity_years'),
            'garage_spaces': prop_dict.get('garage_spaces'),
            'ascensor': 'sí' if prop_dict.get('has_elevator') else 'no',
            'real_address': prop_dict.get('display_address') or prop_dict.get('map_address'),
            'tipo_propiedad': None,
            'imagen_url': image_url,
            'currency_symbol': '$' if prop_dict.get('currency_id') == 1 else 'S/',
        }
        return ret


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