from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid


class Role(models.Model):
    """
    Roles configurables que determinan nivel de acceso (1, 2, 3).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True, verbose_name="Nombre del rol")
    allowed_levels = models.JSONField(
        default=list,
        verbose_name="Niveles permitidos",
        help_text="Lista de niveles permitidos para este rol (ej: [1, 2, 3])"
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
        ordering = ['name']

    def __str__(self):
        if self.allowed_levels:
            levels_str = ",".join(str(l) for l in self.allowed_levels)
            return f"{self.name} (Niveles {levels_str})"
        return f"{self.name} (Sin niveles)"


class User(models.Model):
    """
    Usuarios del sistema. Ahora con username, nombre, apellido, password y last_login
    para soportar registro y autenticación por username + password.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.CharField(max_length=50, unique=True, verbose_name="Nombre de usuario", default='')
    first_name = models.CharField(max_length=100, blank=True, verbose_name="Nombre")
    last_name = models.CharField(max_length=100, blank=True, verbose_name="Apellido")
    phone = models.CharField(max_length=20, blank=True, null=True, unique=True, verbose_name="Teléfono")
    email = models.EmailField(blank=True, null=True, unique=True, verbose_name="Email")
    password = models.CharField(max_length=128, blank=True, null=True, verbose_name="Contraseña")
    last_login = models.DateTimeField(blank=True, null=True, verbose_name="Último login")
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name='users', verbose_name="Rol")
    metadata = models.JSONField(default=dict, verbose_name="Metadatos adicionales")
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Campos requeridos por Django para AUTH_USER_MODEL
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['phone']

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
            models.Index(fields=['username']),
            models.Index(fields=['phone']),
            models.Index(fields=['email']),
            models.Index(fields=['created_at']),
        ]

    def set_password(self, raw_password):
        """Hashea y guarda la contraseña usando el sistema de hash de Django."""
        from django.contrib.auth.hashers import make_password
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        """Verifica la contraseña contra el hash almacenado."""
        from django.contrib.auth.hashers import check_password
        return check_password(raw_password, self.password)

    @property
    def is_anonymous(self):
        return False

    @property
    def is_authenticated(self):
        return True

    def __str__(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name} (@{self.username})"
        return f"@{self.username}"


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
                 (3, 'Nivel 3 - Memoria + Conocimiento + Métricas'),
                 (4, 'Nivel 4 - Acceso completo + Analytics'),
                 (5, 'Nivel 5 - Administrador total')],
        default=1,
        verbose_name="Nivel de la app",
        help_text="Nivel de acceso (1-5) según SPEC-005"
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
    Configuración de colecciones vectoriales para RAG con campos dinámicos.
    Define origen de datos (tabla Azure SQL), campos a embedder y nivel de acceso.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nombre de colección",
        help_text="Nombre único de la colección (ej: 'propiedades_propifai')"
    )
    table_name = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        verbose_name="Nombre de tabla",
        help_text="Nombre exacto de la tabla en Azure SQL (ej: 'propiedadraw'). Dejar vacío para colecciones manuales."
    )
    description = models.TextField(
        blank=True,
        verbose_name="Descripción",
        help_text="Descripción de la colección y su propósito"
    )
    source_sql = models.TextField(
        blank=True,
        verbose_name="SQL de origen",
        help_text="Query SQL contra Azure SQL que retorna id, y campos para embedding (opcional, se genera automáticamente si está vacío)"
    )
    field_definitions = models.JSONField(
        default=dict,
        verbose_name="Definiciones de campos",
        help_text="Diccionario con definición de TODOS los campos de la tabla: {'nombre_campo': {'type': 'string', 'nullable': false, ...}}"
    )
    embedding_fields = models.JSONField(
        default=list,
        verbose_name="Campos para embedding",
        help_text="Lista de campos (nombres reales) usados para embedding (ej: ['titulo', 'descripcion', 'zona'])"
    )
    display_fields = models.JSONField(
        default=list,
        verbose_name="Campos a mostrar",
        help_text="Lista de campos (nombres reales) a mostrar en resultados de búsqueda"
    )
    filter_fields = models.JSONField(
        default=list,
        verbose_name="Campos filtrables",
        help_text="Lista de campos (nombres reales) que se pueden usar como filtros"
    )
    access_level = models.IntegerField(
        choices=[(1, 'Nivel 1 - Memoria pura'),
                 (2, 'Nivel 2 - Memoria + Conocimiento'),
                 (3, 'Nivel 3 - Memoria + Conocimiento + Métricas'),
                 (4, 'Nivel 4 - Acceso completo + Analytics'),
                 (5, 'Nivel 5 - Administrador total')],
        default=2,
        verbose_name="Nivel de acceso mínimo",
        help_text="Nivel mínimo requerido para acceder a esta colección (1-5)"
    )
    roles_con_acceso = models.JSONField(
        default=list,
        verbose_name="Roles con acceso",
        help_text="Lista de IDs de roles que pueden acceder a esta colección"
    )
    apps_con_acceso = models.JSONField(
        default=list,
        verbose_name="Apps con acceso",
        help_text="Lista de IDs de apps que pueden acceder a esta colección"
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
    Documentos vectorizados para búsqueda semántica RAG con campos dinámicos.
    Almacena field_values con nombres REALES de campos de la tabla origen.
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
        help_text="Valor del campo ID en la tabla origen"
    )
    field_values = models.JSONField(
        default=dict,
        verbose_name="Valores de campos",
        help_text="Diccionario con nombres REALES de campos y sus valores de la tabla origen"
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


class EpisodicMemory(models.Model):
    """
    Memoria episódica: eventos completos de interacción usuario-sistema.
    Cada "episodio" es una interacción atómica (mensaje + respuesta + contexto completo).
    """
    EPISODE_TYPES = [
        ('property_search', 'Búsqueda de propiedad'),
        ('property_detail', 'Consulta de detalle'),
        ('price_inquiry', 'Consulta de precio'),
        ('matching', 'Matching oferta-demanda'),
        ('acm_analysis', 'Análisis ACM'),
        ('general', 'Consulta general'),
        ('fact_extraction', 'Extracción de hecho'),
        ('user_preference', 'Preferencia del usuario'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='episodic_memories',
        verbose_name="Usuario"
    )
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE,
        related_name='episodic_memories',
        verbose_name="Conversación"
    )

    # --- El episodio en sí ---
    user_message = models.TextField(verbose_name="Mensaje del usuario")
    user_message_embedding = models.BinaryField(
        null=True, blank=True,
        verbose_name="Embedding del mensaje",
        help_text="Vector de 384 dimensiones para búsqueda semántica"
    )
    assistant_response = models.TextField(verbose_name="Respuesta del asistente")
    timestamp = models.DateTimeField(
        db_index=True,
        verbose_name="Momento de la interacción"
    )

    # --- Clasificación ---
    episode_type = models.CharField(
        max_length=50, db_index=True,
        choices=EPISODE_TYPES,
        default='general',
        verbose_name="Tipo de episodio"
    )
    intent_detected = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name="Intención detectada"
    )

    # --- Contexto enriquecido (JSON) ---
    context = models.JSONField(
        default=dict, blank=True,
        verbose_name="Contexto del episodio",
        help_text="""Almacena:
            - entities: {districts, property_types, price_range, ...}
            - topics: [temas detectados]
            - sentiment: positivo/neutral/negativo
            - user_actions: [acciones del usuario]
        """
    )

    # --- RAG context usado ---
    rag_context_used = models.JSONField(
        default=dict, blank=True,
        verbose_name="Contexto RAG utilizado",
        help_text="""Almacena:
            - collections_queried: [nombres de colecciones]
            - documents_retrieved: [{id, title, score}]
            - search_type: vector | text | hybrid
            - total_results: número total de resultados
        """
    )

    # --- Memory context usado ---
    memory_context_used = models.JSONField(
        default=dict, blank=True,
        verbose_name="Contexto de memoria utilizado",
        help_text="""Almacena:
            - facts_retrieved: [hechos usados]
            - conversations_retrieved: [conversaciones usadas]
        """
    )

    # --- Feedback del usuario ---
    feedback = models.JSONField(
        default=dict, blank=True,
        verbose_name="Feedback del usuario",
        help_text="""Almacena:
            - thumbs_up: bool | null
            - thumbs_down: bool | null
            - user_comment: str | null
            - collected_at: timestamp | null
        """
    )

    # --- Métricas de rendimiento ---
    latency_ms = models.IntegerField(
        null=True, blank=True,
        verbose_name="Latencia (ms)",
        help_text="Tiempo de generación de la respuesta en milisegundos"
    )

    # --- Importancia ---
    importance_score = models.FloatField(
        default=0.5,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        verbose_name="Puntuación de importancia",
        help_text="0.0 = trivial, 1.0 = muy importante. Se calcula automáticamente."
    )

    # --- Control ---
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'intelligence_episodic_memory'
        verbose_name = 'Memoria Episódica'
        verbose_name_plural = 'Memorias Episódicas'
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['user', 'episode_type']),
            models.Index(fields=['user', 'importance_score']),
            models.Index(fields=['timestamp']),
        ]
        ordering = ['-timestamp']

    def __str__(self):
        return f"Episodio {self.episode_type} ({self.user}) - {self.timestamp.strftime('%d/%m/%Y %H:%M') if self.timestamp else 'sin fecha'}"
