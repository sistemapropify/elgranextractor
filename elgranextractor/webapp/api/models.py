"""
Modelos para el sistema de Puntos de Interés (POIs) y capas de cercanía.
Permite gestionar categorías dinámicas (capas) y puntos de interés con coordenadas.
"""

from django.db import models


class CategoriaPOI(models.Model):
    """
    Categoría / Capa de Puntos de Interés.
    Cada categoría funciona como una capa que puede activarse/desactivarse
    al consultar cercanía a propiedades.
    Las categorías se crean desde el admin sin necesidad de escribir código.
    """
    nombre = models.CharField(
        max_length=100, unique=True,
        verbose_name='Nombre'
    )
    slug = models.SlugField(
        max_length=100, unique=True,
        verbose_name='Identificador',
        help_text='Identificador único para la API (ej: hospital, pharmacy)'
    )
    icono = models.CharField(
        max_length=50, blank=True,
        verbose_name='Icono (emoji)',
        help_text='Ej: 🏥, 💊, 🏪, 🏫'
    )
    color = models.CharField(
        max_length=7, default='#58a6ff',
        verbose_name='Color (hex)',
        help_text='Color para el marcador en el mapa, ej: #FF5733'
    )
    descripcion = models.TextField(
        blank=True,
        verbose_name='Descripción'
    )
    orden = models.PositiveIntegerField(
        default=0,
        verbose_name='Orden',
        help_text='Orden de aparición en listados (menor = primero)'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Activo'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Categoría / Capa'
        verbose_name_plural = 'Categorías / Capas'
        ordering = ['orden', 'nombre']

    def __str__(self):
        icon = f"{self.icono} " if self.icono else ""
        return f"{icon}{self.nombre}"


class PointOfInterest(models.Model):
    """
    Punto de Interés geolocalizado.
    Cada POI pertenece a una categoría/capa y tiene coordenadas precisas.
    """
    nombre = models.CharField(
        max_length=200,
        verbose_name='Nombre'
    )
    categoria = models.ForeignKey(
        CategoriaPOI,
        on_delete=models.CASCADE,
        related_name='puntos',
        verbose_name='Categoría / Capa'
    )
    latitud = models.DecimalField(
        max_digits=10, decimal_places=7,
        verbose_name='Latitud'
    )
    longitud = models.DecimalField(
        max_digits=10, decimal_places=7,
        verbose_name='Longitud'
    )
    direccion = models.CharField(
        max_length=300, blank=True,
        verbose_name='Dirección'
    )
    descripcion = models.TextField(
        blank=True,
        verbose_name='Descripción'
    )
    telefono = models.CharField(
        max_length=30, blank=True,
        verbose_name='Teléfono'
    )
    sitio_web = models.URLField(
        max_length=500, blank=True,
        verbose_name='Sitio web'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Activo'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Punto de Interés'
        verbose_name_plural = 'Puntos de Interés'
        indexes = [
            models.Index(fields=['categoria']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.nombre} ({self.categoria.nombre})"
