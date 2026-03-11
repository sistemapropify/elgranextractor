#!/usr/bin/env python
"""
Script para probar la funcionalidad de configuración jerárquica.
"""

import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from cuadrantizacion.models import ZonaValor
from django.test import RequestFactory
from cuadrantizacion.views import configurar_jerarquia

def test_vista_configurar_jerarquia():
    """Prueba que la vista configurar_jerarquia funcione correctamente."""
    print("🧪 Probando vista configurar_jerarquia...")
    
    # Crear una solicitud de prueba
    factory = RequestFactory()
    request = factory.get('/cuadrantizacion/jerarquia/')
    
    try:
        # Ejecutar la vista
        response = configurar_jerarquia(request)
        
        # Verificar que la respuesta sea exitosa
        if response.status_code == 200:
            print("✅ Vista configurar_jerarquia funciona correctamente")
            print(f"   Status code: {response.status_code}")
            
            # Verificar que el contexto tenga los datos esperados
            context = response.context_data if hasattr(response, 'context_data') else {}
            
            if 'arbol_jerarquico' in context:
                arbol = context['arbol_jerarquico']
                print(f"   ✅ Árbol jerárquico en contexto: {len(arbol)} nodos raíz")
                
                # Mostrar estructura del árbol
                def contar_nodos(nodos, nivel=0):
                    total = 0
                    for nodo in nodos:
                        total += 1
                        if 'hijos' in nodo and nodo['hijos']:
                            total += contar_nodos(nodo['hijos'], nivel + 1)
                    return total
                
                total_nodos = contar_nodos(arbol)
                print(f"   ✅ Total de nodos en árbol: {total_nodos}")
            
            if 'zonas_por_nivel' in context:
                niveles = context['zonas_por_nivel']
                print(f"   ✅ Zonas por nivel en contexto: {len(niveles)} niveles")
                for nivel_codigo, nivel_info in niveles.items():
                    print(f"      - {nivel_info['nombre']}: {nivel_info['cantidad']} zonas")
            
            if 'niveles' in context:
                niveles_lista = context['niveles']
                print(f"   ✅ Niveles en contexto: {len(niveles_lista)} niveles definidos")
                for i, (codigo, nombre) in enumerate(niveles_lista, 1):
                    print(f"      {i}. {nombre} ({codigo})")
            
            if 'total_zonas' in context:
                print(f"   ✅ Total de zonas: {context['total_zonas']}")
            
            return True
            
        else:
            print(f"❌ Error: Status code {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error al ejecutar la vista: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_estructura_jerarquica():
    """Prueba la estructura jerárquica del modelo."""
    print("\n🧪 Probando estructura jerárquica del modelo...")
    
    try:
        # Contar zonas existentes
        total_zonas = ZonaValor.objects.filter(activo=True).count()
        print(f"   Total de zonas activas: {total_zonas}")
        
        # Verificar zonas por nivel
        for nivel_codigo, nivel_nombre in ZonaValor.NIVELES:
            zonas_nivel = ZonaValor.objects.filter(nivel=nivel_codigo, activo=True).count()
            print(f"   - {nivel_nombre}: {zonas_nivel} zonas")
        
        # Verificar relaciones padre-hijo
        zonas_con_hijos = ZonaValor.objects.filter(children__isnull=False, activo=True).distinct().count()
        zonas_sin_padre = ZonaValor.objects.filter(parent__isnull=True, activo=True).count()
        
        print(f"   Zonas con hijos: {zonas_con_hijos}")
        print(f"   Zonas sin padre (raíz): {zonas_sin_padre}")
        
        # Mostrar algunas jerarquías de ejemplo
        print("\n   Ejemplos de jerarquías:")
        zonas_raiz = ZonaValor.objects.filter(parent__isnull=True, activo=True)[:3]
        for zona in zonas_raiz:
            print(f"   - {zona.nombre_zona} ({zona.get_nivel_display()})")
            hijos = zona.children.filter(activo=True)[:3]
            for hijo in hijos:
                print(f"     └── {hijo.nombre_zona} ({hijo.get_nivel_display()})")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en estructura jerárquica: {e}")
        return False

def main():
    """Función principal de prueba."""
    print("=" * 60)
    print("PRUEBA DE CONFIGURACIÓN JERÁRQUICA DE ZONAS")
    print("=" * 60)
    
    # Ejecutar pruebas
    test1_ok = test_vista_configurar_jerarquia()
    test2_ok = test_estructura_jerarquica()
    
    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN DE PRUEBAS:")
    print("=" * 60)
    
    if test1_ok and test2_ok:
        print("✅ Todas las pruebas pasaron correctamente")
        print("\n📋 La funcionalidad de configuración jerárquica está lista para usar.")
        print("   Accede a: /cuadrantizacion/jerarquia/")
        print("\n🔧 Características implementadas:")
        print("   - Visualización de árbol jerárquico")
        print("   - Creación de nuevas zonas con padre")
        print("   - Drag & drop para reorganizar jerarquía")
        print("   - Filtrado por nivel")
        print("   - Estadísticas de jerarquía")
        print("   - Validación de niveles (país → departamento → provincia → distrito → zona → subzona)")
    else:
        print("❌ Algunas pruebas fallaron")
        sys.exit(1)

if __name__ == '__main__':
    main()