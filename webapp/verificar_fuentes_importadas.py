#!/usr/bin/env python
"""
Script para verificar que las tres fuentes del Excel se hayan importado correctamente.
"""
import os
import sys

# Monkey patch para evitar error de Django
import django.template.context
original_copy = django.template.context.BaseContext.__copy__
def patched_copy(self):
    return self
django.template.context.BaseContext.__copy__ = patched_copy

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import django
    django.setup()
except Exception as e:
    print(f"Error configurando Django: {e}")
    sys.exit(1)

from requerimientos.models import Requerimiento, FuenteChoices
from django.db.models import Count

def main():
    print("=== Verificación de fuentes importadas ===")
    
    # Contar total de requerimientos
    total = Requerimiento.objects.count()
    print(f"Total de requerimientos en la base de datos: {total}")
    
    # Contar por fuente
    conteo_por_fuente = Requerimiento.objects.values('fuente').annotate(
        total=Count('id')
    ).order_by('fuente')
    
    print("\nConteo por fuente:")
    for item in conteo_por_fuente:
        fuente_val = item['fuente']
        fuente_display = dict(FuenteChoices.choices).get(fuente_val, fuente_val)
        print(f"  {fuente_val} ({fuente_display}): {item['total']}")
    
    # Verificar que las tres fuentes esperadas estén presentes
    fuentes_esperadas = [
        FuenteChoices.RED_INMOBILIARIA,
        FuenteChoices.EXITO,
        FuenteChoices.UNIDAS
    ]
    
    fuentes_presentes = set(item['fuente'] for item in conteo_por_fuente)
    
    print("\nVerificación de fuentes esperadas:")
    for fuente in fuentes_esperadas:
        if fuente in fuentes_presentes:
            print(f"  ✓ {fuente} está presente")
        else:
            print(f"  ✗ {fuente} NO está presente")
    
    # Verificar que no haya fuentes inesperadas
    fuentes_inesperadas = fuentes_presentes - set(fuentes_esperadas)
    if fuentes_inesperadas:
        print(f"\nAdvertencia: Se encontraron fuentes inesperadas: {fuentes_inesperadas}")
    else:
        print("\n✓ Todas las fuentes son las esperadas")
    
    # Verificar distribución aproximada (solo para referencia)
    print("\nDistribución aproximada (basada en el Excel):")
    print("  - RED INMOBILIARIA AREQUIPA: ~588 registros (según importación anterior)")
    print("  - ÉXITO INMOBILIARIO: ~? registros")
    print("  - INMOBILIARIAS UNIDAS: ~? registros")
    
    # Mostrar algunos ejemplos de cada fuente
    print("\nEjemplos de cada fuente (primeros 2 registros):")
    for fuente in fuentes_esperadas:
        ejemplos = Requerimiento.objects.filter(fuente=fuente)[:2]
        if ejemplos:
            print(f"\n  {fuente}:")
            for i, req in enumerate(ejemplos):
                print(f"    {i+1}. ID: {req.id}, Agente: {req.agente[:30]}...")

if __name__ == '__main__':
    main()