from django import forms
from .models import Agente, Inmobiliaria


class InmobiliariaForm(forms.ModelForm):
    """Formulario para crear/editar una inmobiliaria."""

    class Meta:
        model = Inmobiliaria
        fields = ['nombre', 'direccion', 'latitud', 'longitud', 'logo', 'icono_marcador']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Inmobiliaria Arequipa SAC',
            }),
            'direccion': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Ej: Av. Ejército 123, Cayma, Arequipa',
            }),
            'latitud': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.000001',
                'placeholder': 'Ej: -16.398764',
            }),
            'longitud': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.000001',
                'placeholder': 'Ej: -71.536887',
            }),
            'logo': forms.FileInput(attrs={
                'class': 'form-control-acm',
                'accept': '.png,.jpg,.jpeg,.svg',
            }),
            'icono_marcador': forms.FileInput(attrs={
                'class': 'form-control-acm',
                'accept': '.png',
            }),
        }

    def clean_latitud(self):
        latitud = self.cleaned_data.get('latitud')
        if latitud is not None and (latitud < -90 or latitud > 90):
            raise forms.ValidationError('La latitud debe estar entre -90 y 90.')
        return latitud

    def clean_longitud(self):
        longitud = self.cleaned_data.get('longitud')
        if longitud is not None and (longitud < -180 or longitud > 180):
            raise forms.ValidationError('La longitud debe estar entre -180 y 180.')
        return longitud


class AgenteForm(forms.ModelForm):
    """Formulario para crear/editar un agente."""

    class Meta:
        model = Agente
        fields = [
            'nombre_completo', 'codigo_agente', 'correo_electronico', 'telefono',
            'tipo_agente', 'inmobiliaria',
            'sitio_web', 'facebook_url', 'instagram_url', 'linkedin_url',
        ]
        widgets = {
            'nombre_completo': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Juan Pérez García',
            }),
            'codigo_agente': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: AG-001',
            }),
            'correo_electronico': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'ej: juan.perez@email.com',
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: +51999888777',
            }),
            'tipo_agente': forms.Select(attrs={
                'class': 'form-select',
            }),
            'inmobiliaria': forms.Select(attrs={
                'class': 'form-select',
            }),
            'sitio_web': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://mipagina.com',
            }),
            'facebook_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://facebook.com/miperfil',
            }),
            'instagram_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://instagram.com/miperfil',
            }),
            'linkedin_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://linkedin.com/in/miperfil',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ordenar inmobiliarias alfabéticamente
        self.fields['inmobiliaria'].queryset = Inmobiliaria.objects.all().order_by('nombre')
        self.fields['inmobiliaria'].empty_label = '--- Seleccione una inmobiliaria ---'
        # Marcar campos de redes como no requeridos
        for field in ['sitio_web', 'facebook_url', 'instagram_url', 'linkedin_url']:
            self.fields[field].required = False

    def clean(self):
        cleaned_data = super().clean()
        tipo_agente = cleaned_data.get('tipo_agente')
        inmobiliaria = cleaned_data.get('inmobiliaria')

        if tipo_agente == 'INMOBILIARIA' and not inmobiliaria:
            raise forms.ValidationError(
                'Debe seleccionar una inmobiliaria cuando el tipo es "Inmobiliaria".'
            )

        return cleaned_data
