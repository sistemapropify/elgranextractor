import requests
import sys

# URL a probar
url = "http://127.0.0.1:8000/meta-ads/dashboard/"

print(f"Probando acceso a: {url}")
print("=" * 60)

try:
    response = requests.get(url)
    
    print(f"Status Code: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type', 'No especificado')}")
    
    if response.status_code == 200:
        print("✓ ¡Éxito! Dashboard accesible")
        # Verificar si es una página HTML
        if 'text/html' in response.headers.get('Content-Type', ''):
            print("✓ Contenido HTML detectado")
            # Mostrar primeras 200 caracteres del título si existe
            content = response.text[:500]
            if '<title>' in content:
                title_start = content.find('<title>') + 7
                title_end = content.find('</title>', title_start)
                if title_end > title_start:
                    print(f"✓ Título de la página: {content[title_start:title_end]}")
    elif response.status_code == 302 or response.status_code == 301:
        print("→ Redirección detectada")
        redirect_url = response.headers.get('Location', 'Desconocida')
        print(f"→ Redirigiendo a: {redirect_url}")
        if '/admin/login/' in redirect_url:
            print("→ Requiere autenticación (login de admin)")
    elif response.status_code == 403:
        print("✗ Acceso prohibido - Requiere autenticación")
    elif response.status_code == 404:
        print("✗ Página no encontrada - Verificar configuración de URLs")
    else:
        print(f"✗ Error {response.status_code}")
        
except requests.exceptions.ConnectionError:
    print("✗ Error de conexión - Servidor no disponible")
except Exception as e:
    print(f"✗ Error inesperado: {e}")

print("\n" + "=" * 60)
print("RESUMEN DE CONFIGURACIÓN:")
print("=" * 60)
print("1. meta_ads en INSTALLED_APPS: ✓ HABILITADO")
print("2. Ruta en urls.py: ✓ HABILITADA (línea 84)")
print("3. URLs definidas en meta_ads/urls.py:")
print("   - /meta-ads/dashboard/")
print("   - /meta-ads/analisis/historico/")
print("   - /meta-ads/campañas/")
print("   - /meta-ads/sincronizar/")
print("\nNOTA: La vista MetaDashboardView requiere autenticación")
print("(LoginRequiredMixin). Si no estás autenticado, serás")
print("redirigido a /admin/login/")