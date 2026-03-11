#!/usr/bin/env python
"""
Prueba simple para crear un país sin coordenadas.
"""
import os
import sys
import django

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from cuadrantizacion.models import ZonaValor

print("=== Prueba de creación de país sin coordenadas ===")

# Limpiar datos de prueba previos
ZonaValor.objects.filter(nombre_zona='Perú Test').delete()

# Crear país sin coordenadas
try:
    pais = ZonaValor.objects.create(
        nombre_zona='Perú Test',
        descripcion='País de prueba',
        nivel='pais',
        codigo='PT',
        nombre_oficial='República de Prueba',
        coordenadas=None,  # None debería funcionar
        activo=True,
        color_fill='#FF0000',
        color_borde='#CC0000',
        opacidad=0.2
    )
    print(f"OK País creado exitosamente:")
    print(f"  ID: {pais.id}")
    print(f"  Nombre: {pais.nombre_zona}")
    print(f"  Nivel: {pais.nivel}")
    print(f"  Coordenadas: {pais.coordenadas}")
    print(f"  Parent: {pais.parent}")
    
    # Verificar que se guardó correctamente
    pais_db = ZonaValor.objects.get(id=pais.id)
    print(f"OK País recuperado de la base de datos")
    print(f"  Coordenadas en DB: {pais_db.coordenadas}")
    
    # Crear departamento hijo
    departamento = ZonaValor.objects.create(
        nombre_zona='Lima Test',
        nivel='departamento',
        codigo='LT',
        parent=pais,
        coordenadas=None,
        activo=True
    )
    print(f"OK Departamento creado: {departamento.nombre_zona}")
    print(f"  Parent: {departamento.parent.nombre_zona}")
    
    # Crear subzona CON coordenadas
    subzona = ZonaValor.objects.create(
        nombre_zona='Subzona Test',
        nivel='subzona',
        codigo='ST',
        parent=departamento,
        coordenadas=[[-12.12, -77.03], [-12.11, -77.02], [-12.10, -77.03]],
        activo=True
    )
    print(f"OK Subzona creada con coordenadas: {subzona.nombre_zona}")
    print(f"  Coordenadas: {subzona.coordenadas}")
    
    # Limpiar
    pais.delete()
    departamento.delete()
    subzona.delete()
    print("OK Datos de prueba eliminados")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

print("=== Prueba completada ===")