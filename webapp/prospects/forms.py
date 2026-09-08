from django import forms
from .models import PropertyProspect


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
        return cleaned


class ProspectEditForm(ProspectCaptureForm):
    class Meta(ProspectCaptureForm.Meta):
        fields = [*ProspectCaptureForm.Meta.fields, 'status']
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
