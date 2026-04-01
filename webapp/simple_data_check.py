#!/usr/bin/env python
"""
Script simple para verificar los datos que se muestran en el dashboard.
"""
import requests
import json

def check_dashboard_data():
    """Verificar datos del dashboard"""
    url = "http://localhost:8000/propifai/dashboard/visitas/"
    
    print("=== VERIFICACIÓN DE DATOS DEL DASHBOARD ===")
    
    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            html = response.text
            
            # Extraer el JSON de propiedades
            if 'propertiesData = ' in html:
                start = html.find('propertiesData = ') + len('propertiesData = ')
                end = html.find('];', start) + 1
                
                if end > start:
                    json_str = html[start:end]
                    try:
                        properties = json.loads(json_str)
                        print(f"\n1. TOTAL PROPIEDADES: {len(properties)}")
                        
                        # Analizar las primeras 3 propiedades
                        print("\n2. ANÁLISIS DE PRIMERAS 3 PROPIEDADES:")
                        for i, prop in enumerate(properties[:3]):
                            print(f"\n   Propiedad {i+1} ({prop.get('code', 'N/A')}):")
                            print(f"      - Título: {prop.get('title', 'N/A')}")
                            print(f"      - Dirección: {prop.get('address', 'N/A')}")
                            print(f"      - Distrito: {prop.get('district', 'N/A')}")
                            print(f"      - Zona: {prop.get('zone', 'N/A')}")
                            print(f"      - Estado: {prop.get('status', 'N/A')}")
                            print(f"      - Precio: {prop.get('price', 'N/A')}")
                            print(f"      - Agente: {prop.get('agent_name', 'N/A')}")
                            print(f"      - Total eventos: {prop.get('total_eventos', 0)}")
                            print(f"      - Primera visita: {prop.get('primera_visita', 'N/A')}")
                            print(f"      - Última visita: {prop.get('ultima_visita', 'N/A')}")
                            print(f"      - Tiene lead: {prop.get('tiene_lead', False)}")
                            print(f"      - Tiene propuesta: {prop.get('tiene_propuesta', False)}")
                            print(f"      - Días en cartera: {prop.get('dias_en_cartera', 'N/A')}")
                        
                        # Verificar problemas comunes
                        print("\n3. PROBLEMAS DETECTADOS:")
                        
                        # Problema 1: Distrito muestra "propiedad"
                        distrito_problema = sum(1 for p in properties if p.get('district') == 'propiedad' or p.get('district') == 'Propiedad')
                        if distrito_problema > 0:
                            print(f"   - {distrito_problema} propiedades tienen 'propiedad' como distrito")
                        
                        # Problema 2: Zona muestra "agente"
                        zona_problema = sum(1 for p in properties if p.get('zone') == 'agente' or p.get('zone') == 'Agente')
                        if zona_problema > 0:
                            print(f"   - {zona_problema} propiedades tienen 'agente' como zona")
                        
                        # Problema 3: Precio muestra fechas
                        precio_fecha = sum(1 for p in properties if isinstance(p.get('price'), str) and '-' in str(p.get('price')))
                        if precio_fecha > 0:
                            print(f"   - {precio_fecha} propiedades tienen fecha como precio")
                        
                        # Problema 4: Fechas de visita incorrectas
                        sin_fechas = sum(1 for p in properties if p.get('primera_visita') is None and p.get('total_eventos', 0) > 0)
                        if sin_fechas > 0:
                            print(f"   - {sin_fechas} propiedades con eventos pero sin fechas de visita")
                        
                        # Mostrar estructura de datos
                        print("\n4. ESTRUCTURA DE DATOS (campos disponibles):")
                        if properties:
                            first_prop = properties[0]
                            for key in sorted(first_prop.keys()):
                                print(f"   - {key}: {type(first_prop[key]).__name__}")
                        
                    except json.JSONDecodeError as e:
                        print(f"\n[ERROR] No se pudo parsear JSON: {e}")
                        print(f"Fragmento: {json_str[:200]}...")
                else:
                    print("\n[ERROR] No se pudo extraer JSON")
            else:
                print("\n[ERROR] No se encontró propertiesData en el HTML")
                
        else:
            print(f"\n[ERROR] HTTP {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("\n[ERROR] No se pudo conectar al servidor")
    except Exception as e:
        print(f"\n[ERROR] {e}")

if __name__ == "__main__":
    check_dashboard_data()