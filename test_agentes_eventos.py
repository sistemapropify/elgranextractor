#!/usr/bin/env python
"""
Script para probar que los nombres de agentes se muestran correctamente en el dashboard de eventos.
"""
import os
import sys
import django
import requests

# Configurar Django
sys.path.append('webapp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from eventos.models import Event
from propifai.models import User

def test_agentes():
    """Verificar que hay eventos con agentes asignados y usuarios correspondientes."""
    print("=== Prueba de nombres de agentes ===")
    
    # Contar eventos con assigned_agent_id
    eventos_con_agente = Event.objects.filter(assigned_agent_id__isnull=False)
    print(f"Total eventos con agente asignado: {eventos_con_agente.count()}")
    
    # Obtener algunos eventos de ejemplo
    eventos_muestra = eventos_con_agente[:5]
    
    for evento in eventos_muestra:
        print(f"\nEvento ID: {evento.id}")
        print(f"  Código: {evento.code}")
        print(f"  Agente ID: {evento.assigned_agent_id}")
        
        # Intentar obtener el usuario
        try:
            usuario = User.objects.get(id=evento.assigned_agent_id)
            nombre_completo = f"{usuario.first_name} {usuario.last_name}".strip()
            print(f"  Usuario encontrado: {nombre_completo}")
            print(f"  Email: {usuario.email}")
        except User.DoesNotExist:
            print(f"  Usuario con ID {evento.assigned_agent_id} no encontrado")
        except Exception as e:
            print(f"  Error: {e}")
    
    # Verificar que la vista funciona
    print("\n=== Probando vista dashboard ===")
    try:
        # Hacer una solicitud HTTP local
        import urllib.request
        import urllib.error
        
        url = "http://localhost:8000/eventos/"
        print(f"Intentando conectar a {url}")
        
        # Usar requests si está disponible
        try:
            response = requests.get(url, timeout=5)
            print(f"Status code: {response.status_code}")
            if response.status_code == 200:
                print("✓ Vista dashboard carga correctamente")
                # Verificar si aparece algún nombre de agente en el HTML
                html = response.text
                if "Agente #" in html:
                    print("✓ Se encontró texto 'Agente #' en el HTML")
                else:
                    print("✗ No se encontró texto 'Agente #' (puede que todos los agentes tengan nombres)")
            else:
                print(f"✗ Error HTTP: {response.status_code}")
        except requests.exceptions.ConnectionError:
            print("✗ No se pudo conectar al servidor (puede que no esté corriendo)")
    except Exception as e:
        print(f"Error en prueba HTTP: {e}")

if __name__ == "__main__":
    test_agentes()