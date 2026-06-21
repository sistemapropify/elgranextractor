from django import forms
from .models import PropertyProspect


class ProspectEditForm(forms.ModelForm):
    class Meta:
        model = PropertyProspect
        fields = [
            'owner_name', 'phone',
            'operation_type', 'property_type',
            'price', 'currency',
            'bedrooms', 'area_m2',
            'address', 'district',
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
