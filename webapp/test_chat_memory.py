#!/usr/bin/env python
"""
Test completo del sistema de memoria del chat.
Simula una conversación para verificar que el chat recuerda información.
"""
import os
import sys
import json
import django
import requests

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from intelligence.models import User, Fact

def test_chat_memory():
    print("=== Test del sistema de memoria del chat ===\n")
    
    # Buscar usuario demo
    users = User.objects.all()
    test_user = None
    for u in users:
        if u.metadata and isinstance(u.metadata, dict):
            if u.metadata.get('demo') == True or u.metadata.get('name') == 'Usuario Demo':
                test_user = u
                break
    
    if not test_user:
        print("No se encontró usuario demo, creando uno...")
        # Crear usuario temporal para prueba
        from django.utils import timezone
        test_user = User.objects.create(
            phone='51999999999',
            role=None,
            metadata={'test': True, 'name': 'Usuario Test', 'demo': True},
            last_seen=timezone.now()
        )
    
    print(f"Usuario de prueba: {test_user.id}")
    print(f"Nombre: {test_user.metadata.get('name', 'Sin nombre')}")
    
    # Verificar hechos existentes
    facts = Fact.objects.filter(user=test_user, is_active=True)
    print(f"\nHechos existentes en la base de datos: {facts.count()}")
    for fact in facts:
        print(f"  - {fact.subject} {fact.relation} {fact.object} (confianza: {fact.confidence})")
    
    # Simular llamadas a la API del chat
    print("\n=== Simulando conversación con el chat ===\n")
    
    # URL de la API (asumiendo que el servidor está corriendo en localhost:8000)
    base_url = "http://localhost:8000"
    chat_api_url = f"{base_url}/api/v1/intelligence/chat-web/api/"
    
    # Headers para la solicitud
    headers = {
        'Content-Type': 'application/json',
    }
    
    # Test 1: Preguntar sobre área de trabajo
    print("Test 1: Preguntar '¿sabes en qué área trabajo de la inmobiliaria?'")
    
    payload = {
        'user_id': str(test_user.id),
        'message': '¿sabes en qué área trabajo de la inmobiliaria?',
        'use_memory': True,
        'use_rag': False,
        'collections': []
    }
    
    try:
        response = requests.post(chat_api_url, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print(f"  Respuesta: {data.get('response', '')[:200]}...")
                print(f"  Contexto usado: memoria={data.get('context_summary', {}).get('memory_used', 0)}")
                
                # Verificar si la respuesta menciona "sistemas" o "área"
                response_text = data.get('response', '').lower()
                if 'sistema' in response_text or 'área' in response_text or 'trabajo' in response_text:
                    print("  ✓ La respuesta parece hacer referencia al área de trabajo")
                else:
                    print("  ✗ La respuesta NO parece hacer referencia al área de trabajo")
            else:
                print(f"  Error en la API: {data.get('error', 'Desconocido')}")
        else:
            print(f"  Error HTTP {response.status_code}: {response.text[:200]}")
    except Exception as e:
        print(f"  Error al llamar a la API: {e}")
    
    # Test 2: Preguntar sobre nombre
    print("\nTest 2: Preguntar '¿cuál es mi nombre?'")
    
    payload = {
        'user_id': str(test_user.id),
        'message': '¿cuál es mi nombre?',
        'use_memory': True,
        'use_rag': False,
        'collections': []
    }
    
    try:
        response = requests.post(chat_api_url, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print(f"  Respuesta: {data.get('response', '')[:200]}...")
                
                # Verificar si la respuesta menciona "José" o "Luis"
                response_text = data.get('response', '').lower()
                if 'josé' in response_text or 'josé luis' in response_text or 'nombre' in response_text:
                    print("  ✓ La respuesta parece hacer referencia al nombre")
                else:
                    print("  ✗ La respuesta NO parece hacer referencia al nombre")
            else:
                print(f"  Error en la API: {data.get('error', 'Desconocido')}")
        else:
            print(f"  Error HTTP {response.status_code}: {response.text[:200]}")
    except Exception as e:
        print(f"  Error al llamar a la API: {e}")
    
    # Test 3: Preguntar sobre ubicación
    print("\nTest 3: Preguntar '¿dónde vivo?'")
    
    payload = {
        'user_id': str(test_user.id),
        'message': '¿dónde vivo?',
        'use_memory': True,
        'use_rag': False,
        'collections': []
    }
    
    try:
        response = requests.post(chat_api_url, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print(f"  Respuesta: {data.get('response', '')[:200]}...")
                
                # Verificar si la respuesta menciona "Yanahuara" o "vive"
                response_text = data.get('response', '').lower()
                if 'yanahuara' in response_text or 'vive' in response_text or 'vives' in response_text:
                    print("  ✓ La respuesta parece hacer referencia a la ubicación")
                else:
                    print("  ✗ La respuesta NO parece hacer referencia a la ubicación")
            else:
                print(f"  Error en la API: {data.get('error', 'Desconocido')}")
        else:
            print(f"  Error HTTP {response.status_code}: {response.text[:200]}")
    except Exception as e:
        print(f"  Error al llamar a la API: {e}")
    
    print("\n=== Test completado ===")

if __name__ == "__main__":
    test_chat_memory()