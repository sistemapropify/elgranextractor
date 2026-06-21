"""Script para ejecutar makemigrations respondiendo automáticamente los prompts."""
import subprocess
import sys

def run_makemigrations(app_label=None):
    """Ejecuta makemigrations y responde prompts interactivos automáticamente."""
    cmd = [sys.executable, 'manage.py', 'makemigrations']
    if app_label:
        cmd.append(app_label)
    
    # Las respuestas a los prompts de cambio nullable → non-nullable:
    # Usamos opción 2 (Ignore for now) para cada campo, que no requiere follow-up.
    # 4 prompts:
    #   1. extractorlog.mensaje_error
    #   2. extractorlog.stack_trace
    #   3. whatsappgroupsession.fuente_choice
    #   4. whatsappgroupsession.mensaje_error
    input_data = "2\n2\n2\n2\n"
    
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd='d:\\proyectos\\prometeo\\webapp',
    )
    
    stdout, _ = process.communicate(input=input_data)
    print(stdout)
    return process.returncode

if __name__ == '__main__':
    app = sys.argv[1] if len(sys.argv) > 1 else None
    sys.exit(run_makemigrations(app))
