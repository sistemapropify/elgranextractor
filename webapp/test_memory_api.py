#!/usr/bin/env python
"""
Probar la API de memoria /api/v1/intelligence/memory/context/
"""
import requests
import json

def test_memory_api():
    url = "http://localhost:8000/api/v1/intelligence/memory/context/"
    
    # Necesitamos un user_id en la sesión o parámetro
    # Primero, obtener una sesión de chat_web para tener user_id en sesión
    session = requests.Session()
    chat_url = "http://localhost:8000/api/v1/intelligence/chat-web/"
    
    print("Obteniendo sesión de chat...")
    try:
        response = session.get(chat_url, timeout=10)
        print(f"Chat response: {response.status_code}")
        if response.status_code != 200:
            print("No se pudo obtener sesión")
            return
    except Exception as e:
        print(f"Error obteniendo sesión: {e}")
        return
    
    # Ahora probar la API de memoria
    print(f"\nProbando API de memoria: {url}")
    try:
        response = session.get(url, timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        if response.text:
            try:
                data = response.json()
                print(f"Respuesta JSON: {json.dumps(data, indent=2)}")
            except:
                print(f"Respuesta (texto): {response.text[:500]}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_memory_api()