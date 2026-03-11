#!/usr/bin/env python
"""
Prueba de renderizado de la plantilla lista.html con datos reales.
"""
import os
import sys
import django
from django.template import Template, Context
from django.template.loader import get_template

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from requerimientos.models import Requerimiento

def test_template():
    # Obtener algunos requerimientos
    requerimientos = Requerimiento.objects.all()[:5]
    
    # Contexto simulado
    context = {
        'requerimientos': requerimientos,
        'fuentes': [('GRUPO_A', 'Grupo A'), ('GRUPO_B', 'Grupo B')],
        'condiciones': [('COMPRA', 'Compra'), ('ALQUILER', 'Alquiler')],
        'tipos_propiedad': [('CASA', 'Casa'), ('DEPARTAMENTO', 'Departamento')],
        'request': type('Request', (), {'GET': {}})(),
        'total': requerimientos.count(),
        'is_paginated': False,
        'page_obj': type('Page', (), {'has_previous': False, 'has_next': False, 'paginator': type('Paginator', (), {'page_range': range(1, 2)})()}),
    }
    
    # Cargar plantilla
    template = get_template('requerimientos/lista.html')
    
    try:
        html = template.render(context)
        print('SUCCESS: Plantilla renderizada correctamente')
        print(f'Longitud HTML: {len(html)} caracteres')
        # Verificar que contiene algunos elementos esperados
        if 'Lista de Requerimientos' in html:
            print('✓ Título encontrado')
        if 'table' in html:
            print('✓ Tabla encontrada')
        if 'Grupo WhatsApp' in html:
            print('✓ Encabezado Grupo WhatsApp encontrado')
        print('---')
        # Mostrar primeros 500 caracteres del HTML generado
        print(html[:500])
        return True
    except Exception as e:
        print('ERROR al renderizar plantilla:', e)
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_template()
    sys.exit(0 if success else 1)