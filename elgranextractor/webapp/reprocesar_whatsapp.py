"""
Script temporal para reprocesar el archivo WhatsApp.
Ejecutar: py manage.py runscript reprocesar_whatsapp
O mejor: py manage.py shell < reprocesar_whatsapp.py
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
sys.path.insert(0, os.path.dirname(__file__))

import django
django.setup()

from whatsapp_extractor.tasks import procesar_archivo_extraccion

print("Iniciando reprocesamiento del archivo ID=21...")
result = procesar_archivo_extraccion(21)
print(f"Resultado: {result}")
