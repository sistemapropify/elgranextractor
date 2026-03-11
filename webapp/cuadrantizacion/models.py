from django.db import models
from ingestas.models import PropiedadRaw


class ZonaValor(models.Model):
    """
    Polígono irregular que define una zona de valor inmobiliario.
    Almacena la geometría del polígono y estadísticas de precio por m².
    """
    # Jerarquía de niveles (de más alto a más básico)
    NIVELES = [
        ('pais', 'País'),
        ('departamento', 'Departamento'),
        ('provincia', 'Provincia'),
        ('distrito', 'Distrito'),
        ('zona', 'Zona'),
        ('subzona', 'Subzona'),
    ]
    
    # Campos de jerarquía
    nivel = models.CharField(
        max_length=20,
        choices=NIVELES,
        default='zona',
        help_text="Nivel jerárquico de la zona"
    )
    
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        help_text="Zona padre en la jerarquía (ej: una zona contiene subzonas)"
    )
    
    # Campos de identificación jerárquica
    codigo = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Código único para identificación (ej: PE-LIM-LIMA-MIRAFLORES)"
    )
    
    nombre_oficial = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Nombre oficial según registros gubernamentales"
    )
    
    nombre_zona = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)
    
    # Geometría del polígono (usando Django GIS si está disponible)
    # Para SQL Server, podemos usar GeometryField si se instala django-mssql-backend con soporte espacial
    # Alternativa: almacenar como JSON de coordenadas
    coordenadas = models.JSONField(
        help_text="Lista de coordenadas [[lat,lng], ...] que definen el polígono. Solo requerido para subzonas.",
        null=True,
        blank=True
    )
    
    # Estadísticas calculadas
    area_total = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True,
                                     help_text="Área total en metros cuadrados")
    precio_promedio_m2 = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    desviacion_estandar_m2 = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    cantidad_propiedades_analizadas = models.IntegerField(default=0)
    
    # Metadatos
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    activo = models.BooleanField(default=True)
    
    # Color para visualización
    color_fill = models.CharField(max_length=7, default='#2196F3', help_text="Color HEX para relleno")
    color_borde = models.CharField(max_length=7, default='#1976D2', help_text="Color HEX para borde")
    opacidad = models.FloatField(default=0.3, help_text="Opacidad del polígono (0-1)")
    
    class Meta:
        verbose_name = "Zona de Valor"
        verbose_name_plural = "Zonas de Valor"
        ordering = ['nivel', 'nombre_zona']
        indexes = [
            models.Index(fields=['nivel']),
            models.Index(fields=['parent']),
            models.Index(fields=['codigo']),
        ]
    
    def __str__(self):
        if self.parent:
            return f"{self.nombre_zona} ({self.get_nivel_display()}) - Hijo de {self.parent.nombre_zona}"
        return f"{self.nombre_zona} ({self.get_nivel_display()}) - ${self.precio_promedio_m2 or 0}/m²"
    
    def get_hierarchy_path(self):
        """Devuelve la ruta completa de la jerarquía como lista."""
        path = []
        current = self
        while current:
            path.insert(0, current)
            current = current.parent
        return path
    
    def get_hierarchy_display(self):
        """Devuelve una representación de texto de la jerarquía."""
        path = self.get_hierarchy_path()
        return " → ".join([f"{z.nombre_zona} ({z.get_nivel_display()})" for z in path])
    
    def get_descendants(self, include_self=False):
        """Devuelve todos los descendientes de esta zona."""
        from django.db.models import Q
        descendants = []
        
        def collect_children(zona):
            for child in zona.children.all():
                descendants.append(child)
                collect_children(child)
        
        if include_self:
            descendants.append(self)
        
        collect_children(self)
        return descendants
    
    def is_leaf(self):
        """Verifica si esta zona es una hoja (no tiene hijos)."""
        return not self.children.exists()
    
    def get_leaf_zones(self):
        """Devuelve todas las subzonas hoja bajo esta zona."""
        return [z for z in self.get_descendants() if z.is_leaf()]


class PropiedadValoracion(models.Model):
    """
    KPI por propiedad: precio por m² calculado y relación con zona.
    """
    propiedad = models.ForeignKey(PropiedadRaw, on_delete=models.CASCADE, related_name='valoraciones')
    zona = models.ForeignKey(ZonaValor, on_delete=models.SET_NULL, null=True, blank=True, 
                             related_name='propiedades_valoradas')
    
    # Cálculos
    precio_m2 = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True,
                                    help_text="precio_venta / metros_cuadrados")
    precio_venta = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    metros_cuadrados = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Factores de ajuste
    es_comparable = models.BooleanField(default=True, help_text="Indica si la propiedad es comparable para análisis")
    factor_ajuste = models.DecimalField(max_digits=5, decimal_places=4, default=1.0000,
                                        help_text="Factor de ponderación para cálculos")
    
    # Metadatos
    fecha_calculo = models.DateTimeField(auto_now_add=True)
    metodo_calculo = models.CharField(max_length=50, default='directo',
                                      choices=[
                                          ('directo', 'Cálculo Directo'),
                                          ('ponderado', 'Ponderado por Antigüedad'),
                                          ('ajustado', 'Ajustado por Tipo'),
                                          ('estimado', 'Estimado por Zona')
                                      ])
    
    class Meta:
        verbose_name = "Valoración de Propiedad"
        verbose_name_plural = "Valoraciones de Propiedades"
        unique_together = ['propiedad', 'zona']
        indexes = [
            models.Index(fields=['precio_m2']),
            models.Index(fields=['es_comparable']),
            models.Index(fields=['zona', 'fecha_calculo']),
        ]
    
    def __str__(self):
        return f"Valoración: {self.propiedad} - ${self.precio_m2 or 0}/m²"


class EstadisticaZona(models.Model):
    """
    Estadísticas detalladas por zona y tipo de propiedad.
    Permite análisis granular por tipo (casa, departamento, terreno, etc.)
    """
    zona = models.ForeignKey(ZonaValor, on_delete=models.CASCADE, related_name='estadisticas')
    tipo_propiedad = models.CharField(max_length=50, 
                                      choices=[
                                          ('casa', 'Casa'),
                                          ('departamento', 'Departamento'),
                                          ('terreno', 'Terreno'),
                                          ('local', 'Local Comercial'),
                                          ('oficina', 'Oficina'),
                                          ('otro', 'Otro')
                                      ])
    
    # Estadísticas
    cantidad_propiedades = models.IntegerField(default=0)
    precio_promedio_m2 = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    precio_mediano_m2 = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    precio_minimo_m2 = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    precio_maximo_m2 = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    desviacion_estandar = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # Características promedio
    habitaciones_promedio = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    banos_promedio = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    antiguedad_promedio = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    metros_cuadrados_promedio = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Fecha de actualización
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Estadística de Zona por Tipo"
        verbose_name_plural = "Estadísticas de Zona por Tipo"
        unique_together = ['zona', 'tipo_propiedad']
    
    def __str__(self):
        return f"{self.zona} - {self.tipo_propiedad}: ${self.precio_promedio_m2 or 0}/m²"


class HistorialPrecioZona(models.Model):
    """
    Historial de cambios en el precio promedio por m² de una zona.
    Permite análisis temporal y tracking de evolución de precios.
    """
    zona = models.ForeignKey(ZonaValor, on_delete=models.CASCADE, related_name='historial_precios')
    fecha_registro = models.DateField()
    precio_promedio_m2 = models.DecimalField(max_digits=15, decimal_places=2)
    cantidad_propiedades = models.IntegerField()
    desviacion_estandar = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # Metadatos
    fuente_datos = models.CharField(max_length=100, default='cálculo_automático',
                                    choices=[
                                        ('cálculo_automático', 'Cálculo Automático'),
                                        ('manual', 'Ingreso Manual'),
                                        ('actualización_masiva', 'Actualización Masiva')
                                    ])
    
    class Meta:
        verbose_name = "Historial de Precio de Zona"
        verbose_name_plural = "Historial de Precios de Zona"
        ordering = ['zona', '-fecha_registro']
        indexes = [
            models.Index(fields=['zona', 'fecha_registro']),
        ]
    
    def __str__(self):
        return f"{self.zona} - {self.fecha_registro}: ${self.precio_promedio_m2}/m²"