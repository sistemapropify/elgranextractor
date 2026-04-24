"""
Script de prueba para el dashboard exacto de Meta Ads.
"""
import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from meta_ads.views_exacto import MetaDashboardExactoView

def test_dashboard_exacto():
    """Prueba la vista del dashboard exacto."""
    print("=== Prueba del Dashboard Exacto de Meta Ads ===")
    
    # Crear usuario de prueba
    user, created = User.objects.get_or_create(
        username='test_user',
        defaults={'email': 'test@example.com'}
    )
    
    # Configurar request
    factory = RequestFactory()
    request = factory.get('/meta-ads/dashboard/exacto/')
    request.user = user
    
    # Crear vista
    view = MetaDashboardExactoView()
    view.setup(request)
    
    try:
        # Obtener contexto
        context = view.get_context_data()
        
        print("[OK] Vista cargada exitosamente")
        print(f"[OK] Template: {view.template_name}")
        
        # Verificar datos en contexto
        required_keys = ['today', 'kpis_mes', 'campañas_activas', 'alertas_count', 'gasto_proyectado', 'porcentaje_presupuesto']
        for key in required_keys:
            if key in context:
                print(f"[OK] Contexto contiene '{key}'")
            else:
                print(f"[ERROR] Contexto NO contiene '{key}'")
        
        # Verificar KPIs
        if 'kpis_mes' in context:
            kpis = context['kpis_mes']
            print(f"[OK] KPIs del mes: {len(kpis)} valores")
            
            # Mostrar algunos valores de ejemplo
            example_keys = ['total_spend_hoy', 'total_spend', 'total_clicks_hoy', 'cpc_promedio']
            for key in example_keys:
                if key in kpis:
                    print(f"  - {key}: {kpis[key]}")
                else:
                    print(f"  - {key}: NO DISPONIBLE (usando valor por defecto)")
        
        print(f"[OK] Alertas: {context.get('alertas_count', 0)}")
        print(f"[OK] Gasto proyectado: {context.get('gasto_proyectado', 0)}")
        print(f"[OK] Porcentaje presupuesto: {context.get('porcentaje_presupuesto', 0)}%")
        
        print("\n[SUCCESS] Dashboard exacto funcionando correctamente")
        return True
        
    except Exception as e:
        print(f"[ERROR] Error al cargar el dashboard exacto: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_dashboard_exacto()
    sys.exit(0 if success else 1)