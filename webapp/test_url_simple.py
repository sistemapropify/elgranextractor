import os
import sys
import django

# Añadir el directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

try:
    django.setup()
    print("✅ Django configurado correctamente")
    
    from django.urls import reverse, resolve
    
    # Verificar que la URL exista
    try:
        url = reverse('configurar_jerarquia')
        print(f"✅ URL configurada correctamente: {url}")
        
        # Verificar que resuelva a la vista correcta
        match = resolve(url)
        print(f"✅ Resuelve a: {match.func.__name__ if hasattr(match.func, '__name__') else match.func}")
        print(f"✅ Patrón: {match.route}")
        
        # Verificar que la vista sea accesible
        from cuadrantizacion import views
        if hasattr(views, 'configurar_jerarquia'):
            print("✅ Vista configurar_jerarquia existe en views.py")
            
            # Verificar que el template exista
            import os
            template_path = os.path.join(os.path.dirname(__file__), 'templates', 'cuadrantizacion', 'configurar_jerarquia.html')
            if os.path.exists(template_path):
                print(f"✅ Template existe: {template_path}")
            else:
                print(f"❌ Template NO existe: {template_path}")
                
            # Verificar template parcial
            template_partial_path = os.path.join(os.path.dirname(__file__), 'templates', 'cuadrantizacion', '_tree_node.html')
            if os.path.exists(template_partial_path):
                print(f"✅ Template parcial existe: {template_partial_path}")
            else:
                print(f"❌ Template parcial NO existe: {template_partial_path}")
                
        else:
            print("❌ Vista configurar_jerarquia NO existe en views.py")
            
    except Exception as e:
        print(f"❌ Error al verificar URL: {e}")
        import traceback
        traceback.print_exc()
        
except Exception as e:
    print(f"❌ Error general: {e}")
    import traceback
    traceback.print_exc()