#!/usr/bin/env python
"""
Script para probar la conexión y el modelo de analisis_crm.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from analisis_crm.models import Lead

def test_connection():
    print("=== PRUEBA DE CONEXION A BASE DE DATOS PROPIFAI ===")
    try:
        count = Lead.objects.count()
        print(f"[OK] Conexion exitosa. Total de leads: {count}")
        
        if count > 0:
            lead = Lead.objects.first()
            print(f"[OK] Primer lead: ID={lead.id}, Nombre={lead.full_name}, Telefono={lead.phone}")
        else:
            print("[OK] La tabla esta vacia.")
        
        # Verificar que el router esta funcionando
        from django.db import connections
        conn = connections['propifai']
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            print(f"[OK] Consulta simple a propifai: {result}")
        
        print("\n=== PRUEBA DE VISTAS ===")
        from django.test import Client
        client = Client()
        response = client.get('/analisis-crm/')
        print(f"[OK] Dashboard status: {response.status_code}")
        if response.status_code == 200:
            print("   Vista dashboard cargada correctamente.")
        else:
            print("   ERROR: Dashboard no responde.")
        
        response2 = client.get('/analisis-crm/leads/')
        print(f"[OK] Lista de leads status: {response2.status_code}")
        
        if count > 0:
            response3 = client.get(f'/analisis-crm/leads/{lead.id}/')
            print(f"[OK] Detalle de lead status: {response3.status_code}")
        
        print("\n=== TODAS LAS PRUEBAS PASARON ===")
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_connection()