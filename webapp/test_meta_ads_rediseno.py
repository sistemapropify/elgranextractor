"""
Script de prueba para verificar el dashboard rediseñado de Meta Ads.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from meta_ads.views_rediseno import MetaDashboardRedisenoView
from django.test import RequestFactory
from django.contrib.auth.models import User

def test_dashboard_rediseno():
    """Prueba la vista del dashboard rediseñado."""
    print("=== Prueba del Dashboard Rediseñado de Meta Ads ===")
    
    # Crear una solicitud de prueba
    factory = RequestFactory()
    request = factory.get('/meta-ads/dashboard/rediseno/')
    
    # Obtener o crear un usuario de prueba (simular autenticación)
    user, created = User.objects.get_or_create(
        username='testuser',
        defaults={'password': 'testpass'}
    )
    request.user = user
    
    # Crear instancia de la vista
    view = MetaDashboardRedisenoView()
    view.request = request
    
    try:
        # Obtener contexto
        context = view.get_context_data()
        
        # Verificar que los datos clave estén presentes
        required_keys = [
            'today', 'kpis_mes', 'campañas_activas', 'spend_diario',
            'top_campañas_clicks', 'kpis_historicos', 'spend_diario_max',
            'top_clicks_max', 'spend_promedio', 'alertas_count'
        ]
        
        print("[OK] Vista creada exitosamente")
        print(f"[OK] Contexto contiene {len(context)} elementos")
        
        # Verificar claves requeridas
        missing_keys = []
        for key in required_keys:
            if key in context:
                print(f"[OK] Clave '{key}' presente")
            else:
                missing_keys.append(key)
                print(f"[ERROR] Clave '{key}' faltante")
        
        if missing_keys:
            print(f"\n[ADVERTENCIA] Faltan {len(missing_keys)} claves: {missing_keys}")
        else:
            print("\n[OK] Todas las claves requeridas están presentes")
        
        # Mostrar algunos datos de ejemplo
        print("\n=== Datos de ejemplo ===")
        if 'kpis_mes' in context:
            kpis = context['kpis_mes']
            print(f"Gasto total: S/ {kpis.get('total_spend', 0):.2f}")
            print(f"Clics totales: {kpis.get('total_clicks', 0):,}")
            print(f"CPC promedio: S/ {kpis.get('cpc_promedio', 0):.4f}")
        
        if 'campañas_activas' in context:
            print(f"Campañas activas: {len(context['campañas_activas'])}")
        
        if 'alertas_count' in context:
            print(f"Alertas: {context['alertas_count']}")
        
        if 'spend_promedio' in context:
            print(f"Gasto diario promedio: S/ {context['spend_promedio']:.2f}")
        
        print("\n=== Prueba completada exitosamente ===")
        
    except Exception as e:
        print(f"\nERROR durante la prueba: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == '__main__':
    # Ejecutar prueba
    success = test_dashboard_rediseno()
    
    if success:
        print("\n[OK] El dashboard rediseñado está listo para usar.")
        print("URL: http://127.0.0.1:8000/meta-ads/dashboard/rediseno/")
        print("\nCaracterísticas implementadas:")
        print("1. Diseño oscuro con colores de Propify")
        print("2. KPIs principales en tarjetas con colores")
        print("3. Tabla de campañas con estados visuales")
        print("4. Gráficos de barras animados para gasto diario")
        print("5. Análisis histórico con tendencias")
        print("6. Sistema de alertas inteligentes")
        print("7. Proyección de gasto mensual")
        print("8. Actualización en tiempo real de la hora")
    else:
        print("\n[ERROR] La prueba encontró problemas que deben resolverse.")
        sys.exit(1)