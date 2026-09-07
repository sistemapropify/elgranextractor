import re

from django import forms
from django.forms import inlineformset_factory, BaseInlineFormSet

from .models import RemarketingCampaign, RemarketingStep


VARIABLES = {'nombre', 'propiedad', 'agente'}
VARIABLE_RE = re.compile(r'{{\s*([a-zA-Z_]+)\s*}}')


def render_message(body, context):
    names = VARIABLE_RE.findall(body)
    if set(names) - VARIABLES:
        raise ValueError('Variables permitidas: nombre, propiedad, agente.')
    if any(not str(context.get(name) or '').strip() for name in names):
        raise ValueError('Faltan datos para completar las variables del mensaje.')
    rendered = VARIABLE_RE.sub(lambda match: str(context[match.group(1)]), body)
    if '{{' in rendered or '}}' in rendered:
        raise ValueError('Variable incompleta o no reconocida.')
    return rendered


class CampaignForm(forms.ModelForm):
    allowed_statuses = forms.CharField(label='Estados CRM permitidos', help_text='Nombres exactos separados por coma. Solo se incluirán estos estados.')
    allowed_channels = forms.CharField(label='Canales permitidos', help_text='Nombres exactos separados por coma, por ejemplo WhatsApp.')
    agent_ids = forms.CharField(label='IDs de agentes (opcional)', required=False, help_text='Separados por coma; vacío incluye todos.')
    weekdays = forms.TypedMultipleChoiceField(label='Días permitidos', coerce=int, choices=list(enumerate(['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'])), widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = RemarketingCampaign
        fields = ['name', 'allowed_statuses', 'allowed_channels', 'agent_ids', 'contact_sender', 'daily_limit', 'hourly_limit', 'contact_limit', 'min_gap_minutes', 'window_margin_minutes', 'start_hour', 'end_hour', 'weekdays']
        labels = {'name': 'Nombre', 'contact_sender': 'Primer contacto válido', 'daily_limit': 'Máximo de mensajes diarios', 'hourly_limit': 'Máximo en una hora', 'contact_limit': 'Máximo por contacto en 24 horas', 'min_gap_minutes': 'Separación mínima (minutos)', 'window_margin_minutes': 'Margen antes de las 24 h (minutos)', 'start_hour': 'Hora de inicio (Lima)', 'end_hour': 'Hora de cierre (exclusiva)'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('allowed_statuses', 'allowed_channels', 'agent_ids'):
            self.initial[name] = ', '.join(map(str, self.initial.get(name) or []))
        if not self.instance.pk:
            self.initial['weekdays'] = [0, 1, 2, 3, 4, 5]

    def clean_allowed_statuses(self):
        return self._list('allowed_statuses')

    def clean_allowed_channels(self):
        return self._list('allowed_channels')

    def _list(self, name):
        result = list(dict.fromkeys(v.strip() for v in self.cleaned_data[name].split(',') if v.strip()))
        if not result:
            raise forms.ValidationError('Indica al menos un valor.')
        return result

    def clean_agent_ids(self):
        try:
            result = [int(v.strip()) for v in self.cleaned_data['agent_ids'].split(',') if v.strip()]
            if any(v <= 0 for v in result):
                raise ValueError
            return list(dict.fromkeys(result))
        except ValueError:
            raise forms.ValidationError('Usa IDs numéricos positivos separados por coma.')

    def clean(self):
        data = super().clean()
        for name in ('daily_limit', 'hourly_limit', 'contact_limit', 'min_gap_minutes', 'window_margin_minutes'):
            if data.get(name, 0) <= 0:
                self.add_error(name, 'Debe ser mayor que cero.')
        if not 0 <= data.get('start_hour', -1) < data.get('end_hour', -1) <= 24:
            raise forms.ValidationError('El horario debe estar entre 0 y 24; cierre posterior al inicio.')
        if data.get('window_margin_minutes', 0) >= 1440:
            self.add_error('window_margin_minutes', 'Debe ser menor a 24 horas.')
        return data


class StepForm(forms.ModelForm):
    class Meta:
        model = RemarketingStep
        fields = ['title', 'delay_minutes', 'body']
        labels = {'title': 'Nombre de plantilla', 'delay_minutes': 'Minutos desde el contacto inicial', 'body': 'Mensaje'}
        widgets = {'body': forms.Textarea(attrs={'rows': 3, 'maxlength': 4000})}

    def clean_delay_minutes(self):
        value = self.cleaned_data['delay_minutes']
        if not 0 < value < 1440:
            raise forms.ValidationError('Usa entre 1 y 1439 minutos.')
        return value

    def clean_body(self):
        body = self.cleaned_data['body'].strip()
        if len(body) > 4000:
            raise forms.ValidationError('Máximo 4000 caracteres.')
        try:
            render_message(body, dict.fromkeys(VARIABLES, 'Ejemplo'))
        except ValueError as exc:
            raise forms.ValidationError(str(exc))
        return body


class StepFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        delays = sorted(f.cleaned_data['delay_minutes'] for f in self.forms if f.cleaned_data and not f.cleaned_data.get('DELETE'))
        if not delays:
            raise forms.ValidationError('Agrega al menos una plantilla.')
        gap = self.instance.min_gap_minutes or 1
        if any(b - a < gap for a, b in zip(delays, delays[1:])):
            raise forms.ValidationError('Los pasos deben respetar la separación mínima configurada.')


CampaignSteps = inlineformset_factory(RemarketingCampaign, RemarketingStep, form=StepForm, formset=StepFormSet, extra=0, can_delete=True)
