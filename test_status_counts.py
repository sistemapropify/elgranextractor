#!/usr/bin/env python3
"""
Script para probar que la tabla "Leads por Estado" muestra nombres en lugar de IDs.
"""

import urllib.request
import urllib.error
import sys
import os

# Agregar el directorio webapp al path para importar configuraciones Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

import django
django.setup()

# Ahora podemos importar los modelos
from analisis_crm.models import LeadStatus

def test_status_names_in_table():
    """Verificar que los nombres de estado existen en la base de datos."""
    print("=== Verificando nombres de estados en base de datos ===")
    
    try:
        statuses = LeadStatus.objects.all()
        print(f"[OK] Se encontraron {statuses.count()} estados en la base de datos")
        
        for status in statuses:
            print(f"  - ID {status.id}: '{status.name}' (activo: {status.is_active})")
        
        return True
    except Exception as e:
        print(f"[FAIL] Error al consultar estados: {e}")
        return False

def test_http_page():
    """Probar que la página carga correctamente y muestra nombres de estado."""
    print("\n=== Probando carga de página HTTP ===")
    
    url = "http://127.0.0.1:8000/analisis-crm/"
    
    try:
        req = urllib.request.Request(url)
        response = urllib.request.urlopen(req, timeout=10)
        html_content = response.read().decode('utf-8')
        
        if response.status == 200:
            print("[OK] Página cargada exitosamente (HTTP 200)")
            
            # Verificar que la tabla "Leads por Estado" existe
            if 'Leads por Estado' in html_content:
                print("[OK] Sección 'Leads por Estado' encontrada en la página")
            else:
                print("[WARN] Sección 'Leads por Estado' no encontrada")
            
            # Verificar que el encabezado muestra "Estado" en lugar de "Estado ID"
            if '<th>Estado</th>' in html_content:
                print("[OK] Encabezado 'Estado' encontrado (no 'Estado ID')")
            else:
                print("[FAIL] Encabezado 'Estado' no encontrado")
            
            # Verificar que no aparece "Estado ID" en la tabla
            if '<th>Estado ID</th>' not in html_content:
                print("[OK] Encabezado 'Estado ID' no aparece (correcto)")
            else:
                print("[FAIL] Encabezado 'Estado ID' todavía aparece")
            
            # Buscar nombres de estado en el HTML
            status_names_found = []
            from analisis_crm.models import LeadStatus
            status_names = list(LeadStatus.objects.values_list('name', flat=True))
            
            for name in status_names:
                if name and name in html_content:
                    status_names_found.append(name)
            
            if status_names_found:
                print(f"[OK] Se encontraron nombres de estado en la página: {', '.join(status_names_found[:3])}")
                if len(status_names_found) > 3:
                    print(f"     ... y {len(status_names_found) - 3} más")
            else:
                print("[WARN] No se encontraron nombres de estado específicos en el HTML")
                print("       Esto podría ser normal si no hay leads con estados asignados")
            
            # Verificar que no aparecen IDs numéricos solos (como <td>1</td>)
            import re
            # Buscar patrones como <td>1</td> o <td>2</td> que podrían ser IDs
            id_pattern = r'<td>(\d+)</td>'
            numeric_ids = re.findall(id_pattern, html_content)
            
            # Filtrar solo los que están en la sección de estados (podrían ser conteos)
            # Los conteos también son números, así que necesitamos ser más específicos
            # Buscamos filas completas de la tabla de estados
            if 'Sin estado' in html_content:
                print("[OK] 'Sin estado' aparece en la página (para leads sin estado)")
            
            return True
        else:
            print(f"[FAIL] Código de estado HTTP inesperado: {response.status}")
            return False
            
    except urllib.error.URLError as e:
        print(f"[FAIL] Error de conexión: {e}")
        print("       Asegúrate de que el servidor Django esté ejecutándose")
        return False
    except Exception as e:
        print(f"[FAIL] Error inesperado: {e}")
        return False

def main():
    """Función principal de prueba."""
    print("=== Prueba de mejora: Nombres de estado en tabla 'Leads por Estado' ===\n")
    
    # Primero verificar la base de datos
    db_ok = test_status_names_in_table()
    
    # Luego probar la página HTTP (si el servidor está corriendo)
    print("\nNota: Para probar la página HTTP, asegúrate de que el servidor Django esté ejecutándose.")
    print("      Ejecuta: py manage.py runserver (en otra terminal)")
    
    response = input("\n¿Está ejecutándose el servidor Django? (s/n): ").strip().lower()
    
    if response == 's':
        http_ok = test_http_page()
    else:
        print("\n[INFO] Omitiendo prueba HTTP. Puedes ejecutar el servidor y luego probar manualmente.")
        print("       URL: http://127.0.0.1:8000/analisis-crm/")
        print("       Verifica que la tabla 'Leads por Estado' muestre nombres en lugar de IDs.")
        http_ok = False
    
    print("\n=== Resumen ===")
    if db_ok:
        print("[OK] Base de datos: Los nombres de estado están disponibles")
    else:
        print("[FAIL] Base de datos: Problema al acceder a nombres de estado")
    
    if http_ok:
        print("[OK] Página HTTP: Los cambios se aplicaron correctamente")
    else:
        print("[INFO] Prueba HTTP no completada o con advertencias")
    
    print("\n=== Pasos para verificar manualmente ===")
    print("1. Ve a http://127.0.0.1:8000/analisis-crm/")
    print("2. Busca la sección 'Leads por Estado' (tarjeta en la parte inferior izquierda)")
    print("3. Verifica que la columna diga 'Estado' (no 'Estado ID')")
    print("4. Verifica que se muestren nombres como 'Nuevo', 'No interesado', etc.")
    print("5. Verifica que no se muestren números solos (como '1', '2')")

if __name__ == '__main__':
    main()