from datetime import date
from django import forms
from .models import LeadControlPolicy, LeadControlMember


class PolicyForm(forms.ModelForm):
    active_statuses = forms.CharField(label='Estados CRM activos (separados por coma)')
    closed_statuses = forms.CharField(label='Estados CRM cerrados (separados por coma)')
    holidays = forms.CharField(label='Feriados (AAAA-MM-DD, separados por coma)', required=False)
    weekdays = forms.TypedMultipleChoiceField(coerce=int, label='Días de atención', choices=list(enumerate(['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'])), widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = LeadControlPolicy
        exclude = ['scan_after_id', 'scan_lease_token', 'scan_lease_until', 'revision', 'updated_at']
        labels = {'name': 'Nombre', 'start_hour': 'Inicio (hora Lima)', 'end_hour': 'Cierre (hora exclusiva)', 'first_minutes': 'Primera respuesta: plazo (min)', 'first_supervisor': 'Primera respuesta: supervisor (min desde inicio)', 'first_manager': 'Primera respuesta: gerencia (min desde inicio)', 'reply_minutes': 'Nueva pregunta: plazo (min)', 'reply_supervisor': 'Nueva pregunta: supervisor (min desde inicio)', 'reply_manager': 'Nueva pregunta: gerencia (min desde inicio)', 'visit_minutes': 'Visita: plazo (min)', 'visit_supervisor': 'Visita: supervisor (min desde inicio)', 'visit_manager': 'Visita: gerencia (min desde inicio)', 'assignment_minutes': 'Asignación: plazo (min)', 'followup_hours': 'Seguimiento sin respuesta (horas corridas)', 'stale_minutes': 'Advertir falta de actualización a los (min)'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['digest_hour'].label = 'Resumen diario (hora Lima, 0 a 23)'
        for field in ('active_statuses', 'closed_statuses', 'holidays'):
            self.initial[field] = ', '.join(self.initial.get(field) or [])

    def clean(self):
        data = super().clean()
        for field in ('active_statuses', 'closed_statuses', 'holidays'):
            values = list(dict.fromkeys(v.strip() for v in (data.get(field) or '').split(',') if v.strip()))
            data[field] = values
        if not data['active_statuses'] or not data['closed_statuses']:
            raise forms.ValidationError('Clasifica los estados activos y cerrados del CRM.')
        if set(v.casefold() for v in data['active_statuses']) & set(v.casefold() for v in data['closed_statuses']):
            raise forms.ValidationError('Un estado no puede ser activo y cerrado a la vez.')
        try:
            for value in data['holidays']:
                date.fromisoformat(value)
        except ValueError:
            self.add_error('holidays', 'Usa fechas AAAA-MM-DD válidas.')
        if not 0 <= data.get('start_hour', -1) < data.get('end_hour', -1) <= 24:
            raise forms.ValidationError('Configura un horario entre 0 y 24, con cierre posterior al inicio.')
        for prefix in ('first', 'reply', 'visit'):
            if not 0 < data.get(f'{prefix}_minutes', 0) <= data.get(f'{prefix}_supervisor', 0) <= data.get(f'{prefix}_manager', 0) <= 10080:
                raise forms.ValidationError('Los plazos deben ser positivos y estar ordenados: atención, supervisor, gerencia (máximo 10080 min).')
        for field in ('assignment_minutes', 'followup_hours', 'stale_minutes'):
            if not 0 < data.get(field, 0) <= 10080:
                self.add_error(field, 'Usa un valor positivo, máximo 10080.')
        if not 0 <= data.get('digest_hour', -1) <= 23:
            self.add_error('digest_hour', 'Usa una hora entre 0 y 23.')
        return data


class MemberForm(forms.ModelForm):
    class Meta:
        model = LeadControlMember
        fields = '__all__'
        labels = {'name': 'Nombre', 'identity_type': 'Sistema de identidad', 'identity_id': 'ID autenticado en ese sistema', 'mobile_identity_id': 'ID Propify para la APK (si difiere de la identidad web)', 'source_user_id': 'ID del agente en CRM', 'role': 'Rol de control', 'email': 'Correo para alertas', 'supervisor': 'Supervisor responsable', 'active': 'Activo', 'away_until': 'Ausente hasta'}
        widgets = {'away_until': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M')}

    def clean(self):
        data = super().clean()
        supervisor = data.get('supervisor')
        if supervisor and (supervisor.pk == self.instance.pk or supervisor.role not in ('supervisor', 'manager') or not supervisor.active):
            self.add_error('supervisor', 'Selecciona otro supervisor o gerente activo.')
        source_id = data.get('source_user_id')
        mobile_id = data.get('mobile_identity_id')
        if mobile_id and LeadControlMember.objects.filter(active=True, mobile_identity_id=mobile_id).exclude(pk=self.instance.pk).exists():
            self.add_error('mobile_identity_id', 'Esta identidad móvil ya está vinculada.')
        if data.get('role') == 'agent' and source_id is None:
            self.add_error('source_user_id', 'El agente necesita su ID del CRM.')
        if source_id is not None and source_id <= 0:
            self.add_error('source_user_id', 'Debe ser positivo.')
        # One routing owner per CRM agent; add additional devices to the same identity.
        if data.get('active') and source_id is not None and LeadControlMember.objects.filter(active=True, source_user_id=source_id).exclude(pk=self.instance.pk).exists():
            self.add_error('source_user_id', 'Ya existe una identidad activa vinculada a este agente.')
        return data
