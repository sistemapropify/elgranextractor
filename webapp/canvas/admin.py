from django.contrib import admin
from .models import CardTemplate, Lienzo, NotaLienzo


@admin.register(CardTemplate)
class CardTemplateAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'user', 'campos_resumen', 'creado_en')
    list_filter = ('user',)
    search_fields = ('nombre',)

    def campos_resumen(self, obj):
        return ', '.join(obj.campos[:5]) if obj.campos else '—'
    campos_resumen.short_description = 'Campos'


@admin.register(Lienzo)
class LienzoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'user', 'estado', 'card_template', 'snapshot_resumen', 'actualizado_en')
    list_filter = ('estado', 'user')
    search_fields = ('nombre', 'descripcion')

    def snapshot_resumen(self, obj):
        nodos = len(obj.snapshot.get('nodos', []))
        aristas = len(obj.snapshot.get('aristas', []))
        return f"{nodos} nodos, {aristas} aristas"
    snapshot_resumen.short_description = 'Snapshot'


@admin.register(NotaLienzo)
class NotaLienzoAdmin(admin.ModelAdmin):
    list_display = ('pk', 'lienzo', 'color', 'x', 'y', 'creado_en')
    list_filter = ('lienzo',)
