#!/usr/bin/env python
"""
Script para probar los datos generados por la vista dashboard de analisis_crm.
"""
import os
import sys
import django
from django.test import RequestFactory

# Configurar entorno Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from analisis_crm.views import dashboard

# Crear un request mock
factory = RequestFactory()
request = factory.get('/analisis-crm/')

# Ejecutar la vista
response = dashboard(request)

# La vista retorna un render, pero podemos inspeccionar el contexto
# En lugar de eso, vamos a ejecutar la lógica directamente copiando el código
# Pero es más fácil inspeccionar los prints que hace la vista.
# Como la vista imprime en stdout, capturaremos la salida.
# Vamos a redirigir stdout temporalmente.
import io
import contextlib

out = io.StringIO()
with contextlib.redirect_stdout(out):
    response = dashboard(request)

output = out.getvalue()
print("=== SALIDA DE DEBUG ===")
print(output)
print("=== FIN SALIDA ===")

# También podemos extraer datos del contexto si modificamos la vista para retornarlos,
# pero por ahora solo vemos los logs.