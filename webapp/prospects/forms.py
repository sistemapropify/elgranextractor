from django import forms
from .models import PropertyProspect


class ProspectCaptureForm(forms.ModelForm):
    """Guarda una captura completa, igual que la aplicación Propitools."""

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
        return cleaned


class ProspectEditForm(forms.ModelForm):
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
            'status', 'notes',
        ]
        widgets = {
            'owner_name':     forms.TextInput(attrs={'placeholder': 'Nombre del propietario'}),
            'phone':          forms.TextInput(attrs={'placeholder': 'Ej: 959 234 871', 'inputmode': 'tel'}),
            'price':          forms.NumberInput(attrs={'placeholder': '0.00', 'step': '0.01'}),
            'bedrooms':       forms.NumberInput(attrs={'placeholder': '0', 'min': '0', 'max': '20'}),
            'area_m2':        forms.NumberInput(attrs={'placeholder': '0.00', 'step': '0.01'}),
            'address':        forms.TextInput(attrs={'placeholder': 'Mz. D Lote 12, Urb. La Encalada'}),
            'district':       forms.TextInput(attrs={'placeholder': 'Cayma, Yanahuara...'}),
            'notes':          forms.Textarea(attrs={'rows': 3, 'placeholder': 'Observaciones del agente...'}),
        }

    def clean(self):
        cleaned = super().clean()
        origin = cleaned.get('origin')
        url = (cleaned.get('marketplace_url') or '').strip()
        if origin == 'marketplace' and not url:
            self.add_error(
                'marketplace_url',
                'Es obligatorio guardar el enlace del anuncio para poder guardar.',
            )
        return cleaned
