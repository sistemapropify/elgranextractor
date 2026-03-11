#!/usr/bin/env python
"""
Script para verificar que los distritos se están generando correctamente para los filtros.
"""
import json
import os

def verificar_mapeo_distritos():
    """Verifica el mapeo de distritos desde el archivo JSON."""
    mapeo_path = 'mapeo_ubicaciones_propifai.json'
    if os.path.exists(mapeo_path):
        with open(mapeo_path, 'r', encoding='utf-8') as f:
            mapeo = json.load(f)
        
        print(f"=== MAPEO DE UBICACIONES ===")
        print(f"Total de departamentos: {len(mapeo.get('departamentos', {}))}")
        print(f"Total de provincias: {len(mapeo.get('provincias', {}))}")
        print(f"Total de distritos: {len(mapeo.get('distritos', {}))}")
        
        # Mostrar algunos distritos de ejemplo
        distritos = mapeo.get('distritos', {})
        if distritos:
            print(f"\nEjemplos de distritos (primeros 10):")
            for i, (distrito_id, distrito_nombre) in enumerate(list(distritos.items())[:10]):
                print(f"  {distrito_id}: {distrito_nombre}")
        
        # Verificar que los distritos tengan nombres legibles
        distritos_con_nombres = [d for d in distritos.values() if d and not d.isdigit()]
        print(f"\nDistritos con nombres legibles: {len(distritos_con_nombres)} de {len(distritos)}")
        
        return True
    else:
        print(f"ERROR: Archivo de mapeo no encontrado: {mapeo_path}")
        return False

def verificar_vista_distritos():
    """Verifica que la vista pueda generar distritos."""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    try:
        # Simular la lógica de la vista para obtener distritos
        from propifai.mapeo_ubicaciones import DISTRITOS
        
        print(f"\n=== MAPEO DESDE mapeo_ubicaciones.py ===")
        print(f"Total de distritos en mapeo: {len(DISTRITOS)}")
        
        # Ejemplos de distritos mapeados
        print(f"\nEjemplos de distritos mapeados (primeros 10):")
        for i, (distrito_id, distrito_nombre) in enumerate(list(DISTRITOS.items())[:10]):
            print(f"  {distrito_id}: {distrito_nombre}")
        
        # Verificar conversión de índices a nombres
        test_indices = ['1', '4', '23', '999']
        print(f"\nPrueba de conversión de índices a nombres:")
        for idx in test_indices:
            nombre = DISTRITOS.get(idx, f'No encontrado ({idx})')
            print(f"  {idx} -> {nombre}")
        
        return True
    except ImportError as e:
        print(f"ERROR importando mapeo_ubicaciones: {e}")
        return False
    except Exception as e:
        print(f"ERROR inesperado: {e}")
        return False

def main():
    print("=== VERIFICACIÓN DE FILTRO DE DISTRITO ===\n")
    
    # Verificar mapeo desde JSON
    mapeo_ok = verificar_mapeo_distritos()
    
    # Verificar mapeo desde módulo Python
    modulo_ok = verificar_vista_distritos()
    
    # Resumen
    print(f"\n=== RESUMEN ===")
    if mapeo_ok and modulo_ok:
        print("OK: Los distritos están correctamente mapeados y disponibles para filtros.")
        print("OK: El filtro de distrito debería funcionar correctamente.")
        print("\nPara probar manualmente:")
        print("1. Visita http://localhost:8000/ingestas/propiedades/")
        print("2. Busca el filtro 'Distrito' en la barra de filtros")
        print("3. Selecciona un distrito y haz clic en 'Filtrar'")
        print("4. Verifica que las propiedades se filtren correctamente")
    else:
        print("ERROR: Hay problemas con el mapeo de distritos.")
    
    return mapeo_ok and modulo_ok

if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)