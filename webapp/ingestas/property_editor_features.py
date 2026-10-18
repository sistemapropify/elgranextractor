"""Review structured listing features without rewriting the original evidence."""
from copy import deepcopy
import json
import re

from django import forms
from django.utils import timezone
from scrapi.building_features import PARKING_TYPES, SUPPORTED, plain, read_features


FEATURE_FIELDS = ('tiene_cochera', 'tipos_cochera', 'tiene_ascensor', 'piso_departamento')
TRISTATE = (('', 'Sin información'), ('si', 'Sí'), ('no', 'No'))


def tri_value(value):
    return 'si' if value is True else 'no' if value is False else ''


class FeatureReviewForm(forms.ModelForm):
    tiene_cochera = forms.ChoiceField(label='¿Tiene cochera?', choices=TRISTATE, required=False)
    tipos_cochera = forms.MultipleChoiceField(
        label='Tipo de cochera', choices=tuple(PARKING_TYPES.items()), required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text='Marca los tipos presentes. Sin cochera: selecciona «No» arriba. '
                  'Tipo sin información: deja las cuatro opciones sin marcar.')
    tiene_ascensor = forms.ChoiceField(label='¿Tiene ascensor?', choices=TRISTATE, required=False)
    piso_departamento = forms.CharField(
        label='Piso del departamento', max_length=60, required=False,
        help_text='Por ejemplo: 3, 3 y 4, planta baja o sótano. Vacío: sin información. '
                  'Es el piso de la unidad, no el número de pisos del edificio.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        obj = self.instance
        self.original_features = deepcopy(read_features(obj.tipo_inmueble, obj.datos_crudos,
            obj.descripcion, obj.estacionamientos, obj.amenities))
        parking = self.original_features['parking']
        initial = {'tiene_cochera': tri_value(parking['has']),
                   'tipos_cochera': parking.get('types') or [],
                   'tiene_ascensor': tri_value(self.original_features['elevator']['has']),
                   'piso_departamento': obj.piso_departamento or ''}
        self.initial.update(initial)
        self.fields['estacionamientos'].label = 'Cantidad de cocheras / estacionamientos'
        self.parking_presence_submitted = self.is_bound and 'tiene_cochera' in self.data
        if self.is_bound:
            # Existing API clients may still submit only the original model fields.
            data = self.data.copy()
            parking_submitted = 'tiene_cochera' in data or 'tipos_cochera' in data
            for field, value in initial.items():
                if field not in data and not (field == 'tipos_cochera' and parking_submitted):
                    if hasattr(data, 'setlist') and isinstance(value, list):
                        data.setlist(field, value)
                    else:
                        data[field] = value
            self.data = data

    def clean(self):
        data = super().clean()
        has, kinds, count = data.get('tiene_cochera'), data.get('tipos_cochera') or [], data.get('estacionamientos')
        if kinds and has == 'no':
            self.add_error('tipos_cochera', 'Sin cochera no puede tener un tipo de cochera.')
        elif kinds:
            data['tiene_cochera'] = 'si'
        if data.get('tiene_cochera') == 'no' and count not in (None, 0):
            self.add_error('estacionamientos', 'Sin cochera: la cantidad debe ser cero o quedar vacía.')
        if not data.get('tiene_cochera') and count is not None and count > 0:
            if self.parking_presence_submitted:
                self.add_error('estacionamientos', 'Para dejar la cochera sin información, deja también la cantidad vacía.')
            else:
                data['tiene_cochera'] = 'si'
        if data.get('tiene_cochera') == 'si' and count == 0:
            self.add_error('estacionamientos', 'Con cochera: indica una cantidad positiva o déjala sin información.')
        if plain(data.get('tipo_inmueble') or '') not in SUPPORTED:
            for field in ('tiene_cochera', 'tipos_cochera', 'tiene_ascensor'):
                if data.get(field):
                    self.add_error(field, 'No aplica a este tipo de inmueble; deja el campo sin información.')
        floor = (data.get('piso_departamento') or '').strip()
        if floor:
            if plain(data.get('tipo_inmueble')) not in ('departamento', 'apartamento', 'duplex', 'triplex', 'flat'):
                self.add_error('piso_departamento', 'El piso de la unidad aplica a departamentos.')
            elif re.fullmatch(r'\d{1,3}(?:\s*(?:y|,)\s*\d{1,3}){0,2}', floor):
                levels = [int(n) for n in re.findall(r'\d+', floor)]
                if any(n > 200 for n in levels):
                    self.add_error('piso_departamento', 'El piso debe estar entre 0 y 200.')
                else:
                    data['piso_departamento'] = ' y '.join(map(str, sorted(set(levels))))
            elif plain(floor) not in ('planta baja', 'semisotano', 'sotano', 'sotano 1', 'sotano 2'):
                self.add_error('piso_departamento', 'Indica un piso, varios niveles o planta baja/sótano.')
        return data

    def apply_review(self):
        """Called only after validation, under the existing editor transaction."""
        changed = set(self.changed_data)
        raw = deepcopy(self.instance.datos_crudos) if isinstance(self.instance.datos_crudos, dict) else {}
        features = deepcopy(self.original_features)
        protected = set()
        if changed & {'tiene_cochera', 'tipos_cochera', 'estacionamientos'}:
            has = {'si': True, 'no': False}.get(self.cleaned_data['tiene_cochera'])
            count = self.cleaned_data.get('estacionamientos')
            kinds = self.cleaned_data['tipos_cochera'] or None
            if has is False:
                count, kinds = 0, []
            elif count is not None and count > 0:
                has = True
            features['parking'].update(has=has, count=count, types=kinds, details=[],
                status='explicit' if has is False or kinds else 'partial' if has is True else 'unknown',
                manual=True, reviewed_at=timezone.now().isoformat())
            self.instance.estacionamientos = count
            protected.update(('tiene_cochera', 'tipos_cochera', 'estacionamientos'))
        if 'tiene_ascensor' in changed:
            has = {'si': True, 'no': False}.get(self.cleaned_data['tiene_ascensor'])
            features['elevator'].update(has=has, status='unknown' if has is None else 'explicit',
                manual=True, reviewed_at=timezone.now().isoformat())
            protected.add('tiene_ascensor')
        if protected:
            raw.update(_building_features=features, tiene_cochera=features['parking']['has'],
                       tipos_cochera=features['parking']['types'], tiene_ascensor=features['elevator']['has'])
        if 'piso_departamento' in changed:
            floor = self.cleaned_data['piso_departamento'] or None
            raw.update(piso_departamento=floor, _floor_evidence={
                'version': 1, 'status': 'explicit' if floor is not None else 'unknown',
                'manual': True, 'reviewed_at': timezone.now().isoformat()})
            protected.add('piso_departamento')
        if protected:
            self.instance.datos_crudos = raw
        return protected


def review_details(obj, editable_fields):
    """Every concrete field has a visible destination in the editor."""
    readonly = []
    for field in obj._meta.concrete_fields:
        if field.name in editable_fields or field.name == 'datos_crudos':
            continue
        value = field.value_from_object(obj)
        if field.choices:
            value = dict(field.choices).get(value, value)
        if hasattr(value, 'isoformat'):
            value = value.isoformat()
        readonly.append({'name': field.name, 'label': str(field.verbose_name), 'value': value})
    for label, value in (
        ('Moneda del precio mostrado', obj.moneda_precio),
        ('Precio por m² de terreno', obj.precio_m2_terreno),
        ('Precio por m² construido', obj.precio_m2_construida),
        ('Precio por m² del área principal', obj.precio_m2),
    ):
        readonly.append({'name': 'computed', 'label': label, 'value': value})
    raw = obj.datos_crudos
    originals = [{'label': str(key), 'value': json.dumps(value, ensure_ascii=False, indent=2)
                  if isinstance(value, (dict, list)) else value} for key, value in raw.items()] if isinstance(raw, dict) else [
                      {'label': 'Datos originales del scraper', 'value': raw}]
    return {'readonly_fields': readonly, 'original_fields': originals}
