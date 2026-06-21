"""Diagnóstico: leer el archivo de Éxito Inmobiliario y ver su formato."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'

import django
django.setup()

from whatsapp_extractor.models import ArchivoExtraccionWhatsApp

OUT = r'd:\proyectos\prometeo\webapp\_debug_exito.txt'

with open(OUT, 'w', encoding='utf-8') as out:
    archivos = ArchivoExtraccionWhatsApp.objects.filter(nombre_archivo_original__icontains='EXITO')
    for a in archivos:
        out.write(f'ID={a.id} | nombre={a.nombre_archivo_original} | ruta={a.ruta_almacenamiento}\n')
        out.write(f'  existe={os.path.exists(a.ruta_almacenamiento)} | procesado={a.procesado}\n')
        if os.path.exists(a.ruta_almacenamiento):
            size = os.path.getsize(a.ruta_almacenamiento)
            out.write(f'  tamanio={size} bytes\n')
            with open(a.ruta_almacenamiento, 'r', encoding='utf-8', errors='replace') as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= 50:
                        break
                    lines.append(f'L{i}: {repr(line[:250])}')
                out.write('  PRIMERAS 50 LINEAS:\n')
                for l in lines:
                    out.write(f'    {l}\n')
        out.write('\n')

print(f'Diagnóstico escrito en {OUT}')
