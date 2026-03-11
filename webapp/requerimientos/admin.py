from django.contrib import admin
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import path
from .models import Requerimiento
from .forms import SubirExcelRequerimientoForm
import pandas as pd
import os
from datetime import datetime


@admin.register(Requerimiento)
class RequerimientoAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'fuente',
        'fecha',
        'hora',
        'agente',
        'condicion',
        'tipo_propiedad',
        'distritos',
        'presupuesto_display',
        'es_urgente',
    )
    list_filter = (
        'fuente',
        'condicion',
        'tipo_propiedad',
        'presupuesto_moneda',
        'presupuesto_forma_pago',
    )
    search_fields = (
        'agente',
        'distritos',
        'caracteristicas_extra',
        'requerimiento',
    )
    readonly_fields = ('creado_en', 'actualizado_en')
    fieldsets = (
        ('Origen', {
            'fields': ('fuente', 'fecha', 'hora', 'agente', 'agente_telefono', 'tipo_original')
        }),
        ('Requerimiento', {
            'fields': ('condicion', 'tipo_propiedad', 'distritos', 'requerimiento')
        }),
        ('Presupuesto', {
            'fields': ('presupuesto_monto', 'presupuesto_moneda', 'presupuesto_forma_pago')
        }),
        ('Características', {
            'fields': ('habitaciones', 'banos', 'cochera', 'ascensor', 'amueblado', 'area_m2', 'piso_preferencia')
        }),
        ('Extras', {
            'fields': ('caracteristicas_extra',)
        }),
        ('Auditoría', {
            'fields': ('creado_en', 'actualizado_en')
        }),
    )
    change_list_template = 'admin/requerimientos/requerimiento_change_list.html'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('importar-excel/', self.admin_site.admin_view(self.importar_excel_view), name='requerimientos_requerimiento_importar_excel'),
        ]
        return custom_urls + urls
    
    def importar_excel_view(self, request):
        """Vista para importar requerimientos desde Excel."""
        if request.method == 'POST':
            form = SubirExcelRequerimientoForm(request.POST, request.FILES)
            if form.is_valid():
                archivo = form.cleaned_data['archivo_excel']
                hoja = form.cleaned_data['hoja'] or 'Sheet1'
                empezar_fila = form.cleaned_data['empezar_fila']
                
                try:
                    # Leer el Excel
                    df = pd.read_excel(archivo, sheet_name=hoja, header=empezar_fila-1)
                    
                    # Mostrar columnas detectadas (para depuración)
                    columnas_detectadas = list(df.columns)
                    print(f"Columnas detectadas: {columnas_detectadas}")
                    
                    # Contador de registros creados
                    creados = 0
                    errores = []
                    
                    # Mapeo de columnas Excel a campos del modelo
                    # Clave: nombre del campo en el modelo Requerimiento
                    # Valor: nombre de columna en el Excel (exacto)
                    mapeo_columnas = {
                        'fuente': 'Fuente',
                        'fecha': 'Fecha',
                        'hora': 'Hora',
                        'agente': 'Agente',
                        'agente_telefono': 'Tel Agente',
                        'tipo_original': 'Tipo Original',
                        'condicion': 'Condicion',
                        'tipo_propiedad': 'Tipo Propiedad',
                        'distritos': 'Distritos',
                        'requerimiento': 'Requerimiento',
                        'presupuesto_monto': 'Presupuesto Monto',
                        'presupuesto_moneda': 'Moneda',
                        'presupuesto_forma_pago': 'Forma Pago',
                        'habitaciones': 'Habitaciones',
                        'banos': 'Banos',
                        'cochera': 'Cochera',
                        'ascensor': 'Ascensor',
                        'amueblado': 'Amueblado',
                        'area_m2': 'Area m2',
                        'piso_preferencia': 'Piso Preferencia',
                        'caracteristicas_extra': 'Caracteristicas Extra',
                        # 'es_urgente' no está en el Excel, se dejará como None
                    }
                    
                    # Función para convertir valores
                    def convertir_valor(campo, valor):
                        if pd.isna(valor):
                            return None
                        # Si es string, strip
                        if isinstance(valor, str):
                            valor = valor.strip()
                            if valor == '':
                                return None
                        # Campos booleanos
                        if campo == 'es_urgente':
                            if isinstance(valor, bool):
                                return valor
                            if isinstance(valor, (int, float)):
                                return bool(valor)
                            if isinstance(valor, str):
                                lower = valor.lower()
                                if lower in ('si', 'sí', 'true', 'verdadero', '1', 'yes'):
                                    return True
                                elif lower in ('no', 'false', 'falso', '0'):
                                    return False
                        # Campos numéricos
                        if campo in ('habitaciones', 'banos', 'cochera', 'ascensor', 'piso_preferencia'):
                            if valor is None:
                                return None
                            try:
                                return int(float(valor))
                            except:
                                return None
                        if campo == 'area_m2':
                            if valor is None:
                                return None
                            try:
                                return float(valor)
                            except:
                                return None
                        if campo == 'presupuesto_monto':
                            if valor is None:
                                return None
                            try:
                                return float(valor)
                            except:
                                return None
                        # Campos de fecha/hora (pandas ya los convierte a Timestamp)
                        if campo == 'fecha' and isinstance(valor, pd.Timestamp):
                            return valor.date()
                        if campo == 'hora' and isinstance(valor, pd.Timestamp):
                            return valor.time()
                        # Normalizar fuente a choices
                        if campo == 'fuente' and isinstance(valor, str):
                            valor = valor.strip().lower()
                            if 'inmobiliarias unidas' in valor:
                                return 'inmobiliarias_unidas'
                            elif 'éxito' in valor or 'exito' in valor:
                                return 'exito_inmobiliario'
                            else:
                                return 'otro'
                        return valor
                    
                    for idx, row in df.iterrows():
                        try:
                            datos = {}
                            for campo_modelo, col_excel in mapeo_columnas.items():
                                if col_excel in df.columns:
                                    valor = row[col_excel]
                                    datos[campo_modelo] = convertir_valor(campo_modelo, valor)
                                else:
                                    # Si la columna no existe, dejar como None
                                    datos[campo_modelo] = None
                            
                            # No asignar valores por defecto, respetar los datos del Excel
                            
                            # Crear el requerimiento
                            Requerimiento.objects.create(**datos)
                            creados += 1
                        except Exception as e:
                            errores.append(f"Fila {idx + empezar_fila + 1}: {str(e)}")
                    
                    if errores:
                        self.message_user(request, f'Importación completada con {len(errores)} errores. {creados} requerimientos creados. Errores: {", ".join(errores[:5])}', level=messages.WARNING)
                    else:
                        self.message_user(request, f'¡Importación exitosa! {creados} requerimientos creados.', level=messages.SUCCESS)
                    
                    return redirect('..')
                    
                except Exception as e:
                    self.message_user(request, f'Error al procesar el archivo: {str(e)}', level=messages.ERROR)
        else:
            form = SubirExcelRequerimientoForm()
        
        context = {
            'form': form,
            'opts': self.model._meta,
            'title': 'Importar Requerimientos desde Excel',
        }
        return render(request, 'admin/requerimientos/importar_excel.html', context)
