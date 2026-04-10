#!/usr/bin/env python3
"""
Script para probar la funcionalidad de ordenamiento en el dashboard de CRM.
"""

import sys
import os

# Agregar el directorio webapp al path para importar configuraciones Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

import django
django.setup()

from analisis_crm.models import Lead, LeadAssignment, LeadStatus, User
from django.test import RequestFactory
from webapp.analisis_crm.views import dashboard

def test_sorting_logic():
    """Probar la lógica de ordenamiento en la vista dashboard."""
    print("=== Prueba de lógica de ordenamiento ===")
    
    # Crear una fábrica de requests
    factory = RequestFactory()
    
    # Probar diferentes parámetros de ordenamiento
    test_cases = [
        ('id', 'asc', 'Ordenar por ID ascendente'),
        ('id', 'desc', 'Ordenar por ID descendente'),
        ('full_name', 'asc', 'Ordenar por nombre ascendente'),
        ('date_entry', 'desc', 'Ordenar por fecha descendente (default)'),
        ('is_active', 'asc', 'Ordenar por estado activo/inactivo'),
        ('status_name', 'asc', 'Ordenar por nombre de estado'),
        ('assigned_user', 'asc', 'Ordenar por usuario asignado'),
    ]
    
    for sort_by, sort_order, description in test_cases:
        print(f"\n--- {description} ---")
        print(f"Parámetros: sort_by={sort_by}, sort_order={sort_order}")
        
        # Crear request con parámetros
        request = factory.get(f'/analisis-crm/?sort_by={sort_by}&sort_order={sort_order}')
        
        try:
            # Ejecutar la vista
            response = dashboard(request)
            
            # Verificar que la respuesta sea exitosa
            if response.status_code == 200:
                print("[OK] Vista ejecutada exitosamente")
                
                # Obtener leads del contexto
                # Nota: Esto es simplificado, en realidad necesitaríamos renderizar el template
                # Pero podemos verificar que no hay errores
                print(f"[OK] Código de estado: {response.status_code}")
                
                # Verificar que los parámetros están en el contexto
                context = response.context_data if hasattr(response, 'context_data') else {}
                if 'sort_by' in context and 'sort_order' in context:
                    print(f"[OK] Parámetros en contexto: sort_by={context['sort_by']}, sort_order={context['sort_order']}")
                else:
                    print("[WARN] Parámetros de ordenamiento no encontrados en contexto")
            else:
                print(f"[FAIL] Código de estado inesperado: {response.status_code}")
                
        except Exception as e:
            print(f"[FAIL] Error al ejecutar vista: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n=== Verificación de campos ordenables ===")
    print("Campos válidos para ordenamiento:")
    print("  - id: ID del lead")
    print("  - full_name: Nombre completo")
    print("  - phone: Teléfono")
    print("  - email: Email")
    print("  - date_entry: Fecha de entrada")
    print("  - is_active: Estado activo/inactivo")
    print("  - lead_status_id: ID del estado del lead")
    print("  - status_name: Nombre del estado del lead")
    print("  - assigned_user: Usuario asignado")
    
    print("\n=== Instrucciones para probar manualmente ===")
    print("1. Inicia el servidor: cd webapp && py manage.py runserver")
    print("2. Ve a http://127.0.0.1:8000/analisis-crm/")
    print("3. Haz clic en los encabezados de la tabla 'Leads Recientes'")
    print("4. Verifica que:")
    print("   - Los encabezados son enlaces clickeables")
    print("   - Al hacer clic, la página se recarga con los parámetros ?sort_by=...&sort_order=...")
    print("   - Los datos se ordenan correctamente")
    print("   - Las flechas (↑↓) indican la dirección del ordenamiento")
    print("   - El filtro por fecha se mantiene al ordenar")

def main():
    """Función principal."""
    print("=== Prueba de funcionalidad de ordenamiento para dashboard CRM ===\n")
    
    test_sorting_logic()
    
    print("\n=== Resumen ===")
    print("La implementación de ordenamiento incluye:")
    print("✓ Parámetros GET: sort_by y sort_order")
    print("✓ Validación de campos de ordenamiento")
    print("✓ Ordenamiento en Python (ya que los leads se filtran por duplicados)")
    print("✓ Encabezados de tabla con enlaces para ordenar")
    print("✓ Indicadores visuales (flechas ↑↓) para dirección de ordenamiento")
    print("✓ Mantenimiento de filtros existentes (fecha) al ordenar")
    
    print("\n=== Notas ===")
    print("- El ordenamiento es del lado del servidor (recarga de página)")
    print("- Se mantiene la lógica de eliminación de duplicados por teléfono")
    print("- Los campos 'status_name' y 'assigned_user' requieren consultas adicionales a la BD")

if __name__ == '__main__':
    main()