from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid


class Role(models.Model):
    """
    Roles configurables que determinan nivel de acceso (1, 2, 3).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True, verbose_name="Nombre del rol")
    level = models.IntegerField(
        choices=[(1, 'Nivel 1 - Memoria pura'), 
                 (2, 'Nivel 2 - Memoria + Conocimiento'), 
                 (3, 'Nivel 3 - Memoria + Conocimiento + Métricas')],
        default=1,
        verbose_name="Nivel de acceso"
    )
    capabilities = models.JSONField(
        default=dict,
        verbose_name="Capacidades",
        help_text="JSON con capacidades específicas: memory, knowledge_base, metrics, projects"
    )
    description = models.TextField(blank=True, verbose_name="Descripción")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'intelligence_roles'
        verbose_name = 'Rol'
        verbose_name_plural = 'Roles'
        ordering = ['level']

    def __str__(self):
        return f"{self.name} (Nivel {self.level})"


class User(models.Model):
    """
    Usuarios identificados por phone o email (uno de los dos).
    Cada usuario tiene un rol asignado.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(max_length=20, blank=True, null=True, unique=True, verbose_name="Teléfono")
    email = models.EmailField(blank=True, null=True, unique=True, verbose_name="Email")
    # Un usuario debe tener al menos phone o email
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name='users', verbose_name="Rol")
    metadata = models.JSONField(default=dict, verbose_name="Metadatos adicionales")
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'intelligence_users'
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
        constraints = [
            models.UniqueConstraint(fields=['phone'], name='unique_phone_when_not_null',
                                    condition=models.Q(phone__isnull=False)),
            models.UniqueConstraint(fields=['email'], name='unique_email_when_not_null',
                                    condition=models.Q(email__isnull=False)),
            models.CheckConstraint(
                check=models.Q(phone__isnull=False) | models.Q(email__isnull=False),
                name='phone_or_email_required'
            )
        ]
        indexes = [
            models.Index(fields=['phone']),
            models.Index(fields=['email']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        identifier = self.phone or self.email or str(self.id)[:8]
        return f"Usuario {identifier}"


class AppConfig(models.Model):
    """
    Configuración de apps con nivel asignado y capacidades.
    Apps definidas por ID único (ej: "web-clientes", "dashboard-admin").
    """
    id = models.CharField(max_length=100, primary_key=True, verbose_name="ID de la app")
    name = models.CharField(max_length=200, verbose_name="Nombre descriptivo")
    level = models.IntegerField(
        choices=[(1, 'Nivel 1 - Memoria pura'), 
                 (2, 'Nivel 2 - Memoria + Conocimiento'), 
                 (3, 'Nivel 3 - Memoria + Conocimiento + Métricas')],
        default=1,
        verbose_name="Nivel de la app"
    )
    capabilities = models.JSONField(
        default=dict,
        verbose_name="Capacidades",
        help_text="JSON con capacidades habilitadas: memory, knowledge_base, metrics, projects"
    )
    is_active = models.BooleanField(default=True, verbose_name="Activa")
    config = models.JSONField(default=dict, verbose_name="Configuración adicional")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'intelligence_app_configs'
        verbose_name = 'Configuración de App'
        verbose_name_plural = 'Configuraciones de Apps'
        ordering = ['id']

    def __str__(self):
        return f"{self.name} ({self.id})"


class Conversation(models.Model):
    """
    Sesiones de chat con mensajes almacenados en JSON.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversations', verbose_name="Usuario")
    app = models.ForeignKey(AppConfig, on_delete=models.CASCADE, related_name='conversations', verbose_name="App")
    session_id = models.CharField(max_length=255, db_index=True, verbose_name="ID de sesión")
    messages = models.JSONField(
        default=list,
        verbose_name="Mensajes",
        help_text="Lista de objetos mensaje con role, content, timestamp"
    )
    context_summary = models.TextField(
        blank=True,
        default='',
        verbose_name="Resumen de contexto",
        help_text="Resumen de conversaciones anteriores para mantener contexto histórico"
    )
    metadata = models.JSONField(default=dict, verbose_name="Metadatos de la conversación")
    is_active = models.BooleanField(default=True, verbose_name="Sesión activa")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_message_at = models.DateTimeField(auto_now=True, verbose_name="Último mensaje")

    class Meta:
        db_table = 'intelligence_conversations'
        verbose_name = 'Conversación'
        verbose_name_plural = 'Conversaciones'
        constraints = [
            models.UniqueConstraint(fields=['user', 'app', 'session_id'], name='unique_session_per_user_app')
        ]
        indexes = [
            models.Index(fields=['user', 'app', 'created_at']),
            models.Index(fields=['last_message_at']),
        ]

    def __str__(self):
        return f"Conversación {self.session_id[:8]}... ({self.user})"


class Fact(models.Model):
    """
    Hechos extraídos de conversaciones almacenados como triples (sujeto, relación, objeto).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='facts', verbose_name="Usuario")
    subject = models.CharField(max_length=500, verbose_name="Sujeto")
    relation = models.CharField(max_length=200, verbose_name="Relación")
    object = models.CharField(max_length=500, verbose_name="Objeto")
    confidence = models.FloatField(
        default=1.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        verbose_name="Confianza",
        help_text="Confianza en la exactitud del hecho (0.0 a 1.0)"
    )
    source_conversation = models.ForeignKey(
        Conversation, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='extracted_facts',
        verbose_name="Conversación fuente"
    )
    metadata = models.JSONField(default=dict, verbose_name="Metadatos adicionales")
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'intelligence_facts'
        verbose_name = 'Hecho'
        verbose_name_plural = 'Hechos'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'subject', 'relation', 'object'],
                name='unique_fact_per_user'
            )
        ]
        indexes = [
            models.Index(fields=['user', 'relation']),
            models.Index(fields=['subject', 'relation', 'object']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.subject} {self.relation} {self.object}"


class IntelligenceCollection(models.Model):
    """
    Configuración de colecciones vectoriales para RAG.
    Define origen de datos, campos a embedder y nivel de acceso.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nombre de colección",
        help_text="Nombre único de la colección (ej: 'propiedades_propifai')"
    )
    source_sql = models.TextField(
        verbose_name="SQL de origen",
        help_text="Query SQL contra Azure SQL que retorna id, y campos para embedding"
    )
    embedding_fields = models.JSONField(
        default=list,
        verbose_name="Campos para embedding",
        help_text="Lista de campos a concatenar (ej: ['titulo', 'descripcion', 'zona'])"
    )
    access_level = models.IntegerField(
        choices=[(1, 'Nivel 1 - Memoria pura'),
                 (2, 'Nivel 2 - Memoria + Conocimiento'),
                 (3, 'Nivel 3 - Memoria + Conocimiento + Métricas')],
        default=2,
        verbose_name="Nivel de acceso mínimo"
    )
    is_active = models.BooleanField(default=True, verbose_name="Activa")
    last_sync_at = models.DateTimeField(null=True, blank=True, verbose_name="Última sincronización")
    last_sync_count = models.IntegerField(default=0, verbose_name="Registros en última sincro")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'intelligence_collections'
        verbose_name = 'Colección Vectorial'
        verbose_name_plural = 'Colecciones Vectoriales'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} (Nivel {self.access_level})"


class IntelligenceDocument(models.Model):
    """
    Documentos vectorizados para búsqueda semántica RAG.
    Almacena contenido, embedding y metadata.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    collection = models.ForeignKey(
        IntelligenceCollection,
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name="Colección"
    )
    source_id = models.CharField(
        max_length=200,
        verbose_name="ID original",
        help_text="ID original en tabla origen"
    )
    content = models.TextField(
        verbose_name="Contenido embeddeado",
        help_text="Texto concatenado de los campos para embedding"
    )
    embedding = models.BinaryField(
        null=True,
        blank=True,
        verbose_name="Vector embedding",
        help_text="Vector de 384 dimensiones (all-MiniLM-L6-v2)"
    )
    metadata_json = models.JSONField(
        default=dict,
        verbose_name="Metadatos",
        help_text="Datos adicionales (precio, zona, fecha, etc.)"
    )
    content_hash = models.CharField(
        max_length=64,
        verbose_name="Hash del contenido",
        help_text="SHA256 del contenido para detectar cambios"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'intelligence_documents'
        verbose_name = 'Documento Vectorial'
        verbose_name_plural = 'Documentos Vectoriales'
        constraints = [
            models.UniqueConstraint(
                fields=['collection', 'source_id'],
                name='unique_document_per_collection'
            )
        ]
        indexes = [
            models.Index(fields=['collection', 'content_hash']),
            models.Index(fields=['collection', 'created_at']),
            models.Index(fields=['content_hash']),
        ]

    def __str__(self):
        return f"{self.collection.name}: {self.source_id}"
