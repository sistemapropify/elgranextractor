from django.contrib import admin
from django.utils.html import format_html
from .models import Role, User, AppConfig, Conversation, Fact


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'level', 'created_at', 'updated_at')
    list_filter = ('level',)
    search_fields = ('name', 'description')
    readonly_fields = ('id', 'created_at', 'updated_at')
    fieldsets = (
        ('Información Básica', {
            'fields': ('id', 'name', 'level', 'description')
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
