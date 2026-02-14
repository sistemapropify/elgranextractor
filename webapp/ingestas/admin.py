from django.contrib import admin
from django.contrib import messages
from django.db.models import Count
from django.http import HttpResponseRedirect
from django.urls import path
from django.utils.html import format_html
from .models import CampoDinamico, MapeoFuente, PropiedadRaw, MigracionPendiente


@admin.register(CampoDinamico)
class CampoDinamicoAdmin(admin.ModelAdmin):
    list_display = ('nombre_campo_bd', 'titulo_display', 'tipo_dato', 'creado_por', 'creado_en')
    list_filter = ('tipo_dato', 'creado_en')
    search_fields = ('nombre_campo_bd', 'titulo_display')
    raw_id_fields = ('creado_por',)


@admin.register(MapeoFuente)
class MapeoFuenteAdmin(admin.ModelAdmin):
    list_display = ('nombre_fuente', 'portal_origen', 'creado_en', 'actualizado_en')
    list_filter = ('portal_origen', 'creado_en')
    search_fields = ('nombre_fuente', 'portal_origen')


@admin.register(PropiedadRaw)
class PropiedadRawAdmin(admin.ModelAdmin):
    list_display = (
        'tipo_propiedad', 'precio_usd', 'moneda', 'ubicacion',
        'metros_cuadrados', 'habitaciones', 'banos', 'estacionamientos',
        'fuente_excel', 'fecha_ingesta'
    )
    list_filter = ('tipo_propiedad', 'moneda', 'fuente_excel', 'fecha_ingesta')
    search_fields = ('ubicacion', 'descripcion', 'fuente_excel')
    readonly_fields = ('fecha_ingesta',)
    fieldsets = (
        ('Información Básica', {
            'fields': ('fuente_excel', 'fecha_ingesta', 'tipo_propiedad', 'precio_usd', 'moneda')
        }),
        ('Características', {
            'fields': ('ubicacion', 'metros_cuadrados', 'habitaciones', 'banos', 'estacionamientos')
        }),
        ('Detalles', {
            'fields': ('descripcion', 'url_fuente', 'atributos_extras')
        }),
    )
    actions = ['borrar_todos', 'borrar_seleccionados', 'importar_desde_excel']

    def borrar_todos(self, request, queryset):
        """Borra todos los registros de PropiedadRaw (ignora el queryset)."""
        from django.db import connection
        from django.conf import settings
        engine = settings.DATABASES['default']['ENGINE']
        with connection.cursor() as cursor:
            if 'sqlserver' in engine or 'mssql' in engine:
                cursor.execute('TRUNCATE TABLE ingestas_propiedadraw')
            else:
                cursor.execute('TRUNCATE TABLE ingestas_propiedadraw RESTART IDENTITY CASCADE')
        count = cursor.rowcount if cursor.rowcount else 'todos'
        self.message_user(request, f'Se borraron {count} registros de PropiedadRaw.', messages.SUCCESS)
    borrar_todos.short_description = "Borrar TODOS los registros (TRUNCATE)"

    def borrar_seleccionados(self, request, queryset):
        """Borra los registros seleccionados."""
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f'Se borraron {count} registros seleccionados.', messages.SUCCESS)
    borrar_seleccionados.short_description = "Borrar registros seleccionados"

    def importar_desde_excel(self, request, queryset):
        """Redirige a la vista de importación desde Excel."""
        from django.urls import reverse
        from django.http import HttpResponseRedirect
        # Ignorar queryset, redirigir a la vista personalizada
        url = reverse('admin:ingestas_propiedadraw_importar_excel')
        return HttpResponseRedirect(url)
    importar_desde_excel.short_description = "Importar registros desde Excel"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('borrar-todo/', self.admin_site.admin_view(self.borrar_todo_view), name='ingestas_propiedadraw_borrar_todo'),
            path('importar-excel/', self.admin_site.admin_view(self.importar_excel_view), name='ingestas_propiedadraw_importar_excel'),
        ]
        return custom_urls + urls

    def borrar_todo_view(self, request):
        """Vista personalizada para borrar todos los registros con confirmación."""
        from django.shortcuts import render
        from django.db import connection

        if request.method == 'POST':
            confirm = request.POST.get('confirm')
            if confirm == 'si':
                with connection.cursor() as cursor:
                    cursor.execute('TRUNCATE TABLE ingestas_propiedadraw RESTART IDENTITY CASCADE')
                self.message_user(request, 'Todos los registros de PropiedadRaw han sido borrados.', messages.SUCCESS)
                return HttpResponseRedirect('../../')
            else:
                self.message_user(request, 'Operación cancelada.', messages.WARNING)
                return HttpResponseRedirect('../../')

        # Obtener conteo actual
        with connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM ingestas_propiedadraw')
            total = cursor.fetchone()[0]

        context = {
            'title': 'Borrar todos los registros de PropiedadRaw',
            'total': total,
            'opts': self.model._meta,
        }
        return render(request, 'admin/ingestas/borrar_todo_confirm.html', context)

    def importar_excel_view(self, request):
        """Vista personalizada para importar registros desde un archivo Excel."""
        from django.shortcuts import render
        import pandas as pd
        import os
        from django.core.files.storage import FileSystemStorage
        from django.conf import settings
        from decimal import Decimal, InvalidOperation

        if request.method == 'POST' and request.FILES.get('excel_file'):
            excel_file = request.FILES['excel_file']
            hoja = request.POST.get('hoja', 0)
            fuente = request.POST.get('fuente', 'excel_importado')

            # Guardar archivo temporalmente
            fs = FileSystemStorage(location=settings.MEDIA_ROOT)
            filename = fs.save(excel_file.name, excel_file)
            file_path = fs.path(filename)

            try:
                # Leer Excel
                df = pd.read_excel(file_path, sheet_name=hoja, dtype=str)
                total_filas = len(df)
                exitos = 0
                errores = 0

                # Mapeo de columnas (simplificado)
                columnas_excel = df.columns.tolist()
                campos_modelo = [f.name for f in PropiedadRaw._meta.get_fields()]
                mapeo = {}
                for col in columnas_excel:
                    col_clean = str(col).strip().lower().replace(' ', '_')
                    for campo in campos_modelo:
                        if campo.lower() == col_clean:
                            mapeo[col] = campo
                            break

                # Procesar filas
                for _, fila in df.iterrows():
                    try:
                        datos = {}
                        for col, campo in mapeo.items():
                            valor = fila[col]
                            if pd.isna(valor):
                                datos[campo] = None
                                continue
                            field = PropiedadRaw._meta.get_field(campo)
                            if field.get_internal_type() == 'DecimalField':
                                try:
                                    if isinstance(valor, str):
                                        valor = valor.replace('$', '').replace(',', '').strip()
                                    datos[campo] = Decimal(str(valor))
                                except (InvalidOperation, ValueError):
                                    datos[campo] = None
                            elif field.get_internal_type() == 'IntegerField':
                                try:
                                    datos[campo] = int(float(valor))
                                except (ValueError, TypeError):
                                    datos[campo] = None
                            else:
                                datos[campo] = str(valor) if not pd.isna(valor) else None

                        if 'fuente_excel' not in datos:
                            datos['fuente_excel'] = fuente

                        PropiedadRaw.objects.create(**datos)
                        exitos += 1
                    except Exception as e:
                        errores += 1
                        # Continuar con siguiente fila

                # Eliminar archivo temporal
                os.remove(file_path)

                self.message_user(
                    request,
                    f'Importación completada: {exitos} registros exitosos, {errores} errores.',
                    messages.SUCCESS
                )
                return HttpResponseRedirect('../../')
            except Exception as e:
                # Si hay error, eliminar archivo y mostrar mensaje
                if os.path.exists(file_path):
                    os.remove(file_path)
                self.message_user(
                    request,
                    f'Error al importar el archivo: {e}',
                    messages.ERROR
                )
                return HttpResponseRedirect('.')

        # GET: mostrar formulario
        context = {
            'title': 'Importar registros desde Excel',
            'opts': self.model._meta,
        }
        return render(request, 'admin/ingestas/importar_excel.html', context)


@admin.register(MigracionPendiente)
class MigracionPendienteAdmin(admin.ModelAdmin):
    list_display = ('nombre_campo_bd', 'titulo_display', 'tipo_dato', 'estado', 'ejecutada_en', 'creado_en')
    list_filter = ('estado', 'tipo_dato', 'creado_en')
    search_fields = ('nombre_campo_bd', 'titulo_display', 'error_mensaje')
    readonly_fields = ('creado_en',)