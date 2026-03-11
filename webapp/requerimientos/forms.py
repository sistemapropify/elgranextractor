# Formularios para el módulo de requerimientos (pendientes de nueva implementación)
# Los formularios anteriores de subida de Excel han sido eliminados.
# Se crearán nuevos formularios según la nueva forma de subir Excel.

from django import forms
from django.core.exceptions import ValidationError
import pandas as pd
import os


class SubirExcelRequerimientoForm(forms.Form):
    """Formulario para subir un archivo Excel con requerimientos."""
    archivo_excel = forms.FileField(
        label='Archivo Excel',
        help_text='Suba un archivo Excel (.xlsx, .xls) con los requerimientos. Las columnas deben coincidir con los campos del modelo.'
    )
    hoja = forms.CharField(
        label='Nombre de la hoja',
        initial='Sheet1',
        help_text='Nombre de la hoja dentro del Excel (por defecto: Sheet1)',
        required=False
    )
    empezar_fila = forms.IntegerField(
        label='Fila de inicio',
        initial=2,
        help_text='Número de fila donde empiezan los datos (la fila 1 suele ser encabezados)',
        min_value=1
    )
    
    def clean_archivo_excel(self):
        archivo = self.cleaned_data['archivo_excel']
        ext = os.path.splitext(archivo.name)[1].lower()
        if ext not in ['.xlsx', '.xls']:
            raise ValidationError('Solo se permiten archivos Excel (.xlsx, .xls)')
        return archivo