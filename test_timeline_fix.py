import requests
import json
import sys

def test_timeline_api(property_id):
    url = f'http://localhost:8000/propifai/api/property/{property_id}/timeline/'
    print(f'Probando API: {url}')
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print('=== DATOS DE PROPIEDAD ===')
            prop = data.get('property', {})
            print(f'ID: {prop.get("id")}')
            print(f'Código: {prop.get("code")}')
            print(f'Fecha creación: {prop.get("created_at")}')
            print(f'Precio/m²: {prop.get("precio_m2")}')
            
            print('\n=== ETAPAS ===')
            etapas = data.get('timeline', {}).get('etapas', [])
            for etapa in etapas:
                print(f"{etapa['id']}. {etapa['nombre']}: {etapa['fecha_inicio']} (estado: {etapa['estado']})")
            
            print('\n=== CONECTORES (días transcurridos) ===')
            conectores = data.get('timeline', {}).get('conectores', [])
            for con in conectores:
                print(f"{con['desde']}→{con['hacia']}: {con['dias_transcurridos']} días (benchmark: {con['benchmark']}, dentro: {con['dentro_benchmark']})")
            
            # Verificar que no haya días cero incorrectos
            zero_days = [c for c in conectores if c['dias_transcurridos'] == 0]
            if zero_days:
                print(f'\n⚠️  Hay {len(zero_days)} conectores con 0 días:')
                for c in zero_days:
                    print(f"   {c['desde']}→{c['hacia']}")
            else:
                print('\n✅ Todos los conectores tienen días > 0 (o fechas faltantes)')
            
            # Verificar que las fechas de etapas 1 y 2 no tengan offset
            if len(etapas) >= 2:
                fecha1 = etapas[0]['fecha_inicio']
                fecha2 = etapas[1]['fecha_inicio']
                print(f'\nFecha etapa 1 (Captación): {fecha1}')
                print(f'Fecha etapa 2 (Publicación): {fecha2}')
                if fecha1 and fecha2:
                    # Verificar que no tengan componente de hora (solo fecha)
                    if 'T' in fecha1:
                        print('⚠️  Fecha etapa 1 contiene hora (posible offset)')
                    if 'T' in fecha2:
                        print('⚠️  Fecha etapa 2 contiene hora (posible offset)')
            
            return True
        else:
            print(f'Error HTTP {response.status_code}: {response.text}')
            return False
    except Exception as e:
        print(f'Error al conectar: {e}')
        return False

if __name__ == '__main__':
    # Obtener un ID de propiedad de la línea de comandos o usar uno por defecto
    if len(sys.argv) > 1:
        property_id = sys.argv[1]
    else:
        # Intentar obtener un ID de propiedad desde la base de datos
        import os
        import django
        sys.path.append('d:/proyectos/prometeo')
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
        django.setup()
        from propifai.models import PropifaiProperty
        prop = PropifaiProperty.objects.filter(created_at__isnull=False).first()
        if prop:
            property_id = prop.id
            print(f'Usando propiedad ID: {property_id} (código: {prop.code})')
        else:
            print('No se encontraron propiedades. Especifica un ID como argumento.')
            sys.exit(1)
    
    test_timeline_api(property_id)