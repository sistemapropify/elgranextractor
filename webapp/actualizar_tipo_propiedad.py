#!/usr/bin/env python
"""
Script para actualizar y estandarizar los valores del campo tipo_propiedad en PropiedadRaw.
"""
import os
import sys
import django
from django.db import transaction

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from ingestas.models import PropiedadRaw

def definir_mapeo():
    """Define las reglas de mapeo para estandarizar tipo_propiedad"""
    
    mapeo = {
        # Terreno - todas las variantes
        'terreno': 'Terreno',
        'TERRENO': 'Terreno',
        'TERRENO EN VENTA': 'Terreno',
        'TERRENO URBANO EN VENTA': 'Terreno',
        'TERRENO AGRÍCOLA EN VENTA': 'Terreno',
        'TERRENO COMERCIAL EN VENTA': 'Terreno',
        'TERRENO INDUSTRIAL EN VENTA': 'Terreno',
        
        # Casa - todas las variantes
        'casa': 'Casa',
        'CASA EN VENTA': 'Casa',
        'CASA URBANA EN VENTA': 'Casa',
        'CASA DE CAMPO EN VENTA': 'Casa',
        
        # Departamento - todas las variantes
        'DEPARTAMENTO EN VENTA': 'Departamento',
        'DEPARTAMENTO FLAT EN VENTA': 'Departamento',
        'DEPARTAMENTO DUPLEX EN VENTA': 'Departamento',
        'DEPARTAMENTO PENTHOUSE EN VENTA': 'Departamento',
        'DEPARTAMENTO TRIPLEX EN VENTA': 'Departamento',
        'DEPARTAMENTO EN CONDOMINIO EN VENTA': 'Departamento',
        'MINIDEPARTAMENTO EN VENTA': 'Departamento',
        
        # Oficina
        'OFICINA EN VENTA': 'Oficina',
        
        # Otros - mapear a "Otros" (según requerimiento del usuario)
        'LOCAL COMERCIAL EN VENTA': 'Otros',
        'LOCAL EN VENTA': 'Otros',
        'LOCAL INDUSTRIAL EN VENTA': 'Otros',
        'EDIFICIOS EN VENTA': 'Otros',
        'HOTEL EN VENTA': 'Otros',
        'AIRES EN VENTA': 'Otros',
        'OPORTUNIDADES EN VENTA': 'Otros',
        'OTROS EN VENTA': 'Otros',
    }
    
    return mapeo

def obtener_valor_mapeado(valor_original, mapeo):
    """Obtiene el valor mapeado para un valor original"""
    if valor_original is None:
        return None
    
    # Buscar coincidencia exacta
    if valor_original in mapeo:
        return mapeo[valor_original]
    
    # Buscar coincidencia case-insensitive
    for key, value in mapeo.items():
        if key.lower() == valor_original.lower():
            return value
    
    # Si no hay mapeo, mantener el valor original
    return valor_original

def actualizar_registros(dry_run=True):
    """Actualiza los registros en la base de datos"""
    print("ACTUALIZACIÓN DE TIPO_PROPIEDAD")
    print("=" * 60)
    
    if dry_run:
        print("MODO SIMULACIÓN (dry-run): No se realizarán cambios reales en la BD")
    else:
        print("MODO REAL: Se actualizarán los registros en la BD")
    
    mapeo = definir_mapeo()
    
    # Obtener todos los registros
    registros = PropiedadRaw.objects.all()
    total = registros.count()
    
    print(f"\nTotal de registros a procesar: {total}")
    
    cambios = 0
    sin_cambios = 0
    errores = 0
    
    # Procesar cada registro
    for i, registro in enumerate(registros, 1):
        original = registro.tipo_propiedad
        mapeado = obtener_valor_mapeado(original, mapeo)
        
        if original != mapeado:
            cambios += 1
            if dry_run:
                print(f"[{i}/{total}] CAMBIO: '{original}' -> '{mapeado}' (ID: {registro.id})")
            else:
                try:
                    registro.tipo_propiedad = mapeado
                    registro.save(update_fields=['tipo_propiedad'])
                    print(f"[{i}/{total}] ACTUALIZADO: '{original}' -> '{mapeado}' (ID: {registro.id})")
                except Exception as e:
                    errores += 1
                    print(f"[{i}/{total}] ERROR al actualizar ID {registro.id}: {e}")
        else:
            sin_cambios += 1
            if i <= 10:  # Mostrar solo primeros 10 sin cambios
                print(f"[{i}/{total}] SIN CAMBIO: '{original}' (ID: {registro.id})")
    
    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN DE LA ACTUALIZACIÓN:")
    print(f"  Total de registros procesados: {total}")
    print(f"  Registros con cambios: {cambios}")
    print(f"  Registros sin cambios: {sin_cambios}")
    print(f"  Errores: {errores}")
    
    if dry_run:
        print("\nPara aplicar los cambios, ejecute el script con --apply")
    else:
        print("\n¡Actualización completada!")
    
    return cambios, errores

def verificar_resultados():
    """Verifica los resultados después de la actualización"""
    print("\n" + "=" * 60)
    print("VERIFICACIÓN DE RESULTADOS")
    print("=" * 60)
    
    from django.db.models import Count
    
    # Obtener valores distintos después de la actualización
    valores = PropiedadRaw.objects.values('tipo_propiedad').annotate(
        total=Count('tipo_propiedad')
    ).order_by('tipo_propiedad')
    
    print(f"{'Valor Actual':<30} {'Registros':>10}")
    print("-" * 40)
    
    for v in valores:
        tipo = v['tipo_propiedad']
        total = v['total']
        print(f"{tipo or 'NULL':<30} {total:>10}")
    
    # Contar por categoría estandarizada
    categorias_esperadas = ['Terreno', 'Casa', 'Departamento', 'Oficina', 'Otros']
    for cat in categorias_esperadas:
        count = PropiedadRaw.objects.filter(tipo_propiedad=cat).count()
        print(f"{cat}: {count} registros")
    
    # Verificar que no queden valores con "EN VENTA"
    con_en_venta = PropiedadRaw.objects.filter(tipo_propiedad__icontains='EN VENTA').count()
    print(f"\nRegistros que aún contienen 'EN VENTA': {con_en_venta}")
    
    if con_en_venta > 0:
        print("  ¡ADVERTENCIA: Algunos registros no fueron mapeados correctamente!")
        ejemplos = PropiedadRaw.objects.filter(tipo_propiedad__icontains='EN VENTA')[:5]
        for ej in ejemplos:
            print(f"    - ID {ej.id}: {ej.tipo_propiedad}")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Estandarizar valores de tipo_propiedad')
    parser.add_argument('--apply', action='store_true', help='Aplicar cambios reales (sin dry-run)')
    parser.add_argument('--verify', action='store_true', help='Verificar resultados después de actualizar')
    
    args = parser.parse_args()
    
    dry_run = not args.apply
    
    try:
        cambios, errores = actualizar_registros(dry_run=dry_run)
        
        if args.apply or args.verify:
            verificar_resultados()
            
    except Exception as e:
        print(f"Error durante la ejecución: {e}")
        sys.exit(1)