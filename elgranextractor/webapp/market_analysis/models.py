from django.db import models


class UbicacionGeografica(models.Model):
    """
    Tabla jerárquica de ubicaciones geográficas:
    Departamento → Provincia → Distrito → Zona/Urbanización.
    
    Cada registro tiene un nivel y un parent opcional que apunta al nivel superior.
    - Departamento: parent = None
    - Provincia: parent = Departamento
    - Distrito: parent = Provincia
    - Zona/Urbanización: parent = Distrito
    
    El borrado en cascada asegura que al eliminar un departamento se eliminen
    todos sus hijos en todos los niveles.
    """
    NIVELES = [
        ('departamento', 'Departamento'),
        ('provincia', 'Provincia'),
        ('distrito', 'Distrito'),
        ('zona_urbanizacion', 'Zona / Urbanización'),
    ]

    nombre = models.CharField(max_length=200, verbose_name='Nombre')
    nivel = models.CharField(max_length=20, choices=NIVELES, verbose_name='Nivel')
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='Padre',
        help_text='Nivel superior en la jerarquía (ej: Provincia padre del Distrito)'
    )
    codigo = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name='Código',
        help_text='Código opcional (ej: UBIGEO, fuente de datos)'
    )
    activo = models.BooleanField(default=True, verbose_name='Activo')
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name='Última actualización')

    class Meta:
        verbose_name = 'Ubicación Geográfica'
        verbose_name_plural = 'Ubicaciones Geográficas'
        ordering = ['nivel', 'nombre']
        indexes = [
            models.Index(fields=['nivel']),
            models.Index(fields=['parent']),
            models.Index(fields=['nombre']),
        ]
        unique_together = [['nombre', 'parent', 'nivel']]

    def __str__(self):
        if self.parent:
            return f"{self.nombre} ({self.get_nivel_display()}) ← {self.parent.nombre}"
        return f"{self.nombre} ({self.get_nivel_display()})"

    @property
    def ruta_completa(self):
        """Devuelve la ruta completa como string: 'Departamento > Provincia > Distrito'."""
        partes = []
        actual = self
        while actual:
            partes.insert(0, actual.nombre)
            actual = actual.parent
        return ' > '.join(partes)

    def get_hijos(self):
        """Devuelve los hijos directos activos."""
        return self.children.filter(activo=True)
