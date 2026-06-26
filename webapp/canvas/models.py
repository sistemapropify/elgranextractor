"""
Modelos del módulo canvas (PropFlow Visual Canvas).

Tres modelos principales:
- CardTemplate: configuración de campos visibles para tarjetas de propiedades
- Lienzo: lienzo guardado con snapshot completo del canvas
- NotaLienzo: notas sticky persistentes dentro de un lienzo
"""

from django.db import models
from django.conf import settings


class CardTemplate(models.Model):
    """
    Configuración de campos visibles para las tarjetas de propiedades.
    El usuario define qué campos quiere ver en el lienzo.
    """
    user      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    nombre    = models.CharField(max_length=100)
    campos    = models.JSONField(default=list)
    # Ejemplo campos: ["title", "price", "district_name", "property_type_name", "bedrooms"]
    # Los nombres de campo están en INGLÉS (reales de field_values en propiedadespropify).
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado_en']

    def __str__(self):
        return f"{self.nombre} ({self.user})"


class Lienzo(models.Model):
    """
    Un lienzo guardado por el usuario.
    Contiene el estado completo del canvas: posiciones, conexiones, notas.
    """
    ESTADO_CHOICES = [
        ('activo',    'Activo'),
        ('archivado', 'Archivado'),
    ]

    user           = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    nombre         = models.CharField(max_length=200)
    descripcion    = models.TextField(blank=True)
    estado         = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='activo')
    card_template  = models.ForeignKey(CardTemplate, null=True, blank=True, on_delete=models.SET_NULL)
    snapshot       = models.JSONField(default=dict)
    # Estructura snapshot:
    # {
    #   "nodos": [
    #     {
    #       "id": "prop_123",
    #       "tipo": "propiedad",       # | "requerimiento" | "nota"
    #       "ref_id": 123,             # source_id del IntelligenceDocument (propiedadespropify) o pk de Requerimiento
    #       "x": 340, "y": 210,
    #       "width": 220, "height": 160,
    #       "collapsed": false,
    #       "color": null              # override de color para notas
    #     }
    #   ],
    #   "aristas": [
    #     {
    #       "id": "e1",
    #       "origen": "prop_123",
    #       "destino": "req_45",
    #       "tipo": "match",           # | "dependencia" | "nota"
    #       "label": ""
    #     }
    #   ],
    #   "viewport": {"x": 0, "y": 0, "zoom": 1.0}
    # }
    creado_en      = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-actualizado_en']

    def __str__(self):
        return f"{self.nombre} — {self.user}"


class NotaLienzo(models.Model):
    """
    Nota sticky dentro de un lienzo. También vive en snapshot.nodos
    pero se persiste aquí para búsqueda y edición directa.
    """
    lienzo    = models.ForeignKey(Lienzo, on_delete=models.CASCADE, related_name='notas')
    contenido = models.TextField()
    color     = models.CharField(max_length=20, default='#2a2a2a')
    x         = models.IntegerField(default=100)
    y         = models.IntegerField(default=100)
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Nota en {self.lienzo} [{self.pk}]"
