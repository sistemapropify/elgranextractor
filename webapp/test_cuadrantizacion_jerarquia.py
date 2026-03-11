#!/usr/bin/env python
"""
Script de prueba para la funcionalidad de cuadrantización jerárquica.
"""

import os
import sys
import django

# Configurar Django - ajustar path para el proyecto
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)  # Subir un nivel desde webapp/

# Agregar el directorio raíz del proyecto al path
sys.path.insert(0, project_root)
sys.path.insert(0, current_dir)

# Configurar settings de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from cuadrantizacion.models import ZonaValor
from cuadrantizacion.services import (
    crear_estructura_jerarquica,
    obtener_zonas_por_nivel,
    calcular_estadisticas_jerarquicas,
    obtener_jerarquia_completa,
    encontrar_zona_por_jerarquia
)

def test_creacion_jerarquia():
    """Prueba la creación de una estructura jerárquica completa."""
    print("=== PRUEBA DE CREACIÓN DE JERARQUÍA ===")
    
    try:
        # 1. País (nivel más alto)
        peru = crear_estructura_jerarquica(
            nombre='Perú',
            nivel='pais',
            coordenadas=[[-18.0, -81.0], [-18.0, -68.0], [-0.0, -68.0], [-0.0, -81.0], [-18.0, -81.0]],
            codigo='PE'
        )
        print(f'[OK] País creado: {peru.nombre_zona} (nivel: {peru.nivel})')
        
        # 2. Departamento (dentro de Perú)
        lima = crear_estructura_jerarquica(
            nombre='Lima',
            nivel='departamento',
            coordenadas=[[-12.5, -77.5], [-12.5, -76.0], [-11.0, -76.0], [-11.0, -77.5], [-12.5, -77.5]],
            parent=peru,
            codigo='PE-LIM'
        )
        print(f'[OK] Departamento creado: {lima.nombre_zona} (padre: {lima.parent.nombre_zona})')
        
        # 3. Provincia (dentro de Lima)
        lima_provincia = crear_estructura_jerarquica(
            nombre='Lima',
            nivel='provincia',
            coordenadas=[[-12.2, -77.2], [-12.2, -76.8], [-11.8, -76.8], [-11.8, -77.2], [-12.2, -77.2]],
            parent=lima,
            codigo='PE-LIM-LIMA'
        )
        print(f'✓ Provincia creada: {lima_provincia.nombre_zona} (padre: {lima_provincia.parent.nombre_zona})')
        
        # 4. Distrito (dentro de Lima provincia)
        miraflores = crear_estructura_jerarquica(
            nombre='Miraflores',
            nivel='distrito',
            coordenadas=[[-12.12, -77.03], [-12.12, -77.01], [-12.10, -77.01], [-12.10, -77.03], [-12.12, -77.03]],
            parent=lima_provincia,
            codigo='PE-LIM-LIMA-MIRA'
        )
        print(f'✓ Distrito creado: {miraflores.nombre_zona} (padre: {miraflores.parent.nombre_zona})')
        
        # 5. Zona (dentro de Miraflores)
        zona_central = crear_estructura_jerarquica(
            nombre='Zona Central Miraflores',
            nivel='zona',
            coordenadas=[[-12.118, -77.028], [-12.118, -77.025], [-12.115, -77.025], [-12.115, -77.028], [-12.118, -77.028]],
            parent=miraflores,
            codigo='PE-LIM-LIMA-MIRA-ZC'
        )
        print(f'✓ Zona creada: {zona_central.nombre_zona} (padre: {zona_central.parent.nombre_zona})')
        
        # 6. Subzona (dentro de Zona Central)
        subzona_parque = crear_estructura_jerarquica(
            nombre='Subzona Parque Kennedy',
            nivel='subzona',
            coordenadas=[[-12.117, -77.027], [-12.117, -77.026], [-12.116, -77.026], [-12.116, -77.027], [-12.117, -77.027]],
            parent=zona_central,
            codigo='PE-LIM-LIMA-MIRA-ZC-PK'
        )
        print(f'✓ Subzona creada: {subzona_parque.nombre_zona} (padre: {subzona_parque.parent.nombre_zona})')
        
        return peru, lima, lima_provincia, miraflores, zona_central, subzona_parque
        
    except Exception as e:
        print(f'✗ Error en creación de jerarquía: {e}')
        import traceback
        traceback.print_exc()
        return None

def test_metodos_jerarquicos(zonas):
    """Prueba los métodos jerárquicos del modelo."""
    if not zonas:
        return
    
    peru, lima, lima_provincia, miraflores, zona_central, subzona_parque = zonas
    
    print("\n=== PRUEBA DE MÉTODOS JERÁRQUICOS ===")
    
    try:
        # Ruta jerárquica
        print(f"1. Ruta jerárquica de subzona: {subzona_parque.get_hierarchy_display()}")
        
        # Verificar si es hoja
        print(f"2. ¿Subzona es hoja? {subzona_parque.is_leaf()}")
        print(f"3. ¿Zona Central es hoja? {zona_central.is_leaf()}")
        
        # Obtener descendientes
        descendientes_miraflores = miraflores.get_descendants()
        print(f"4. Descendientes de Miraflores: {len(descendientes_miraflores)} zonas")
        
        # Obtener hojas
        hojas_peru = peru.get_leaf_zones()
        print(f"5. Zonas hoja bajo Perú: {len(hojas_peru)} zonas")
        
        # Obtener jerarquía completa
        jerarquia = obtener_jerarquia_completa(miraflores)
        print(f"6. Jerarquía de Miraflores: {len(jerarquia['ancestros'])} ancestros, {len(jerarquia['descendientes'])} descendientes directos")
        
    except Exception as e:
        print(f'✗ Error en métodos jerárquicos: {e}')
        import traceback
        traceback.print_exc()

def test_servicios_jerarquicos(zonas):
    """Prueba los servicios jerárquicos."""
    if not zonas:
        return
    
    peru, lima, lima_provincia, miraflores, zona_central, subzona_parque = zonas
    
    print("\n=== PRUEBA DE SERVICIOS JERÁRQUICOS ===")
    
    try:
        # Obtener zonas por nivel
        zonas_distrito = obtener_zonas_por_nivel('distrito')
        print(f"1. Zonas de nivel distrito: {zonas_distrito.count()}")
        
        # Calcular estadísticas jerárquicas
        stats = calcular_estadisticas_jerarquicas(miraflores, incluir_descendientes=True)
        print(f"2. Estadísticas de Miraflores (con descendientes):")
        print(f"   - Cantidad propiedades: {stats['cantidad_propiedades']}")
        print(f"   - Nivel: {stats['nivel']}")
        print(f"   - Subzonas incluidas: {stats['subzonas_incluidas']}")
        
        # Encontrar zona por jerarquía
        punto_lat, punto_lng = -12.1165, -77.0265  # Dentro del Parque Kennedy
        zona_encontrada = encontrar_zona_por_jerarquia(punto_lat, punto_lng)
        if zona_encontrada:
            print(f"3. Zona encontrada para punto ({punto_lat}, {punto_lng}): {zona_encontrada.nombre_zona} (nivel: {zona_encontrada.nivel})")
        else:
            print(f"3. No se encontró zona para el punto")
            
        # Buscar específicamente a nivel distrito
        zona_distrito = encontrar_zona_por_jerarquia(punto_lat, punto_lng, nivel_deseado='distrito')
        if zona_distrito:
            print(f"4. Distrito encontrado: {zona_distrito.nombre_zona}")
        
    except Exception as e:
        print(f'✗ Error en servicios jerárquicos: {e}')
        import traceback
        traceback.print_exc()

def test_vistas_api():
    """Prueba que las vistas API funcionen con la nueva jerarquía."""
    print("\n=== PRUEBA DE VISTAS API ===")
    
    try:
        from django.test import Client
        from rest_framework.test import APIClient
        
        client = APIClient()
        
        # 1. Probar endpoint de niveles
        print("1. Probando endpoint /api/cuadrantizacion/zonas/niveles/")
        response = client.get('/api/cuadrantizacion/zonas/niveles/')
        if response.status_code == 200:
            print(f"   ✓ Status: {response.status_code}")
            data = response.data
            print(f"   ✓ Niveles disponibles: {list(data.keys())}")
        else:
            print(f"   ✗ Status: {response.status_code}")
        
        # 2. Probar filtro por nivel
        print("2. Probando filtro por nivel 'distrito'")
        response = client.get('/api/cuadrantizacion/zonas/?nivel=distrito')
        if response.status_code == 200:
            print(f"   ✓ Status: {response.status_code}")
            print(f"   ✓ Zonas encontradas: {len(response.data)}")
        else:
            print(f"   ✗ Status: {response.status_code}")
            
    except Exception as e:
        print(f'✗ Error en pruebas de API: {e}')
        import traceback
        traceback.print_exc()

def limpiar_datos_prueba():
    """Elimina los datos de prueba creados."""
    print("\n=== LIMPIANDO DATOS DE PRUEBA ===")
    
    try:
        # Eliminar zonas de prueba por código
        zonas_eliminadas = ZonaValor.objects.filter(codigo__startswith='PE').delete()
        print(f"✓ Zonas eliminadas: {zonas_eliminadas[0]}")
    except Exception as e:
        print(f"✗ Error al limpiar datos: {e}")

def main():
    """Función principal de prueba."""
    print("INICIANDO PRUEBAS DE CUADRANTIZACIÓN JERÁRQUICA")
    print("=" * 50)
    
    # Crear estructura jerárquica
    zonas = test_creacion_jerarquia()
    
    if zonas:
        # Probar métodos jerárquicos
        test_metodos_jerarquicos(zonas)
        
        # Probar servicios jerárquicos
        test_servicios_jerarquicos(zonas)
        
        # Probar vistas API (solo si el servidor está corriendo)
        # test_vistas_api()
        
        # Limpiar datos de prueba
        limpiar_datos_prueba()
    
    print("\n" + "=" * 50)
    print("PRUEBAS COMPLETADAS")

if __name__ == '__main__':
    main()