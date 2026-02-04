#!/usr/bin/env python
"""
Script para probar la conexión y subida de documentos a Azure Blob Storage.
"""
import os
import sys
import django
import logging

# Configurar Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
django.setup()

from captura.azure_storage import (
    get_blob_service_client,
    ensure_container_exists,
    upload_raw_html,
    list_blobs,
    AzureStorageError
)
from django.conf import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_connection():
    """Prueba la conexión a Azure Storage."""
    print("=== Prueba de conexión a Azure Storage ===")
    try:
        # Verificar configuración
        print(f"RAW_HTML_STORAGE: {settings.RAW_HTML_STORAGE}")
        print(f"AZURE_STORAGE_CONTAINER_NAME: {settings.AZURE_STORAGE_CONTAINER_NAME}")
        
        # Obtener cliente
        client = get_blob_service_client()
        print("[OK] Cliente de Azure Storage creado exitosamente")
        
        # Verificar contenedor
        container_client = ensure_container_exists()
        print(f"[OK] Contenedor '{settings.AZURE_STORAGE_CONTAINER_NAME}' verificado/creado")
        
        # Listar blobs existentes
        blobs = list_blobs()
        print(f"[OK] Número de blobs en el contenedor: {len(blobs)}")
        if blobs:
            print("  Blobs encontrados:")
            for blob in blobs[:5]:  # Mostrar primeros 5
                print(f"    - {blob}")
            if len(blobs) > 5:
                print(f"    ... y {len(blobs) - 5} más")
        
        return True
    except AzureStorageError as e:
        print(f"[ERROR] Error de Azure Storage: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_upload_html():
    """Prueba subir un documento HTML de ejemplo."""
    print("\n=== Prueba de subida de HTML ===")
    try:
        # Contenido HTML de ejemplo
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Documento de prueba</title>
        </head>
        <body>
            <h1>Prueba de Azure Blob Storage</h1>
            <p>Este es un documento HTML de prueba subido desde Django.</p>
            <p>Fecha: 2026-02-03</p>
        </body>
        </html>
        """
        
        # Subir con fuente_id = 1 (de prueba)
        fuente_id = 1
        print(f"Subiendo HTML para fuente_id={fuente_id}...")
        
        blob_url = upload_raw_html(html_content, fuente_id)
        
        if blob_url:
            print(f"[OK] HTML subido exitosamente")
            print(f"  URL: {blob_url}")
            
            # Verificar que aparece en la lista
            blobs = list_blobs(prefix=f"fuentes/{fuente_id}/")
            print(f"  Blobs con prefijo 'fuentes/{fuente_id}/': {len(blobs)}")
            for blob in blobs:
                print(f"    - {blob}")
            
            return True
        else:
            print("[ERROR] No se pudo subir el HTML (RAW_HTML_STORAGE no es 'blob_storage'?)")
            return False
    except AzureStorageError as e:
        print(f"[ERROR] Error al subir HTML: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Función principal."""
    print("Iniciando pruebas de Azure Blob Storage...")
    
    # Verificar que RAW_HTML_STORAGE está configurado como 'blob_storage'
    if settings.RAW_HTML_STORAGE != 'blob_storage':
        print(f"ADVERTENCIA: RAW_HTML_STORAGE está configurado como '{settings.RAW_HTML_STORAGE}'")
        print("Para probar Azure Storage, configurar RAW_HTML_STORAGE = 'blob_storage' en settings.py")
        print("Continuando con pruebas de conexión...")
    
    # Ejecutar pruebas
    connection_ok = test_connection()
    
    if connection_ok:
        upload_ok = test_upload_html()
    else:
        upload_ok = False
        print("No se puede probar subida debido a error de conexión")
    
    # Resumen
    print("\n=== Resumen de pruebas ===")
    print(f"Conexión: {'[OK]' if connection_ok else '[ERROR] FALLÓ'}")
    print(f"Subida: {'[OK]' if upload_ok else '[ERROR] FALLÓ'}")
    
    if connection_ok and upload_ok:
        print("\n¡Todas las pruebas pasaron! Azure Storage está configurado correctamente.")
        return 0
    else:
        print("\nAlgunas pruebas fallaron. Revisar configuración.")
        return 1

if __name__ == '__main__':
    sys.exit(main())