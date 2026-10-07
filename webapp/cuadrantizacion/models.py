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
        ('cuadrante', 'Cuadrante'),
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


class CapaRasterMapa(models.Model):
    """
    Capa raster (imagen) georreferenciada que se superpone al mapa base.

    Se usa para calzar planos que vienen en PDF/imagen —por ejemplo la
    Zonificación del Plan de Desarrollo Metropolitano de Arequipa 2016-2025—
    sobre Google Maps. El encaje geográfico se define con las esquinas de la
    imagen en longitud/latitud; sobre ese encaje se aplican ajustes finos de
    transparencia, giro, escala y desplazamiento, que se guardan aquí para que
    la capa quede igual para todos los usuarios.
    """

    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)

    imagen_url = models.CharField(
        max_length=500,
        blank=True,
        default='',
        help_text="Ruta dentro de /static/ o URL completa de la imagen de la capa."
    )

    # Georreferenciación: esquinas de la imagen expresadas en [longitud, latitud].
    # Orden esperado: tl (sup.izq), tr (sup.der), br (inf.der), bl (inf.izq).
    esquinas = models.JSONField(
        default=dict,
        blank=True,
        help_text='{"tl": [lon, lat], "tr": [lon, lat], "br": [lon, lat], "bl": [lon, lat]}'
    )

    # Ajuste fino sobre el encaje georreferenciado
    opacidad = models.FloatField(
        default=0.65,
        help_text="0 = totalmente transparente, 1 = totalmente opaca"
    )
    rotacion = models.FloatField(default=0.0, help_text="Giro en grados (positivo = sentido horario)")
    escala = models.FloatField(default=1.0, help_text="Factor de escala")
    offset_x = models.FloatField(
        default=0.0,
        help_text="Desplazamiento horizontal en píxeles de pantalla"
    )
    offset_y = models.FloatField(
        default=0.0,
        help_text="Desplazamiento vertical en píxeles de pantalla"
    )

    # Estado
    bloqueado = models.BooleanField(
        default=False,
        help_text="Si está bloqueada, la capa no se puede mover ni girar"
    )
    visible = models.BooleanField(default=True)
    activo = models.BooleanField(default=True)
    orden = models.IntegerField(default=0)

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Capa raster del mapa"
        verbose_name_plural = "Capas raster del mapa"
        ordering = ['orden', 'nombre']
        indexes = [
            models.Index(fields=['activo', 'orden']),
        ]

    def __str__(self):
        return self.nombre

    def tiene_georreferencia(self):
        """Indica si la capa tiene las cuatro esquinas cargadas."""
        esquinas = self.esquinas or {}
        return all(
            isinstance(esquinas.get(clave), (list, tuple)) and len(esquinas[clave]) == 2
            for clave in ('tl', 'tr', 'br', 'bl')
        )

    def a_diccionario(self):
        """Serializa la capa para el mapa (y para la API de guardado)."""
        return {
            'id': self.id,
            'nombre': self.nombre,
            'descripcion': self.descripcion or '',
            'imagen_url': self.imagen_url or '',
            'esquinas': self.esquinas or {},
            'opacidad': self.opacidad,
            'rotacion': self.rotacion,
            'escala': self.escala,
            'offset_x': self.offset_x,
            'offset_y': self.offset_y,
            'bloqueado': self.bloqueado,
            'visible': self.visible,
            'activo': self.activo,
            'orden': self.orden,
        }


class ZonaUso(models.Model):
    """
    Categoría de uso del suelo de la leyenda del plano de zonificación.

    Cada fila es un recuadro de la leyenda: su código (el que va impreso en el
    mapa), su descripción, la categoría general y el color de relleno. El
    clasificador usa este color para deducir la zona de cada marcador.
    """

    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=200)
    categoria = models.CharField(max_length=60, blank=True, default='')
    color = models.CharField(
        max_length=7,
        help_text="Color de relleno en formato HEX, tal como aparece en la leyenda."
    )
    descripcion = models.TextField(blank=True, null=True)
    orden = models.IntegerField(default=0)
    activo = models.BooleanField(default=True)

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Zona de uso (leyenda)"
        verbose_name_plural = "Zonas de uso (leyenda)"
        ordering = ['orden', 'codigo']

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"

    def a_diccionario(self):
        return {
            'id': self.id,
            'codigo': self.codigo,
            'nombre': self.nombre,
            'categoria': self.categoria,
            'color': self.color,
            'activo': self.activo,
        }


class Zonificacion(models.Model):
    """
    Zona de uso del plano (PDM) asignada a una propiedad del scraper.

    Una fila por propiedad: guarda el código y el nombre de la zona —que salen
    de resolver el polígono del plano que contiene la propiedad—
    y el control de verificación humana en el campo `verificada`.

    La clave es (fuente, propiedad_id) porque el mapa reúne propiedades de
    orígenes distintos: Propify vive en su propia base y los portales
    (remax, properati, ...) en PropiedadesCompetencia. `propiedad_id` guarda el
    identificador dentro de su origen, tal como lo expone el mapa.
    """

    ORIGENES_CALCULO = [
        ('automatico', 'Automático (color del plano)'),
        ('manual', 'Manual'),
    ]

    fuente = models.CharField(
        max_length=40,
        help_text="Origen de la propiedad: propify, remax, properati, ..."
    )
    propiedad_id = models.CharField(
        max_length=80,
        help_text="Identificador de la propiedad dentro de su origen"
    )
    propiedad_ref = models.CharField(
        max_length=200, blank=True, null=True,
        help_text="Código o título de la publicación, para reconocerla rápido"
    )
    latitud = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitud = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)

    # Zona asignada (copia del código de la leyenda)
    codigo = models.CharField(max_length=20, blank=True, default='')
    nombre = models.CharField(max_length=200, blank=True, default='')
    categoria = models.CharField(max_length=60, blank=True, default='')
    color = models.CharField(max_length=7, blank=True, default='')
    cobertura = models.FloatField(null=True, blank=True, help_text="Proporción de píxeles que coinciden")
    confianza = models.CharField(max_length=10, blank=True, default='')
    origen_calculo = models.CharField(
        max_length=20, choices=ORIGENES_CALCULO, default='automatico'
    )
    fecha_calculo = models.DateTimeField(auto_now_add=True)

    # Verificación humana
    verificada = models.BooleanField(
        default=False,
        help_text="Marca que alguien confirmó que la propiedad está bien ubicada en esta zona"
    )
    verificada_por = models.CharField(max_length=150, blank=True, null=True)
    fecha_verificacion = models.DateTimeField(null=True, blank=True)
    observacion = models.TextField(blank=True, null=True)

    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Zonificación de propiedad"
        verbose_name_plural = "Zonificaciones de propiedades"
        ordering = ['fuente', 'propiedad_id']
        unique_together = [('fuente', 'propiedad_id')]
        indexes = [
            models.Index(fields=['fuente', 'propiedad_id']),
            models.Index(fields=['codigo']),
            models.Index(fields=['verificada']),
        ]

    def __str__(self):
        if self.codigo:
            return f"{self.fuente}:{self.propiedad_id} → {self.codigo}"
        return f"{self.fuente}:{self.propiedad_id} → sin zona"

    def a_diccionario(self):
        return {
            'id': self.id,
            'fuente': self.fuente,
            'propiedad_id': self.propiedad_id,
            'propiedad_ref': self.propiedad_ref or '',
            'latitud': float(self.latitud) if self.latitud is not None else None,
            'longitud': float(self.longitud) if self.longitud is not None else None,
            'codigo': self.codigo or None,
            'nombre': self.nombre or '',
            'categoria': self.categoria or '',
            'color': self.color or '',
            'cobertura': self.cobertura,
            'confianza': self.confianza or '',
            'origen_calculo': self.origen_calculo,
            'verificada': self.verificada,
            'verificada_por': self.verificada_por or '',
            'fecha_verificacion': (
                self.fecha_verificacion.isoformat() if self.fecha_verificacion else None
            ),
            'observacion': self.observacion or '',
        }


class CapaVectorialMapa(models.Model):
    """
    Capa vectorial (polígonos) que se dibuja sobre el mapa base.

    El plano de zonificación del PDM se extrae del PDF como polígonos
    georreferenciados y se sirve como GeoJSON. Dibujar vectores en lugar de una
    imagen hace que los límites entre zonas sean líneas exactas a cualquier
    zoom, con los colores sólidos de la leyenda, y permite clasificar cada
    marcador por geometría en vez de por color.
    """

    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)
    geojson_url = models.CharField(
        max_length=500,
        help_text="Ruta dentro de /static/ o URL del archivo GeoJSON."
    )
    propiedad_color = models.CharField(
        max_length=60, default='color',
        help_text="Nombre de la propiedad del feature que trae el color de relleno."
    )
    propiedad_codigo = models.CharField(
        max_length=60, default='codigo',
        help_text="Nombre de la propiedad del feature que trae el código de zona."
    )
    opacidad = models.FloatField(
        default=0.65, help_text="0 = invisible, 1 = relleno sólido"
    )
    color_borde = models.CharField(
        max_length=7, default='#000000', blank=True,
        help_text="Color del borde de los polígonos (vacío = sin borde)."
    )
    grosor_borde = models.FloatField(default=0.4)

    visible = models.BooleanField(default=True)
    activo = models.BooleanField(default=True)
    orden = models.IntegerField(default=0)

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Capa vectorial del mapa"
        verbose_name_plural = "Capas vectoriales del mapa"
        ordering = ['orden', 'nombre']

    def __str__(self):
        return self.nombre

    def a_diccionario(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'descripcion': self.descripcion or '',
            'geojson_url': self.geojson_url or '',
            'propiedad_color': self.propiedad_color or 'color',
            'propiedad_codigo': self.propiedad_codigo or 'codigo',
            'opacidad': self.opacidad,
            'color_borde': self.color_borde or '',
            'grosor_borde': self.grosor_borde,
            'visible': self.visible,
            'activo': self.activo,
            'orden': self.orden,
        }
