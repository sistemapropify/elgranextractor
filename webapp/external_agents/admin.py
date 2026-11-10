from django.contrib import admin

from .models import DocumentType, ExternalAgent, ExternalAgentAttachment


@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'scope', 'is_active', 'sort_order', 'updated_at']
    list_filter = ['scope', 'is_active']
    search_fields = ['name']
    ordering = ['scope', 'sort_order', 'name']


class ExternalAgentAttachmentInline(admin.TabularInline):
    model = ExternalAgentAttachment
    extra = 0
    fields = ['document_type', 'file', 'original_name', 'uploaded_by_username']
    readonly_fields = ['original_name', 'uploaded_by_username']


@admin.register(ExternalAgent)
class ExternalAgentAdmin(admin.ModelAdmin):
    list_display = [
        'full_name',
        'personal_document_type',
        'document_number',
        'email',
        'mobile',
        'level',
        'is_active',
        'updated_at',
    ]
    list_filter = ['is_active', 'level', 'personal_document_type']
    search_fields = [
        'full_name',
        'document_number',
        'email',
        'mobile',
    ]
    raw_id_fields = []
    readonly_fields = [
        'created_by_username',
        'updated_by_username',
        'created_at',
        'updated_at',
    ]
    inlines = [ExternalAgentAttachmentInline]
