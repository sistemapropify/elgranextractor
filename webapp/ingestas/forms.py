from django import forms
from django.forms import formset_factory


class SubirExcelForm(forms.Form):
    """Formulario para subir archivo Excel."""
    archivo = forms.FileField(
        label="Archivo Excel/CSV",
        help_text="Formatos soportados: .xlsx, .xls, .csv"
    )
    nombre_fuente = forms.CharField(
        max_length=100,
        label="Nombre de la fuente",
        help_text="Ej: PortalInmobiliarioXYZ"
    )
    portal_origen = forms.CharField(
        max_length=50,
        label="Portal de origen",
        help_text="Ej: urbania, adondevivir, etc."
    )


class MapeoColumnaForm(forms.Form):
    """Formulario dinámico para mapear una columna del Excel."""
    columna_origen = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )
    campo_bd = forms.CharField(
        label="Nombre en BD (snake_case)",
        max_length=100,
        help_text="Ej: tipo_propiedad, precio_usd, etc."
    )
    titulo_display = forms.CharField(
        label="Título para mostrar",
        max_length=150,
        help_text="Ej: Tipo de Propiedad, Precio USD, etc."
    )
    tipo_dato = forms.ChoiceField(
        label="Tipo de dato",
        choices=[
            ('VARCHAR', 'Texto (VARCHAR)'),
            ('INTEGER', 'Número entero (INTEGER)'),
            ('DECIMAL', 'Número decimal (DECIMAL)'),
            ('BOOLEAN', 'Verdadero/Falso (BOOLEAN)'),
            ('DATE', 'Fecha (DATE)'),
            ('DATETIME', 'Fecha y hora (DATETIME)'),
        ],
        help_text="Selecciona el tipo de dato que almacenará este campo."
    )
    incluir = forms.BooleanField(
        label="Incluir en importación",
        required=False,
        initial=True,
        help_text="Marcar para incluir esta columna en la importación."
    )
    crear_campo = forms.BooleanField(
        label="Crear campo ahora",
        required=False,
        initial=False,
        help_text="Marcar para ejecutar migración inmediata."
    )


# Formset para múltiples columnas
ValidarMapeoFormSet = formset_factory(
    MapeoColumnaForm,
    extra=0,
    can_delete=False
)


class ProcesarTodoForm(forms.Form):
    """Formulario para procesar todas las filas después de mapear."""
    confirmar = forms.BooleanField(
        label="Confirmar procesamiento de todas las filas",
        required=True,
        help_text="Al confirmar, se importarán todas las filas del Excel a la base de datos."
    )


from django.forms import ModelForm
from .models import PropiedadRaw

class PropiedadRawForm(ModelForm):
    """Formulario para editar propiedades."""
    class Meta:
        model = PropiedadRaw
        exclude = ['fecha_ingesta']  # Excluir campo automático
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 4}),
            'imagenes_propiedad': forms.Textarea(attrs={'rows': 3}),
            'atributos_extras': forms.Textarea(attrs={'rows': 3, 'placeholder': 'JSON de atributos extras'}),
            'fecha_publicacion': forms.DateInput(attrs={'type': 'date'}),
            'fecha_venta': forms.DateInput(attrs={'type': 'date'}),
        }