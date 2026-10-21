"""Versioned, source-aware fields shared by collectors and the master registry."""
import math
import re

VERSION = 'catastro-maestro-v1'
KINDS = ('lote', 'manzana', 'edificio', 'unidad', 'establecimiento', 'registro_documental')
TEXT_FIELDS = {
    'country_code': 'País', 'department': 'Departamento', 'province': 'Provincia',
    'district': 'Distrito', 'ubigeo': 'UBIGEO', 'postal_code': 'Código postal',
    'zone': 'Zona según fuente', 'sector': 'Sector catastral',
    'urbanization': 'Urbanización / habilitación', 'block': 'Manzana catastral',
    'lot': 'Lote catastral', 'address_block': 'Manzana municipal',
    'address_lot': 'Lote municipal', 'building': 'Edificación', 'entrance': 'Entrada',
    'floor': 'Piso', 'unit': 'Unidad', 'address': 'Dirección',
    'street_type': 'Tipo de vía', 'street_name': 'Nombre de vía',
    'municipal_number': 'Número municipal', 'cuc': 'CUC según fuente',
    'cadastral_reference': 'Código de referencia catastral',
    'cadastral_use': 'Uso catastral documentado', 'observed_use': 'Uso observado',
    'use_category': 'Categoría de uso propia', 'business_category': 'Categoría de actividad propia',
    'business_subcategory': 'Subcategoría de actividad propia',
    'ciiu_code': 'Código CIIU', 'ciiu_version': 'Edición CIIU',
    'commercial_name': 'Nombre comercial', 'zoning': 'Zonificación según fuente',
    'condition': 'Estado de conservación', 'registry_entry_number': 'Partida registral',
    'registry_office': 'Oficina registral', 'registry_entry_type': 'Tipo de partida',
    'notary_name': 'Notaría', 'notary_kardex': 'Kárdex', 'deed_date': 'Fecha de escritura',
    'registry_folios': 'Fojas', 'registry_seat': 'Asiento',
    'property_registration_date': 'Fecha de inscripción del predio',
    'construction_declaration': 'Declaración de fábrica',
    'construction_registration_seat': 'Asiento de inscripción de fábrica',
    'construction_registration_date': 'Fecha de inscripción de fábrica',
}
NUMBER_FIELDS = {
    'land_area': ('Área documental del terreno', 'm²'),
    'built_area': ('Área documental construida', 'm²'),
    'geometric_land_area': ('Área calculada del terreno', 'm²'),
    'gis_land_area': ('Área de terreno de capa de origen', 'm²'),
    'gis_built_area': ('Área construida de capa de origen', 'm²'),
    'front': ('Longitud documental del frente', 'm'),
    'back': ('Longitud documental del fondo', 'm'),
    'left': ('Longitud documental izquierda', 'm'),
    'right': ('Longitud documental derecha', 'm'),
    'perimeter': ('Perímetro documental', 'm'),
    'bedrooms': ('Dormitorios', None), 'bathrooms': ('Baños', None),
    'half_bathrooms': ('Medios baños', None), 'parking_spaces': ('Cocheras', None),
    'floors': ('Pisos', None), 'units': ('Unidades', None),
}
BOOLEAN_FIELDS = {'is_corner': 'Es esquina', 'is_through': 'Es pasante',
                  'faces_park': 'Frente a parque'}
# Custom navigation categories, deliberately not advertised as official CIIU codes.
BUSINESS_CATEGORIES = [
    {'code': key, 'label': label, 'scheme': 'propify-actividades-v1'} for key, label in (
        ('supermercado', 'Supermercado'), ('minimarket', 'Minimarket'),
        ('alimentos', 'Bodega / tienda de alimentos'), ('ropa', 'Tienda de ropa'),
        ('restaurante', 'Restaurante'), ('farmacia', 'Farmacia'),
        ('educacion', 'Educación / colegio'), ('salud', 'Salud'),
        ('inmobiliaria', 'Inmobiliaria'), ('otros', 'Otra actividad documentada'))]


def fields():
    return ([{'key': k, 'label': v, 'type': 'text', 'unit': None} for k, v in TEXT_FIELDS.items()]
            + [{'key': k, 'label': v[0], 'type': 'number', 'unit': v[1]} for k, v in NUMBER_FIELDS.items()]
            + [{'key': k, 'label': v, 'type': 'boolean', 'unit': None} for k, v in BOOLEAN_FIELDS.items()])


def validate_field(key, value):
    if key in TEXT_FIELDS:
        if not isinstance(value, str) or len(value) > 2000:
            raise ValueError('El campo de texto no es válido: ' + key)
        if key == 'country_code' and not re.fullmatch(r'[A-Z]{2}', value):
            raise ValueError('El país requiere un código de dos letras.')
        if key == 'ubigeo' and not re.fullmatch(r'[0-9]{6}', value):
            raise ValueError('UBIGEO requiere seis dígitos como texto.')
        if key == 'postal_code' and not re.fullmatch(r'[0-9]{5}', value):
            raise ValueError('El código postal peruano requiere cinco dígitos como texto.')
        # Shape alone never certifies an official assignment. Keep its evidence.
        if key == 'cuc' and not re.fullmatch(r'[A-Za-z0-9]{12}', value):
            raise ValueError('Conserva el CUC completo de doce posiciones; los fragmentos van en los originales.')
    elif key in NUMBER_FIELDS:
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError('El campo numérico no es válido: ' + key)
    elif key in BOOLEAN_FIELDS:
        if type(value) is not bool:
            raise ValueError('La clasificación debe ser sí, no o quedar sin dato: ' + key)
    else:
        raise ValueError('Campo no definido en el contrato: ' + key)
    return value
