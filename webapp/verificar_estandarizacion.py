#!/usr/bin/env python
"""
Script de verificación final para confirmar la estandarización del campo tipo_propiedad.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from ingestas.models import PropiedadRaw
from django.db.models import Count

def verificar_estandarizacion():
    print("VERIFICACIÓN FINAL DE ESTANDARIZACIÓN DE TIPO_PROPIEDAD")
    print("=" * 70)
    
    # 1. Verificar valores actuales
    valores = PropiedadRaw.objects.values('tipo_propiedad').annotate(
        total=Count('tipo_propiedad')
    ).order_by('tipo_propiedad')
    
    print("\n1. VALORES ACTUALES EN LA BASE DE DATOS:")
    print("-" * 50)
    print(f"{'Valor':<20} {'Registros':>10} {'¿Válido?':>10}")
    print("-" * 50)
    
    valores_permitidos = ['Terreno', 'Casa', 'Departamento', 'Oficina', 'Otros']
    total_registros = 0
    registros_validos = 0
    registros_invalidos = 0
    
    for v in valores:
        tipo = v['tipo_propiedad']
        total = v['total']
        total_registros += total
        
        if tipo in valores_permitidos:
            valido = "SÍ"
            registros_validos += total
        else:
            valido = "NO"
            registros_invalidos += total
        
        print(f"{tipo or 'NULL':<20} {total:>10} {valido:>10}")
    
    print("-" * 50)
    print(f"{'TOTAL':<20} {total_registros:>10}")
    print(f"\nRegistros válidos: {registros_validos} ({registros_validos/total_registros*100:.1f}%)")
    print(f"Registros inválidos: {registros_invalidos} ({registros_invalidos/total_registros*100:.1f}%)")
    
    # 2. Verificar que no queden valores con "EN VENTA"
    con_en_venta = PropiedadRaw.objects.filter(tipo_propiedad__icontains='EN VENTA').count()
    print(f"\n2. REGISTROS QUE CONTIENEN 'EN VENTA': {con_en_venta}")
    if con_en_venta > 0:
        print("   ¡ADVERTENCIA: Hay valores no estandarizados!")
        ejemplos = PropiedadRaw.objects.filter(tipo_propiedad__icontains='EN VENTA')[:5]
        for ej in ejemplos:
            print(f"   - ID {ej.id}: {ej.tipo_propiedad}")
    
    # 3. Verificar mayúsculas/minúsculas inconsistentes
    print("\n3. VERIFICACIÓN DE FORMATO (mayúsculas/minúsculas):")
    for valor in valores_permitidos:
        count_exacto = PropiedadRaw.objects.filter(tipo_propiedad=valor).count()
        print(f"   {valor}: {count_exacto} registros")
    
    # 4. Probar validación del modelo
    print("\n4. PRUEBA DE VALIDACIÓN DEL MODELO:")
    try:
        # Intentar crear una instancia con valor inválido
        from django.core.exceptions import ValidationError
        propiedad_test = PropiedadRaw(
            fuente_excel="test",
            tipo_propiedad="VALOR_INVALIDO"
        )
        propiedad_test.full_clean()  # Esto debería fallar
        print("   ERROR: El modelo permitió un valor inválido")
    except ValidationError as e:
        if 'tipo_propiedad' in e.message_dict:
            print("   ✓ El modelo valida correctamente valores inválidos")
        else:
            print(f"   ERROR: Validación falló por otra razón: {e}")
    except Exception as e:
        print(f"   ERROR inesperado: {e}")
    
    # 5. Verificar distribución final
    print("\n5. DISTRIBUCIÓN FINAL POR CATEGORÍA:")
    print("-" * 40)
    for valor in valores_permitidos:
        count = PropiedadRaw.objects.filter(tipo_propiedad=valor).count()
        porcentaje = count / total_registros * 100 if total_registros > 0 else 0
        print(f"   {valor:<15} {count:>5} registros ({porcentaje:.1f}%)")
    
    # 6. Resumen
    print("\n" + "=" * 70)
    print("RESUMEN FINAL:")
    if registros_invalidos == 0 and con_en_venta == 0:
        print("✓ ¡ESTANDARIZACIÓN COMPLETADA EXITOSAMENTE!")
        print(f"  Todos los {total_registros} registros tienen valores estandarizados.")
    else:
        print("✗ ¡HAY PROBLEMAS POR RESOLVER!")
        print(f"  Registros inválidos: {registros_invalidos}")
        print(f"  Registros con 'EN VENTA': {con_en_venta}")
    
    return registros_invalidos == 0 and con_en_venta == 0

if __name__ == '__main__':
    exit_code = 0 if verificar_estandarizacion() else 1
    sys.exit(exit_code)