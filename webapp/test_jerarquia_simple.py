#!/usr/bin/env python
"""
Script de prueba simple para la funcionalidad de cuadrantización jerárquica.
"""

import os
import sys
import django

# Configurar Django
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)
sys.path.insert(0, current_dir)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from cuadrantizacion.models import ZonaValor
from cuadrantizacion.services import crear_estructura_jerarquica

def main():
    print("INICIANDO PRUEBAS DE JERARQUIA")
    print("=" * 50)
    
    try:
        # 1. Crear estructura jerárquica
        print("1. Creando estructura jerárquica...")
        
        # País
        peru = crear_estructura_jerarquica(
            nombre='Peru',
            nivel='pais',
            coordenadas=[[-18.0, -81.0], [-18.0, -68.0], [-0.0, -68.0], [-0.0, -81.0], [-18.0, -81.0]],
            codigo='PE'
        )
        print(f"   - Pais creado: {peru.nombre_zona} (nivel: {peru.nivel})")
        
        # Departamento
        lima = crear_estructura_jerarquica(
            nombre='Lima',
            nivel='departamento',
            coordenadas=[[-12.5, -77.5], [-12.5, -76.0], [-11.0, -76.0], [-11.0, -77.5], [-12.5, -77.5]],
            parent=peru,
            codigo='PE-LIM'
        )
        print(f"   - Departamento creado: {lima.nombre_zona}")
        
        # Provincia
        lima_provincia = crear_estructura_jerarquica(
            nombre='Lima Provincia',
            nivel='provincia',
            coordenadas=[[-12.2, -77.2], [-12.2, -76.8], [-11.8, -76.8], [-11.8, -77.2], [-12.2, -77.2]],
            parent=lima,
            codigo='PE-LIM-LIMA'
        )
        print(f"   - Provincia creada: {lima_provincia.nombre_zona}")
        
        # Distrito
        miraflores = crear_estructura_jerarquica(
            nombre='Miraflores',
            nivel='distrito',
            coordenadas=[[-12.12, -77.03], [-12.12, -77.01], [-12.10, -77.01], [-12.10, -77.03], [-12.12, -77.03]],
            parent=lima_provincia,
            codigo='PE-LIM-LIMA-MIRA'
        )
        print(f"   - Distrito creado: {miraflores.nombre_zona}")
        
        # 2. Probar métodos de jerarquía
        print("\n2. Probando metodos jerarquicos...")
        
        # Ruta jerárquica (manejar posible Unicode)
        try:
            ruta = miraflores.get_hierarchy_display()
            print(f"   - Ruta jerarquica de Miraflores: {ruta}")
        except UnicodeEncodeError:
            # Si hay problemas con Unicode, usar representación simple
            ruta_simple = f"{miraflores.nombre_zona} ({miraflores.get_nivel_display()})"
            if miraflores.parent:
                ruta_simple = f"{miraflores.parent.nombre_zona} -> {ruta_simple}"
            print(f"   - Ruta jerarquica de Miraflores: {ruta_simple}")
        
        # Verificar si es hoja
        print(f"   - ¿Miraflores es hoja? {miraflores.is_leaf()}")
        
        # Obtener descendientes
        descendientes = miraflores.get_descendants()
        print(f"   - Descendientes de Miraflores: {len(descendientes)}")
        
        # 3. Verificar estructura en base de datos
        print("\n3. Verificando estructura en base de datos...")
        
        total_zonas = ZonaValor.objects.count()
        print(f"   - Total de zonas en BD: {total_zonas}")
        
        zonas_por_nivel = {}
        for nivel_codigo, nivel_nombre in ZonaValor.NIVELES:
            count = ZonaValor.objects.filter(nivel=nivel_codigo).count()
            zonas_por_nivel[nivel_nombre] = count
        
        print("   - Zonas por nivel:")
        for nivel_nombre, count in zonas_por_nivel.items():
            print(f"     * {nivel_nombre}: {count}")
        
        # 4. Limpiar datos de prueba
        print("\n4. Limpiando datos de prueba...")
        eliminadas = ZonaValor.objects.filter(codigo__startswith='PE').delete()
        print(f"   - Zonas eliminadas: {eliminadas[0]}")
        
        print("\n" + "=" * 50)
        print("PRUEBAS COMPLETADAS EXITOSAMENTE")
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())