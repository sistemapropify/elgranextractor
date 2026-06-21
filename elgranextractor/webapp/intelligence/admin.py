from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Role, User, AppConfig, Conversation, Fact,
    IntelligenceCollection, IntelligenceDocument,
    EpisodicMemory, UserIntelligenceProfile
)

# ─── Constantes para choices ────────────────────────────────────────────────
LEVEL_CHOICES = [
    (1, '1 - Consulta básica'),
    (2, '2 - Consulta avanzada'),
    (3, '3 - Análisis'),
    (4, '4 - Edición'),
    (5, '5 - Administración total'),
]

DOMAIN_CHOICES = [
    ('publico', 'Público'),
    ('legal', 'Legal'),
    ('marketing', 'Marketing'),
    ('escuela', 'Escuela'),
    ('gerencia', 'Gerencia'),
    ('ti', 'TI'),
    ('general', 'General'),
]


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'default_level', 'max_level', 'default_domains_display', 'created_at', 'updated_at')
    list_filter = ('default_level', 'max_level')
    search_fields = ('name', 'description')
    readonly_fields = ('id', 'created_at', 'updated_at')
    fieldsets = (
        ('Información Básica', {
            'fields': ('id', 'name', 'description')
        }),
        ('Niveles de Inteligencia', {
            'fields': ('default_level', 'max_level', 'default_domains'),
            'description': 'Configuración de niveles y dominios por defecto para usuarios de este rol'
        }),
        ('Capacidades', {
            'fields': ('capabilities',),
            'description': 'Configuración JSON de capacidades del rol'
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def default_domains_display(self, obj):
        """Muestra los dominios por defecto de forma legible"""
        if not obj.default_domains:
            return "Sin dominios"
        domain_labels = dict(DOMAIN_CHOICES)
        return ", ".join(domain_labels.get(d, d) for d in obj.default_domains)
    default_domains_display.short_description = "Dominios por defecto"


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('phone', 'email', 'role', 'is_active', 'created_at')
    list_filter = ('role', 'is_active', 'created_at')
    search_fields = ('phone', 'email')
    readonly_fields = ('id', 'created_at', 'updated_at')
    fieldsets = (
        ('Identificación', {
            'fields': ('id', 'phone', 'email', 'role')
        }),
        ('Estado', {
            'fields': ('is_active', 'metadata')
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(AppConfig)
class AppConfigAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'level', 'is_active', 'created_at')
    list_filter = ('level', 'is_active')
    search_fields = ('id', 'name')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Identificación', {
            'fields': ('id', 'name', 'level', 'is_active')
        }),
        ('Configuración', {
            'fields': ('capabilities', 'config'),
            'description': 'Capacidades y configuración adicional de la app'
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('session_id', 'user', 'app', 'is_active', 'last_message_at', 'created_at')
    list_filter = ('app', 'is_active', 'created_at')
    search_fields = ('session_id', 'user__phone', 'user__email')
    readonly_fields = ('id', 'created_at', 'updated_at', 'last_message_at')
    fieldsets = (
        ('Identificación', {
            'fields': ('id', 'session_id', 'user', 'app', 'is_active')
        }),
        ('Contenido', {
            'fields': ('messages', 'metadata'),
            'description': 'Mensajes en formato JSON y metadatos adicionales'
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at', 'last_message_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Fact)
class FactAdmin(admin.ModelAdmin):
    list_display = ('subject', 'relation', 'object', 'user', 'confidence', 'is_active', 'created_at')
    list_filter = ('relation', 'is_active', 'created_at')
    search_fields = ('subject', 'object', 'user__phone', 'user__email')
    readonly_fields = ('id', 'created_at', 'updated_at')
    fieldsets = (
        ('Hecho', {
            'fields': ('id', 'subject', 'relation', 'object', 'confidence')
        }),
        ('Contexto', {
            'fields': ('user', 'source_conversation', 'metadata')
        }),
        ('Estado', {
            'fields': ('is_active',)
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def __str__(self):
        return f"{self.subject} {self.relation} {self.object}"


@admin.register(IntelligenceCollection)
class IntelligenceCollectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'table_name', 'min_level', 'domain', 'is_public', 'is_active', 'document_count', 'last_sync_at', 'created_at')
    list_filter = ('min_level', 'domain', 'is_public', 'is_active', 'created_at')
    search_fields = ('name', 'table_name', 'description')
    readonly_fields = ('id', 'created_at', 'updated_at', 'document_count', 'last_sync_count')
    fieldsets = (
        ('Identificación', {
            'fields': ('id', 'name', 'table_name', 'description', 'is_active')
        }),
        ('Nivel de Acceso', {
            'fields': ('min_level', 'domain', 'is_public'),
            'description': 'Configuración de nivel mínimo, dominio y visibilidad pública'
        }),
        ('Configuración SQL', {
            'fields': ('source_sql', 'field_definitions', 'embedding_fields', 'display_fields', 'filter_fields'),
            'classes': ('collapse',),
            'description': 'Configuración de origen de datos y campos para embedding'
        }),
        ('Control de Acceso', {
            'fields': ('roles_con_acceso', 'apps_con_acceso'),
            'classes': ('collapse',),
            'description': 'Configuración de roles y apps con acceso a esta colección'
        }),
        ('Sincronización', {
            'fields': ('last_sync_at', 'last_sync_count'),
            'classes': ('collapse',),
            'description': 'Información de la última sincronización de datos'
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def document_count(self, obj):
        """Muestra el número de documentos en la colección"""
        return obj.documents.count()
    document_count.short_description = "Documentos"


@admin.register(IntelligenceDocument)
class IntelligenceDocumentAdmin(admin.ModelAdmin):
    list_display = ('id_short', 'collection', 'source_id', 'has_embedding', 'created_at')
    list_filter = ('collection', 'created_at')
    search_fields = ('source_id', 'content')
    readonly_fields = ('id', 'created_at', 'updated_at', 'content_preview', 'has_embedding_display')
    exclude = ('embedding',)  # Excluir el campo embedding del formulario
    fieldsets = (
        ('Identificación', {
            'fields': ('id', 'collection', 'source_id')
        }),
        ('Contenido', {
            'fields': ('content', 'field_values', 'content_hash'),
            'description': 'Contenido del documento y valores de campos'
        }),
        ('Embedding', {
            'fields': ('has_embedding_display',),
            'classes': ('collapse',),
            'description': 'Estado del embedding vectorial'
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def id_short(self, obj):
        """Muestra una versión corta del ID"""
        return str(obj.id)[:8] + "..."
    id_short.short_description = "ID"
    
    def has_embedding(self, obj):
        """Indica si el documento tiene embedding"""
        return bool(obj.embedding)
    has_embedding.boolean = True
    has_embedding.short_description = "Embedding"
    
    def has_embedding_display(self, obj):
        """Muestra el estado del embedding"""
        if obj.embedding:
            return "✅ Con embedding"
        return "❌ Sin embedding"
    has_embedding_display.short_description = "Estado del embedding"
    
    def content_preview(self, obj):
        """Muestra una vista previa del contenido"""
        if obj.content:
            preview = obj.content[:100]
            if len(obj.content) > 100:
                preview += "..."
            return preview
        return "(vacío)"
    content_preview.short_description = "Vista previa"


@admin.register(EpisodicMemory)
class EpisodicMemoryAdmin(admin.ModelAdmin):
    list_display = ('id_short', 'user', 'episode_type', 'intent_detected', 'importance_score', 'timestamp', 'has_feedback')
    list_filter = ('episode_type', 'importance_score', 'timestamp', 'is_active')
    search_fields = ('user_message', 'assistant_response', 'intent_detected')
    readonly_fields = ('id', 'created_at', 'updated_at', 'user_message_preview', 'response_preview')
    exclude = ('user_message_embedding',)
    fieldsets = (
        ('Identificación', {
            'fields': ('id', 'user', 'conversation', 'timestamp')
        }),
        ('Interacción', {
            'fields': ('user_message_preview', 'response_preview', 'episode_type', 'intent_detected'),
            'description': 'Contenido de la interacción (solo vista previa)'
        }),
        ('Contexto', {
            'fields': ('context', 'rag_context_used', 'memory_context_used'),
            'classes': ('collapse',),
            'description': 'Contexto completo de la interacción'
        }),
        ('Feedback', {
            'fields': ('feedback',),
            'classes': ('collapse',),
            'description': 'Feedback del usuario sobre esta respuesta'
        }),
        ('Métricas', {
            'fields': ('importance_score', 'latency_ms', 'is_active'),
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    actions = ['mark_as_inactive', 'mark_as_active']

    def id_short(self, obj):
        return str(obj.id)[:8] + "..."
    id_short.short_description = "ID"

    def user_message_preview(self, obj):
        if obj.user_message:
            preview = obj.user_message[:150]
            if len(obj.user_message) > 150:
                preview += "..."
            return preview
        return "(vacío)"
    user_message_preview.short_description = "Mensaje del usuario"

    def response_preview(self, obj):
        if obj.assistant_response:
            preview = obj.assistant_response[:150]
            if len(obj.assistant_response) > 150:
                preview += "..."
            return preview
        return "(vacío)"
    response_preview.short_description = "Respuesta del asistente"

    def has_feedback(self, obj):
        fb = obj.feedback or {}
        return bool(fb.get('thumbs_up')) or bool(fb.get('thumbs_down'))
    has_feedback.boolean = True
    has_feedback.short_description = "Feedback"

    def mark_as_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} episodio(s) marcados como inactivos.")
    mark_as_inactive.short_description = "Marcar como inactivos"

    def mark_as_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} episodio(s) marcados como activos.")
    mark_as_active.short_description = "Marcar como activos"


@admin.register(UserIntelligenceProfile)
class UserIntelligenceProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'level', 'allowed_domains_display', 'extra_count', 'blocked_count', 'created_at')
    list_filter = ('level', 'created_at')
    search_fields = ('user__phone', 'user__email')
    readonly_fields = ('id', 'created_at', 'updated_at')
    filter_horizontal = ('extra_collections', 'blocked_collections')
    fieldsets = (
        ('Identificación', {
            'fields': ('id', 'user', 'level')
        }),
        ('Dominios Permitidos', {
            'fields': ('allowed_domains',),
            'description': 'Lista de dominios a los que el usuario tiene acceso (JSON)'
        }),
        ('Colecciones', {
            'fields': ('extra_collections', 'blocked_collections'),
            'description': 'Colecciones adicionales (extra) y bloqueadas (blocked)'
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def allowed_domains_display(self, obj):
        if not obj.allowed_domains:
            return "Sin dominios"
        domain_labels = dict(DOMAIN_CHOICES)
        return ", ".join(domain_labels.get(d, d) for d in obj.allowed_domains)
    allowed_domains_display.short_description = "Dominios"

    def extra_count(self, obj):
        return obj.extra_collections.count()
    extra_count.short_description = "Extra"

    def blocked_count(self, obj):
        return obj.blocked_collections.count()
    blocked_count.short_description = "Bloqueadas"
