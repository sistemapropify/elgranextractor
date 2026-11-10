from pathlib import Path

from django import forms
from django.db.models import Q

from .models import DocumentType, ExternalAgent, ExternalAgentAttachment


INPUT_CLASS = 'ea-input'
SELECT_CLASS = 'ea-input ea-select'
MAX_ATTACHMENT_BYTES = 15 * 1024 * 1024


def clean_attachment_file(uploaded):
    if not uploaded:
        return ''
    if uploaded.size > MAX_ATTACHMENT_BYTES:
        raise forms.ValidationError('El archivo supera el límite de 15 MB.')
    extension = Path(uploaded.name).suffix.lower()
    if extension not in {'.pdf', '.png', '.jpg', '.jpeg', '.webp'}:
        raise forms.ValidationError('Formato no permitido. Usa PDF, JPG, PNG o WEBP.')
    return Path(uploaded.name).name[:255]


class ExternalAgentForm(forms.ModelForm):
    attachment_type = forms.ModelChoiceField(
        queryset=DocumentType.objects.none(),
        required=False,
        label='Tipo de documento adjunto',
        empty_label='Seleccionar tipo de adjunto',
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )
    attachment_file = forms.FileField(
        required=False,
        label='Documento adjunto',
        help_text='Opcional. PDF, JPG, PNG o WEBP. Máximo 15 MB.',
        widget=forms.FileInput(attrs={
            'class': 'ea-file-input',
            'accept': '.pdf,.png,.jpg,.jpeg,.webp',
        }),
    )

    class Meta:
        model = ExternalAgent
        fields = [
            'first_name',
            'paternal_last_name',
            'maternal_last_name',
            'personal_document_type',
            'document_number',
            'address',
            'email',
            'mobile',
            'level',
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': INPUT_CLASS,
                'placeholder': 'Nombres del agente',
                'autocomplete': 'given-name',
            }),
            'paternal_last_name': forms.TextInput(attrs={
                'class': INPUT_CLASS,
                'placeholder': 'Apellido paterno',
                'autocomplete': 'family-name',
            }),
            'maternal_last_name': forms.TextInput(attrs={
                'class': INPUT_CLASS,
                'placeholder': 'Apellido materno',
                'autocomplete': 'additional-name',
            }),
            'personal_document_type': forms.Select(attrs={'class': SELECT_CLASS}),
            'document_number': forms.TextInput(attrs={
                'class': INPUT_CLASS,
                'placeholder': 'Número de documento',
                'autocomplete': 'off',
            }),
            'address': forms.TextInput(attrs={
                'class': INPUT_CLASS,
                'placeholder': 'Dirección completa',
                'autocomplete': 'street-address',
            }),
            'email': forms.EmailInput(attrs={
                'class': INPUT_CLASS,
                'placeholder': 'nombre@correo.com',
                'autocomplete': 'email',
            }),
            'mobile': forms.TextInput(attrs={
                'class': INPUT_CLASS,
                'placeholder': '+51 999 999 999',
                'inputmode': 'tel',
                'autocomplete': 'tel',
            }),
            'level': forms.Select(attrs={'class': SELECT_CLASS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_type_id = getattr(self.instance, 'personal_document_type_id', None)
        self.fields['personal_document_type'].queryset = (
            DocumentType.objects
            .filter(scope=DocumentType.Scope.PERSONAL)
            .filter(Q(is_active=True) | Q(pk=current_type_id))
            .order_by('sort_order', 'name', 'pk')
        )
        self.fields['personal_document_type'].empty_label = 'Seleccionar tipo de documento'
        self.fields['attachment_type'].queryset = (
            DocumentType.objects
            .filter(scope=DocumentType.Scope.ATTACHMENT, is_active=True)
            .order_by('sort_order', 'name', 'pk')
        )
        for field_name, field in self.fields.items():
            if field.required and field_name != 'attachment_file':
                field.widget.attrs['aria-required'] = 'true'

    def clean(self):
        cleaned = super().clean()
        document_type = cleaned.get('personal_document_type')
        document_number = (cleaned.get('document_number') or '').strip()
        cleaned['document_number'] = document_number
        if document_type and document_number:
            duplicates = ExternalAgent.objects.filter(
                personal_document_type=document_type,
                document_number=document_number,
            )
            if self.instance.pk:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists():
                self.add_error(
                    'document_number',
                    'Ya existe un agente externo con este tipo y número de documento.',
                )
        attachment_type = cleaned.get('attachment_type')
        attachment_file = cleaned.get('attachment_file')
        if bool(attachment_type) != bool(attachment_file):
            self.add_error(
                'attachment_file' if attachment_file else 'attachment_type',
                'Selecciona el tipo y adjunta el archivo para guardar el documento.',
            )
        if attachment_file:
            try:
                clean_attachment_file(attachment_file)
            except forms.ValidationError as error:
                self.add_error('attachment_file', error)
        return cleaned


class AttachmentForm(forms.ModelForm):
    class Meta:
        model = ExternalAgentAttachment
        fields = ['document_type', 'file']
        widgets = {
            'document_type': forms.Select(attrs={'class': SELECT_CLASS}),
            'file': forms.FileInput(attrs={
                'class': 'ea-file-input',
                'accept': '.pdf,.png,.jpg,.jpeg,.webp',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['document_type'].queryset = (
            DocumentType.objects
            .filter(scope=DocumentType.Scope.ATTACHMENT, is_active=True)
            .order_by('sort_order', 'name', 'pk')
        )
        self.fields['document_type'].empty_label = 'Seleccionar tipo de adjunto'
        self.fields['file'].help_text = 'PDF, JPG, PNG o WEBP. Máximo 15 MB.'

    def clean_file(self):
        uploaded = self.cleaned_data.get('file')
        if not uploaded:
            return uploaded
        self.original_name = clean_attachment_file(uploaded)
        return uploaded


class DocumentTypeForm(forms.ModelForm):
    class Meta:
        model = DocumentType
        fields = ['name', 'sort_order']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': INPUT_CLASS,
                'placeholder': 'Ej. DNI, Pasaporte, Contrato firmado',
                'maxlength': '80',
            }),
            'sort_order': forms.NumberInput(attrs={
                'class': INPUT_CLASS,
                'min': '0',
                'max': '999',
            }),
        }

    def clean_name(self):
        return ' '.join((self.cleaned_data.get('name') or '').split())
