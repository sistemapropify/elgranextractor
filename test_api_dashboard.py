#!/usr/bin/env python3
"""
Script para probar la API del dashboard de análisis.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'webapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

import django
django.setup()

from django.test import Client

def test_api():
    client = Client()
    response = client.get('/requerimientos/api/analisis-temporal/')
    print(f"Status: {response.status_code}")
    print(f"Content: {response.content[:500]}")
    
    if response.status_code == 200:
        import json
        try:
            data = json.loads(response.content)
            print(f"Success: {data.get('success')}")
            print(f"Mode: {data.get('mode')}")
            if 'error' in data:
                print(f"Error: {data['error']}")
        except Exception as e:
            print(f"Error parsing JSON: {e}")
    else:
        print("API returned non-200 status")

if __name__ == '__main__':
    test_api()