"""
Modelos del módulo canvas (PropFlow Visual Canvas).

Cuatro modelos principales:
- CardTemplate: configuración de campos visibles para tarjetas de propiedades
- Lienzo: lienzo guardado con snapshot completo del canvas
- NotaLienzo: notas sticky persistentes dentro de un lienzo
- ArchivoLienzo: archivos subidos (Excel, Word, PDF, imagenes, etc.)
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
    #       "tipo": "propiedad",       # | "requerimiento" | "nota" | "archivo" | "enlace"
    #       "ref_id": 123,             # source_id del IntelligenceDocument o pk de ArchivoLienzo
    #       "x": 340, "y": 210,
    #       "width": 220, "height": 160,
    #       "collapsed": false,
    #       "color": null,
    #       "field_data": {}           # datos adicionales (file_url, url, etc.)
    #     }
    #   ],
    #   "aristas": [ ... ],
    #   "viewport": {"x": 0, "y": 0, "zoom": 1.0},
    #   "campos": ["bedrooms", ...],
    #   "agente_id": "Juan Perez"
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


class ArchivoLienzo(models.Model):
    """
    Archivo subido a un lienzo (Excel, Word, PDF, imagen, etc.).
    Se almacena en Azure Blob Storage (contenedor 'lienzostorage').
    Este modelo guarda los metadatos y la referencia al blob.
    """
    TIPO_CHOICES = [
        ('excel', 'Excel'),
        ('word',  'Word'),
        ('pdf',   'PDF'),
        ('image', 'Imagen'),
        ('other', 'Otro'),
    ]

    lienzo    = models.ForeignKey(Lienzo, on_delete=models.CASCADE, related_name='archivos')
    nombre    = models.CharField(max_length=255, help_text="Nombre original del archivo")
    tipo      = models.CharField(max_length=20, choices=TIPO_CHOICES)
    blob_url  = models.URLField(max_length=1024, blank=True, default='', help_text="URL en Azure Blob Storage")
    blob_name = models.CharField(max_length=512, blank=True, default='', help_text="Nombre del blob en Azure")
    tamano    = models.BigIntegerField(default=0, help_text="Tamaño en bytes")
    x         = models.IntegerField(default=100)
    y         = models.IntegerField(default=100)
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre} ({self.get_tipo_display()}) en {self.lienzo}"
