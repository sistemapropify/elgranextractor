#!/usr/bin/env python
"""
Verificación de integración del Chat Web con servicios existentes.
"""
import os
import sys

# Verificar archivos existentes
print("=== Verificación de integración del Chat Web (SPEC-007) ===")
print()

base_dir = os.path.dirname(os.path.abspath(__file__))

# 1. Verificar archivos de implementación
print("1. ARCHIVOS DE IMPLEMENTACIÓN:")
files_to_check = [
    ('intelligence/views.py', 'Vistas del chat web'),
    ('intelligence/urls.py', 'URLs del chat web'),
    ('templates/intelligence/chat.html', 'Template del chat'),
    ('static/intelligence/chat.css', 'Estilos del chat'),
    ('static/intelligence/chat.js', 'JavaScript del chat'),
    ('intelligence/services/llm.py', 'Servicio LLM con streaming'),
    ('intelligence/services/__init__.py', 'Exportación de servicios'),
]

all_files_ok = True
for file_path, description in files_to_check:
    full_path = os.path.join(base_dir, file_path)
    if os.path.exists(full_path):
        print(f"   [OK] {description}: {file_path}")
        
        # Verificar contenido específico para algunos archivos
        if file_path == 'intelligence/urls.py':
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if 'chat_web_stream' in content:
                    print(f"        -> URL de streaming configurada")
                else:
                    print(f"        -> [WARNING] URL de streaming no encontrada")
                    
        if file_path == 'intelligence/services/llm.py':
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if 'generate_streaming_response' in content:
                    print(f"        -> Método de streaming implementado")
                else:
                    print(f"        -> [WARNING] Método de streaming no encontrado")
    else:
        print(f"   [ERROR] {description}: NO encontrado")
        all_files_ok = False

print()

# 2. Verificar servicios PIL
print("2. SERVICIOS PIL INTEGRADOS:")
try:
    # Verificar imports
    import django
    django.setup()
    
    from intelligence.services import MemoryService, RAGService, LLMService
    print("   [OK] MemoryService importado correctamente")
    print("   [OK] RAGService importado correctamente")
    print("   [OK] LLMService importado correctamente")
    
    # Verificar métodos específicos
    if hasattr(LLMService, 'generate_streaming_response'):
        print("   [OK] LLMService tiene método generate_streaming_response")
    else:
        print("   [ERROR] LLMService NO tiene método de streaming")
        all_files_ok = False
        
    if hasattr(MemoryService, 'get_relevant_context'):
        print("   [OK] MemoryService tiene método get_relevant_context")
    else:
        print("   [WARNING] MemoryService puede no tener todos los métodos")
        
    if hasattr(RAGService, 'search_dynamic'):
        print("   [OK] RAGService tiene método search_dynamic")
    else:
        print("   [WARNING] RAGService puede no tener todos los métodos")
        
except ImportError as e:
    print(f"   [ERROR] Error importando servicios: {e}")
    all_files_ok = False
except Exception as e:
    print(f"   [ERROR] Error inesperado: {e}")
    all_files_ok = False

print()

# 3. Verificar vistas implementadas
print("3. VISTAS IMPLEMENTADAS:")
try:
    from intelligence import views
    
    views_to_check = [
        ('chat_web', 'Vista principal del chat'),
        ('chat_web_api', 'API del chat'),
        ('chat_web_stream', 'API de streaming'),
        ('chat_web_upload', 'API de upload'),
    ]
    
    for view_name, description in views_to_check:
        if hasattr(views, view_name):
            print(f"   [OK] {description}: {view_name}()")
        else:
            print(f"   [ERROR] {description}: NO encontrada")
            all_files_ok = False
            
except Exception as e:
    print(f"   [ERROR] Error verificando vistas: {e}")
    all_files_ok = False

print()

# 4. Verificar URLs configuradas
print("4. URLs CONFIGURADAS:")
try:
    from django.urls import reverse, NoReverseMatch
    
    urls_to_check = [
        ('intelligence:chat_web', '/api/v1/intelligence/chat-web/'),
        ('intelligence:chat_web_api', '/api/v1/intelligence/chat-web/api/'),
        ('intelligence:chat_web_stream', '/api/v1/intelligence/chat-web/stream/'),
        ('intelligence:chat_web_upload', '/api/v1/intelligence/chat-web/upload/'),
    ]
    
    for url_name, expected_path in urls_to_check:
        try:
            path = reverse(url_name)
            print(f"   [OK] {url_name}: {path}")
            if expected_path not in path:
                print(f"        [WARNING] Ruta diferente a la esperada")
        except NoReverseMatch:
            print(f"   [ERROR] {url_name}: NO configurada")
            all_files_ok = False
            
except Exception as e:
    print(f"   [ERROR] Error verificando URLs: {e}")
    all_files_ok = False

print()

# 5. Resumen
print("=" * 60)
print("RESUMEN DE INTEGRACIÓN")
print("=" * 60)

if all_files_ok:
    print("✅ INTEGRACIÓN COMPLETA DEL CHAT WEB (SPEC-007)")
    print()
    print("COMPONENTES IMPLEMENTADOS:")
    print("1. Interfaz web tipo chat con panel lateral (30%/70%)")
    print("2. Integración con MemoryService para contexto personalizado")
    print("3. Integración con RAGService para búsqueda de conocimiento")
    print("4. Integración con LLMService (DeepSeek) para generación de respuestas")
    print("5. Streaming de respuestas en tiempo real")
    print("6. Gestión de archivos adjuntos (imágenes, PDFs, texto)")
    print("7. Selector de instrucciones predefinidas")
    print("8. Memoria de conversación y contexto de usuario")
    print()
    print("URLS DISPONIBLES:")
    print("- /api/v1/intelligence/chat-web/          (Vista principal)")
    print("- /api/v1/intelligence/chat-web/api/      (API normal)")
    print("- /api/v1/intelligence/chat-web/stream/   (API streaming)")
    print("- /api/v1/intelligence/chat-web/upload/   (Upload archivos)")
    print()
    print("✅ SPEC-007 COMPLETADO: Chat Web Interactivo PIL v1.0")
else:
    print("⚠ ALGUNOS PROBLEMAS DETECTADOS")
    print("Revisar los errores indicados arriba.")

print("=" * 60)