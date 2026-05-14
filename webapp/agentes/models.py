from django.db import models
from django.core.validators import FileExtensionValidator

from .storage_backends import LogoStorage, IconoMarcadorStorage, FotoPerfilStorage


class Inmobiliaria(models.Model):
    """Modelo para empresas inmobiliarias."""
    nombre = models.CharField(
        max_length=200,
        unique=True,
        db_index=True,
        verbose_name='Nombre',
        help_text='Nombre de la inmobiliaria',
    )
    direccion = models.TextField(
        blank=True,
        verbose_name='Dirección',
        help_text='Dirección física de la inmobiliaria',
    )
    latitud = models.FloatField(
        null=True, blank=True,
        verbose_name='Latitud',
        help_text='Coordenada de latitud (-90 a 90)',
    )
    longitud = models.FloatField(
        null=True, blank=True,
        verbose_name='Longitud',
        help_text='Coordenada de longitud (-180 a 180)',
    )
    logo = models.ImageField(
        upload_to='logos_inmobiliarias/',
        storage=LogoStorage(),
        blank=True, null=True,
        verbose_name='Logo',
        help_text='Logo de la inmobiliaria (PNG recomendado, máx. 200×200 px, fondo claro)',
        validators=[FileExtensionValidator(['png', 'jpg', 'jpeg', 'svg'])],
    )
    icono_marcador = models.ImageField(
        upload_to='iconos_marcadores/',
        storage=IconoMarcadorStorage(),
        blank=True, null=True,
        verbose_name='Ícono de marcador',
        help_text='Ícono PNG para el marcador en el mapa (recomendado: 40×40 px, fondo transparente)',
        validators=[FileExtensionValidator(['png'])],
    )
    creado_en = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Creado en',
    )
    actualizado_en = models.DateTimeField(
        auto_now=True,
        verbose_name='Actualizado en',
    )

    class Meta:
        db_table = 'agentes_inmobiliaria'
        ordering = ['nombre']
        verbose_name = 'Inmobiliaria'
        verbose_name_plural = 'Inmobiliarias'

    def __str__(self):
        return self.nombre


class Agente(models.Model):
    """Modelo para agentes inmobiliarios."""
    class TipoAgente(models.TextChoices):
        INDEPENDIENTE = 'INDEPENDIENTE', 'Independiente'
        INMOBILIARIA = 'INMOBILIARIA', 'Inmobiliaria'

    nombre_completo = models.CharField(
        max_length=200,
        db_index=True,
        verbose_name='Nombre completo',
        help_text='Nombres y apellidos del agente',
    )
    codigo_agente = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Código de agente',
        help_text='Código interno o ID del agente (ej: AG-001)',
    )
    correo_electronico = models.EmailField(
        max_length=254,
        blank=True,
        verbose_name='Correo electrónico',
        help_text='Dirección de correo electrónico del agente',
    )
    telefono = models.CharField(
        max_length=20,
        verbose_name='Teléfono',
        help_text='Número de contacto del agente (formato E.164: +51999888777)',
    )
    tipo_agente = models.CharField(
        max_length=15,
        choices=TipoAgente.choices,
        default=TipoAgente.INDEPENDIENTE,
        verbose_name='Tipo de agente',
        help_text='Independiente o trabaja para una inmobiliaria',
    )
    inmobiliaria = models.ForeignKey(
        'Inmobiliaria',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Inmobiliaria',
        help_text='Inmobiliaria a la que pertenece (solo si aplica)',
    )

    # ── Redes sociales y web ──────────────────
    sitio_web = models.URLField(
        max_length=500,
        blank=True,
        verbose_name='Sitio web',
        help_text='URL de la página web personal o profesional',
    )
    facebook_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name='Facebook',
        help_text='URL del perfil o página de Facebook',
    )
    instagram_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name='Instagram',
        help_text='URL del perfil de Instagram',
    )
    linkedin_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name='LinkedIn',
        help_text='URL del perfil de LinkedIn',
    )
    tiktok_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name='TikTok',
        help_text='URL del perfil de TikTok',
    )

    # ── Foto de perfil ────────────────────────
    foto_perfil = models.ImageField(
        upload_to='fotos_agentes/',
        storage=FotoPerfilStorage(),
        blank=True, null=True,
        verbose_name='Foto de perfil',
        help_text='Foto del agente (JPG/PNG recomendado, máx. 400×400 px)',
        validators=[FileExtensionValidator(['png', 'jpg', 'jpeg'])],
    )

    # ── Auditoría ─────────────────────────────
    creado_en = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Creado en',
    )
    actualizado_en = models.DateTimeField(
        auto_now=True,
        verbose_name='Actualizado en',
    )

    class Meta:
        db_table = 'agentes_agente'
        ordering = ['nombre_completo']
        verbose_name = 'Agente'
        verbose_name_plural = 'Agentes'

    def __str__(self):
        if self.codigo_agente:
            return f'[{self.codigo_agente}] {self.nombre_completo}'
        return self.nombre_completo
