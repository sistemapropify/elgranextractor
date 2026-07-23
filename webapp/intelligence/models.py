from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from typing import Tuple
import uuid


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTES COMPARTIDAS
# ═══════════════════════════════════════════════════════════════════════════════

DOMAIN_CHOICES = [
    ('publico', 'Público'),
    ('legal', 'Legal / Regulatorio'),
    ('marketing', 'Marketing / Ventas'),
    ('escuela', 'Escuela / Capacitación'),
    ('gerencia', 'Gerencia / Estrategia'),
    ('ti', 'TI / Infraestructura'),
    ('general', 'General / Sin clasificar'),
]

LEVEL_CHOICES = [
    (1, 'Nivel 1 - Consulta básica'),
    (2, 'Nivel 2 - Consulta avanzada'),
    (3, 'Nivel 3 - Análisis'),
    (4, 'Nivel 4 - Edición'),
    (5, 'Nivel 5 - Administración total'),
]


class Role(models.Model):
    """
    Roles configurables que determinan nivel de acceso (1-5) y dominios permitidos.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True, verbose_name="Nombre del rol")
    default_level = models.IntegerField(
        choices=LEVEL_CHOICES,
        default=1,
        verbose_name="Nivel por defecto",
        help_text="Nivel base que reciben los usuarios de este rol (1-5)"
    )
    max_level = models.IntegerField(
        choices=LEVEL_CHOICES,
        default=5,
        verbose_name="Nivel máximo",
        help_text="Nivel máximo que puede alcanzar un usuario de este rol (1-5)"
    )
    default_domains = models.JSONField(
        default=list,
        verbose_name="Dominios por defecto",
        help_text="Lista de dominios asignados por defecto a usuarios de este rol (ej: ['publico', 'legal'])"
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
        return f"{self.name} (Nivel {self.default_level}, Max {self.max_level})"


class UserManager(models.Manager):
    """Manager personalizado para User que implementa get_by_natural_key."""
    def get_by_natural_key(self, username):
        return self.get(username=username)


class User(models.Model):
    """
    Usuarios del sistema. Ahora con username, nombre, apellido, password y last_login
    para soportar registro y autenticación por username + password.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    objects = UserManager()
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

    @property
    def is_staff(self):
        """Propiedad requerida por Django Admin. Retorna True si el rol es Administrador."""
        try:
            return self.role.name == 'Administrador' if self.role else False
        except Exception:
            return False

    @property
    def is_superuser(self):
        """Propiedad requerida por Django Admin. Retorna True si el rol es Administrador."""
        try:
            return self.role.name == 'Administrador' if self.role else False
        except Exception:
            return False

    def has_perm(self, perm, obj=None):
        """Requerido por Django Admin. Los administradores tienen todos los permisos."""
        return self.is_superuser

    def has_perms(self, perm_list, obj=None):
        """Requerido por Django Admin."""
        return self.is_superuser

    def has_module_perms(self, app_label):
        """Requerido por Django Admin. Retorna True si puede acceder a un módulo."""
        return self.is_superuser

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
    Define origen de datos (tabla Azure SQL), campos a embedder, nivel mínimo,
    dominio funcional y visibilidad pública.
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
    min_level = models.IntegerField(
        choices=LEVEL_CHOICES,
        default=1,
        verbose_name="Nivel mínimo requerido",
        help_text="Nivel mínimo que debe tener el usuario para acceder a esta colección (1-5)"
    )
    domain = models.CharField(
        max_length=50,
        choices=DOMAIN_CHOICES,
        default='general',
        verbose_name="Dominio funcional",
        help_text="Dominio al que pertenece esta colección. Controla qué usuarios pueden verla según sus dominios asignados."
    )
    is_public = models.BooleanField(
        default=False,
        verbose_name="Colección pública",
        help_text="Si es True, cualquier usuario autenticado puede verla (sin importar dominio). Si es False, solo usuarios con el dominio asignado."
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
    table_relationships = models.JSONField(
        default=list,
        verbose_name="Relaciones entre tablas",
        help_text="Lista de relaciones FK para resolver durante sync: [{'foreign_key_field': 'district_fk_id', 'referenced_table': 'districts', 'referenced_display_fields': ['name'], 'label': 'Distrito'}]"
    )
    semantic_tags = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Etiquetas semánticas",
        help_text="Lista de etiquetas semánticas que describen el contenido de la colección. "
                  "Se inyectan en el embedding durante sync para mejorar búsquedas conceptuales. "
                  "Ej: ['terreno', 'construccion', 'educacion', 'comercial', 'vivienda']"
    )
    database_alias = models.CharField(
        max_length=50,
        default='default',
        verbose_name="Alias de base de datos",
        help_text="Alias de la conexión de base de datos en Django settings (ej: 'default', 'propifai')"
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
        domain_label = dict(DOMAIN_CHOICES).get(self.domain, self.domain)
        return f"{self.name} [{domain_label}] (Nivel {self.min_level})"


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
        help_text="Vector de 384 dimensiones (multilingual-e5-small)"
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


class UserIntelligenceProfile(models.Model):
    """
    Perfil de inteligencia por usuario. Controla nivel real, dominios permitidos
    y colecciones extra/bloqueadas de forma individual.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='intelligence_profile',
        verbose_name="Usuario"
    )
    level = models.IntegerField(
        choices=LEVEL_CHOICES,
        default=1,
        verbose_name="Nivel del usuario",
        help_text="Nivel real del usuario (1-5). Se hereda del rol al crear, pero puede ajustarse individualmente."
    )
    allowed_domains = models.JSONField(
        default=list,
        verbose_name="Dominios permitidos",
        help_text="Lista de dominios a los que el usuario tiene acceso (ej: ['publico', 'legal', 'marketing'])"
    )
    extra_collections = models.ManyToManyField(
        IntelligenceCollection,
        blank=True,
        related_name='extra_profiles',
        verbose_name="Colecciones extra",
        help_text="Colecciones adicionales a las que el usuario tiene acceso, más allá de las de su dominio/nivel."
    )
    blocked_collections = models.ManyToManyField(
        IntelligenceCollection,
        blank=True,
        related_name='blocked_profiles',
        verbose_name="Colecciones bloqueadas",
        help_text="Colecciones específicas bloqueadas para este usuario, incluso si cumple nivel/dominio."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'intelligence_user_profiles'
        verbose_name = 'Perfil de Inteligencia'
        verbose_name_plural = 'Perfiles de Inteligencia'
        indexes = [
            models.Index(fields=['user', 'level']),
        ]

    def __str__(self):
        return f"Perfil de {self.user.username} (Nivel {self.level})"

    def can_access_collection(self, collection: IntelligenceCollection) -> Tuple[bool, str]:
        """
        Verifica si el usuario puede acceder a una colección específica.
        Retorna (True, '') o (False, 'razón').
        """
        # 1. Bloqueo explícito
        if self.blocked_collections.filter(id=collection.id).exists():
            return False, "Colección bloqueada explícitamente para este usuario"

        # 2. Verificar nivel mínimo
        if self.level < collection.min_level:
            return False, f"Nivel insuficiente: {self.level} < {collection.min_level}"

        # 3. Colección pública → acceso concedido
        if collection.is_public:
            return True, ""

        # 4. Colección extra → acceso concedido
        if self.extra_collections.filter(id=collection.id).exists():
            return True, ""

        # 5. Verificar dominio
        if collection.domain in self.allowed_domains:
            return True, ""

        return False, f"Dominio '{collection.domain}' no está en los dominios permitidos del usuario"


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


# ═══════════════════════════════════════════════════════════════════════════════
# FLUJOS DE CONVERSACIÓN (Workflows)
# ═══════════════════════════════════════════════════════════════════════════════

class ConversationFlow(models.Model):
    """
    Flujo de conversación guiado (como n8n pero para chat).

    Permite crear flujos conversacionales con estados, transiciones y mensajes
    automatizados. Soporta botones para dirigir el flujo.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, unique=True, verbose_name="Nombre del flujo")
    description = models.TextField(blank=True, verbose_name="Descripción")

    # Estados del flujo (JSON con estructura de nodos)
    states = models.JSONField(
        default=dict,
        verbose_name="Estados del flujo",
        help_text="""
        JSON con estados del flujo. Ejemplo:
        {
            "start": {
                "message": "¡Hola! ¿Quieres vender o comprar una propiedad?",
                "buttons": [
                    {"text": "Vender", "next_state": "ask_sell_details"},
                    {"text": "Comprar", "next_state": "ask_buy_details"}
                ]
            },
            "ask_sell_details": {
                "message": "¿Qué tipo de propiedad quieres vender?",
                "collect_data": ["property_type", "location"],
                "next_state": "schedule_visit"
            }
        }
        """
    )

    # Estado inicial
    initial_state = models.CharField(max_length=100, default='start', verbose_name="Estado inicial")

    # Metadatos adicionales
    metadata = models.JSONField(default=dict, verbose_name="Metadatos")

    # Control
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'intelligence_conversation_flows'
        verbose_name = 'Flujo de Conversación'
        verbose_name_plural = 'Flujos de Conversación'
        ordering = ['name']

    def __str__(self):
        return f"Flujo: {self.name}"


class ConversationFlowState(models.Model):
    """
    Estado actual de una conversación en un flujo.

    Rastrea el progreso del usuario a través del flujo y almacena datos recopilados.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.OneToOneField(
        Conversation,
        on_delete=models.CASCADE,
        related_name='flow_state',
        verbose_name="Conversación"
    )
    flow = models.ForeignKey(
        ConversationFlow,
        on_delete=models.CASCADE,
        related_name='active_conversations',
        verbose_name="Flujo"
    )

    # Estado actual en el flujo
    current_state = models.CharField(max_length=100, verbose_name="Estado actual")

    # Datos recopilados durante el flujo
    collected_data = models.JSONField(
        default=dict,
        verbose_name="Datos recopilados",
        help_text="Datos que el usuario ha proporcionado durante el flujo"
    )

    # Historial de estados visitados
    state_history = models.JSONField(
        default=list,
        verbose_name="Historial de estados",
        help_text="Lista de estados por los que ha pasado la conversación"
    )

    # Control
    is_completed = models.BooleanField(default=False, verbose_name="Completado")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Completado en")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'intelligence_conversation_flow_states'
        verbose_name = 'Estado de Flujo de Conversación'
        verbose_name_plural = 'Estados de Flujo de Conversación'
        ordering = ['-updated_at']

    def __str__(self):
        return f"Estado de {self.conversation} en {self.flow.name}: {self.current_state}"


class SkillExecution(models.Model):
    """Registro de ejecución de una skill para persistencia a largo plazo y dashboard."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    skill_name = models.CharField(max_length=100, db_index=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    conversation = models.ForeignKey(Conversation, on_delete=models.SET_NULL, null=True, blank=True)
    parameters = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, null=True, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('success', 'Success'),
        ('error', 'Error'),
        ('timeout', 'Timeout'),
        ('cached', 'Cached'),
    ], db_index=True, default='success')
    latency_ms = models.FloatField(default=0)
    error_message = models.TextField(null=True, blank=True)
    cached = models.BooleanField(default=False)
    executed_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'intelligence_skill_execution'
        verbose_name = 'Ejecución de Skill'
        verbose_name_plural = 'Ejecuciones de Skills'
        indexes = [
            models.Index(fields=['skill_name', 'executed_at']),
            models.Index(fields=['status', 'executed_at']),
        ]
        # NOTA: Sin ordering global porque SQL Server en modo estricto (ODBC Driver 18)
        # rechaza ORDER BY en columnas no incluidas en GROUP BY cuando hay agregaciones.
        # Usar order_by explícito solo donde se necesite.

    def __str__(self):
        return f"Skill {self.skill_name} - {self.status} ({self.executed_at.strftime('%d/%m/%Y %H:%M') if self.executed_at else 'sin fecha'})"


# ═══════════════════════════════════════════════════════════════════════════════
# MODELO: AIConsumptionLog — Registro de consumo de API de DeepSeek
# ═══════════════════════════════════════════════════════════════════════════════

class AIConsumptionLog(models.Model):
    """
    Registro de cada llamada a la API de DeepSeek para monitorear consumo de tokens,
    costos y patrones de uso por hora.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Metadatos de la llamada
    model_name = models.CharField(
        max_length=100, default='deepseek-chat',
        verbose_name="Modelo usado"
    )
    endpoint = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name="Endpoint o función que llamó a la API"
    )
    caller_app = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name="App Django que originó la llamada"
    )
    
    # Tokens
    prompt_tokens = models.IntegerField(
        default=0, verbose_name="Tokens de entrada (prompt)"
    )
    completion_tokens = models.IntegerField(
        default=0, verbose_name="Tokens de salida (completion)"
    )
    total_tokens = models.IntegerField(
        default=0, verbose_name="Tokens totales"
    )
    
    # Costo estimado (DeepSeek: $0.14/1M input, $0.28/1M output para deepseek-chat)
    estimated_cost_usd = models.DecimalField(
        max_digits=10, decimal_places=8, default=0,
        verbose_name="Costo estimado USD"
    )
    
    # Métricas de rendimiento
    duration_ms = models.IntegerField(
        default=0, verbose_name="Duración de la llamada (ms)"
    )
    success = models.BooleanField(
        default=True, verbose_name="¿La llamada fue exitosa?"
    )
    status_code = models.IntegerField(
        null=True, blank=True, verbose_name="Código de estado HTTP"
    )
    error_message = models.TextField(
        blank=True, default='', verbose_name="Mensaje de error si falló"
    )
    
    # Calidad de extracción (porcentaje) — añadido directamente a BD, campo sincronizado
    calidad_extraccion_pct = models.FloatField(
        null=True, blank=True, verbose_name="Calidad de extracción (%)"
    )
    
    # Resumen del input — añadido directamente a BD, campo sincronizado
    input_summary = models.TextField(
        null=True, blank=True, default=None,
        verbose_name="Resumen del prompt de entrada"
    )
    
    # Skill que procesó la llamada — añadido directamente a BD, campo sincronizado
    skill_name = models.CharField(
        max_length=200, null=True, blank=True, default=None,
        verbose_name="Nombre del skill ejecutado"
    )
    
    # Campos faltantes detectados — añadido directamente a BD, campo sincronizado
    campos_faltantes = models.TextField(
        null=True, blank=True, default=None,
        verbose_name="Campos faltantes detectados"
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Fecha/hora de la llamada"
    )
    
    class Meta:
        verbose_name = "Registro de consumo IA"
        verbose_name_plural = "Registros de consumo IA"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['model_name']),
            models.Index(fields=['success']),
        ]
    
    def __str__(self):
        return (
            f"{self.model_name} | "
            f"{self.total_tokens} tokens | "
            f"{'OK' if self.success else 'ERROR'} | "
            f"{self.created_at.strftime('%d/%m/%Y %H:%M:%S') if self.created_at else 'sin fecha'}"
        )
    
    @classmethod
    def registrar_llamada(
        cls,
        model_name: str = 'deepseek-chat',
        endpoint: str = '',
        caller_app: str = '',
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        duration_ms: int = 0,
        success: bool = True,
        status_code: int = None,
        error_message: str = '',
    ) -> 'AIConsumptionLog':
        """
        Crea un registro de consumo de IA.
        
        Calcula automáticamente el costo estimado basado en los precios de DeepSeek:
        - Input: $0.14 por 1M tokens (deepseek-chat)
        - Output: $0.28 por 1M tokens (deepseek-chat)
        """
        # Precios DeepSeek (deepseek-chat)
        PRICE_INPUT_PER_1M = 0.14
        PRICE_OUTPUT_PER_1M = 0.28
        
        cost_input = (prompt_tokens / 1_000_000) * PRICE_INPUT_PER_1M
        cost_output = (completion_tokens / 1_000_000) * PRICE_OUTPUT_PER_1M
        estimated_cost = cost_input + cost_output
        
        return cls.objects.create(
            model_name=model_name,
            endpoint=endpoint,
            caller_app=caller_app,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens or (prompt_tokens + completion_tokens),
            estimated_cost_usd=round(estimated_cost, 8),
            duration_ms=duration_ms,
            success=success,
            status_code=status_code,
            error_message=error_message,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# MODELO: AgentExecution — Registro de ejecución de agentes (Fase 8)
# ═══════════════════════════════════════════════════════════════════════════════

class AgentExecution(models.Model):
    """
    Registro de ejecución de un agente para trazabilidad y dashboard.

    Análogo a SkillExecution pero para agentes. Cada ejecución de un agente
    (exitosa o no) queda registrada con la traza completa de pasos ReAct.

    SPEC: refactor_plataforma_agentes.md — Fase 8
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent_name = models.CharField(max_length=100, db_index=True,
                                  verbose_name="Nombre del agente")
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE,
        related_name='agent_executions',
        verbose_name="Conversación",
        null=True, blank=True,
    )
    steps = models.JSONField(
        default=list, blank=True,
        verbose_name="Pasos de ejecución",
        help_text="Lista de AgentStep serializados del ReAct loop"
    )
    iterations_used = models.IntegerField(default=0,
                                          verbose_name="Iteraciones usadas")
    success = models.BooleanField(default=False,
                                  verbose_name="¿Ejecución exitosa?")
    confidence = models.FloatField(default=0.0,
                                   verbose_name="Confianza del agente")
    total_cost_usd = models.DecimalField(
        max_digits=10, decimal_places=6, default=0,
        verbose_name="Costo total USD",
    )
    duration_ms = models.IntegerField(default=0,
                                      verbose_name="Duración (ms)")
    error_message = models.TextField(null=True, blank=True,
                                     verbose_name="Mensaje de error")
    created_at = models.DateTimeField(auto_now_add=True,
                                      verbose_name="Fecha de ejecución")

    class Meta:
        db_table = 'intelligence_agent_execution'
        verbose_name = 'Ejecución de Agente'
        verbose_name_plural = 'Ejecuciones de Agentes'
        indexes = [
            models.Index(fields=['agent_name', 'created_at']),
            models.Index(fields=['success', 'created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return (
            f"Agente {self.agent_name} - "
            f"{'✅' if self.success else '❌'} - "
            f"{self.created_at.strftime('%d/%m/%Y %H:%M') if self.created_at else 'sin fecha'}"
        )


class SystemTrace(models.Model):
    """Traza global, anónima y transversal de una interacción PIL."""

    STATUS_CHOICES = [
        ('started', 'Iniciada'),
        ('completed', 'Completada'),
        ('completed_degraded', 'Completada con fallback'),
        ('completed_empty', 'Completada sin resultados'),
        ('needs_review', 'Requiere revisión'),
        ('failed', 'Fallida'),
        ('timeout', 'Timeout'),
        ('blocked', 'Bloqueada por guardrail'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trace_id = models.CharField(max_length=64, unique=True, db_index=True)
    conversation = models.ForeignKey(
        Conversation, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='system_traces',
    )
    request_kind = models.CharField(max_length=50, default='unknown', db_index=True)
    normalized_query_hash = models.CharField(max_length=64, blank=True, default='', db_index=True)
    query_redacted = models.TextField(blank=True, default='')
    status = models.CharField(
        max_length=30, choices=STATUS_CHOICES, default='started', db_index=True,
    )
    technical_success = models.BooleanField(default=False)
    grounded = models.BooleanField(null=True, blank=True, db_index=True)
    result_count = models.IntegerField(null=True, blank=True)
    orchestration_mode = models.CharField(max_length=50, blank=True, default='')
    code_version = models.CharField(max_length=64, blank=True, default='unknown')
    config_version = models.CharField(max_length=64, blank=True, default='unknown')
    embedding_version = models.CharField(max_length=64, blank=True, default='unknown')
    latency_ms = models.IntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'intelligence_system_trace'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['status', 'started_at'], name='intel_trace_status_idx'),
            models.Index(fields=['request_kind', 'started_at'], name='intel_trace_kind_idx'),
            models.Index(fields=['grounded', 'started_at'], name='intel_trace_ground_idx'),
        ]

    def __str__(self):
        return f"{self.trace_id} · {self.status}"


class SystemEvent(models.Model):
    """Evento ordenado perteneciente a una SystemTrace."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trace = models.ForeignKey(
        SystemTrace, on_delete=models.CASCADE, related_name='events',
    )
    sequence = models.PositiveIntegerField()
    event_type = models.CharField(max_length=80, db_index=True)
    component = models.CharField(max_length=100, db_index=True)
    outcome = models.CharField(max_length=30, default='info', db_index=True)
    error_code = models.CharField(max_length=80, blank=True, default='', db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'intelligence_system_event'
        ordering = ['sequence']
        constraints = [
            models.UniqueConstraint(
                fields=['trace', 'sequence'],
                name='unique_event_sequence_per_trace',
            ),
        ]
        indexes = [
            models.Index(fields=['event_type', 'created_at'], name='intel_event_type_idx'),
            models.Index(fields=['error_code', 'created_at'], name='intel_event_error_idx'),
        ]

    def __str__(self):
        return f"{self.trace.trace_id} #{self.sequence} {self.event_type}"
