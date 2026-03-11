import os
import sys
import django
from django.template import Template, TemplateSyntaxError
from django.conf import settings

# Configurar Django
sys.path.insert(0, 'd:/proyectos/prometeo/webapp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

try:
    django.setup()
except Exception as e:
    print(f"Error configurando Django: {e}")
    sys.exit(1)

# Leer el template
template_path = 'market_analysis/templates/market_analysis/heatmap.html'
full_path = os.path.join('webapp', template_path)

try:
    with open(full_path, 'r', encoding='utf-8') as f:
        template_content = f.read()
except FileNotFoundError:
    print(f"Archivo no encontrado: {full_path}")
    sys.exit(1)

# Intentar compilar el template
try:
    template = Template(template_content)
    print("OK: Template compilado correctamente")
except TemplateSyntaxError as e:
    print(f"ERROR: Error de sintaxis en template: {e}")
    print(f"  Línea: {e.lineno}, Mensaje: {e}")
except Exception as e:
    print(f"ERROR: Error inesperado: {e}")

# Verificar si hay tags sin cerrar
from django.template.base import Lexer, TOKEN_TEXT, TOKEN_VAR, TOKEN_BLOCK
lexer = Lexer(template_content)
tokens = lexer.tokenize()

block_stack = []
for token in tokens:
    if token.token_type == TOKEN_BLOCK:
        content = token.contents.strip()
        if content.startswith('block '):
            block_stack.append(content)
        elif content == 'endblock':
            if block_stack:
                block_stack.pop()
            else:
                print(f"  Advertencia: endblock sin block correspondiente")

if block_stack:
    print(f"  Advertencia: bloques sin cerrar: {block_stack}")
else:
    print("✓ Todos los bloques están balanceados")