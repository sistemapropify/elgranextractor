import re
import unicodedata

from django import forms
from .models import PropertyProspect


DISTRICTS_AREQUIPA = (
    'Alto Selva Alegre', 'Cayma', 'Cerro Colorado', 'Characato', 'Chiguata',
    'Jacobo Hunter', 'José Luis Bustamante y Rivero', 'La Joya',
    'Mariano Melgar', 'Miraflores', 'Mollebaya', 'Paucarpata', 'Pocsi',
    'Polobaya', 'Quequeña', 'Sabandía', 'Sachaca', 'Socabaya', 'Tiabaya',
    'Uchumayo', 'Yanahuara', 'Yarabamba', 'Yura',
)


def _plain(value):
    return ''.join(
        char for char in unicodedata.normalize('NFKD', str(value or '').lower())
        if not unicodedata.combining(char)
    )


def district_from_address(address):
    """Infer a known district only when its full name occurs in the address."""
    normalized = _plain(address)
    for district in sorted(DISTRICTS_AREQUIPA, key=len, reverse=True):
        name = _plain(district)
        if re.search(r'(?<![a-z0-9])' + re.escape(name) + r'(?![a-z0-9])', normalized):
            return district
    return ''


class ProspectCaptureForm(forms.ModelForm):
    """Guarda una captura completa, igual que la aplicación Propitools."""

    origin = forms.ChoiceField(
        choices=[('', '— Seleccionar —'), *PropertyProspect.ORIGIN_CHOICES],
        error_messages={'required': 'Selecciona el origen de la prospección.'},
    )

    def __init__(self, data=None, *args, **kwargs):
        if data is not None:
            data = data.copy()
            # Un campo oculto de otro origen no debe impedir guardar.
            if data.get('origin') != 'marketplace':
                data['marketplace_url'] = ''
            if data.get('origin') != 'otros':
                data['origin_other'] = ''
        super().__init__(data, *args, **kwargs)

    class Meta:
        model = PropertyProspect
        fields = [
            'photo',
            'origin', 'origin_other', 'marketplace_url',
            'owner_name', 'phone',
            'operation_type', 'contract_type', 'property_type',
            'price', 'currency',
            'bedrooms', 'area_m2',
            'address', 'zone', 'district', 'latitude', 'longitude',
            'notes',
        ]

    def clean(self):
        cleaned = super().clean()
        origin = cleaned.get('origin')
        url = (cleaned.get('marketplace_url') or '').strip()
        if origin == 'marketplace' and not url:
            self.add_error(
                'marketplace_url',
                'Es obligatorio guardar el enlace del anuncio para poder guardar.',
            )
        if self.data.get('photo_expected') == '1' and not self.files.get('photo'):
            self.add_error('photo', 'La foto seleccionada no llegó al servidor. Selecciónala nuevamente y vuelve a guardar.')
        for field in ('price', 'area_m2'):
            value = cleaned.get(field)
            if value is not None and value < 0:
                self.add_error(field, 'El valor no puede ser negativo.')
        latitude, longitude = cleaned.get('latitude'), cleaned.get('longitude')
        if not {'latitude', 'longitude'} & self.errors.keys():
            if (latitude is None) != (longitude is None):
                self.add_error(None, 'Selecciona una ubicación completa en el mapa.')
            elif latitude is not None and not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                self.add_error(None, 'La ubicación seleccionada está fuera del rango válido.')
        if not str(cleaned.get('district') or '').strip():
            inferred = district_from_address(cleaned.get('address'))
            if inferred:
                cleaned['district'] = inferred
        return cleaned


class ProspectEditForm(ProspectCaptureForm):
    # Selector sí/no con valores de texto ('1'/'0'). Con un BooleanField normal
    # el formulario re-renderizado tras un error marcaba CAPTADO, porque el
    # valor enviado ("0") es una cadena no vacía y por tanto verdadera en la
    # plantilla. Comparando texto el estado queda siempre explícito.
    captado = forms.ChoiceField(
        choices=[('1', '✓ CAPTADO'), ('0', 'NO CAPTADO')],
        required=False,
        label='Captado',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            # El desplegable debe reflejar el valor guardado (no el primero).
            self.initial['captado'] = '1' if self.instance.captado else '0'

    def clean_captado(self):
        return str(self.cleaned_data.get('captado') or '0').strip() == '1'

    class Meta(ProspectCaptureForm.Meta):
        fields = [*ProspectCaptureForm.Meta.fields, 'status', 'captado']
        widgets = {
            'owner_name':     forms.TextInput(attrs={'placeholder': 'Nombre del propietario'}),
            'phone':          forms.TextInput(attrs={'placeholder': 'Ej: 959 234 871', 'inputmode': 'tel'}),
            'price':          forms.NumberInput(attrs={'placeholder': '0.00', 'step': '0.01'}),
            'bedrooms':       forms.NumberInput(attrs={'placeholder': '0', 'min': '0'}),
            'area_m2':        forms.NumberInput(attrs={'placeholder': '0.00', 'step': '0.01'}),
            'address':        forms.TextInput(attrs={'placeholder': 'Mz. D Lote 12, Urb. La Encalada'}),
            'district':       forms.TextInput(attrs={'placeholder': 'Cayma, Yanahuara...'}),
            'notes':          forms.Textarea(attrs={'rows': 3, 'placeholder': 'Observaciones del agente...'}),
        }
