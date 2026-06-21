import subprocess, sys, os, time

os.chdir(os.path.dirname(__file__))

python = r'C:\Users\USUARIO\AppData\Local\Python\bin\python.exe'

# Provide inputs for 4 interactive prompts:
# Each prompt: option 1 (provide a default) then '' (empty string default value)
# 1. extractorlog.mensaje_error -> option 1 -> default ''
# 2. extractorlog.stack_trace -> option 1 -> default ''
# 3. whatsappgroupsession.fuente_choice -> option 1 -> default ''
# 4. whatsappgroupsession.mensaje_error -> option 1 -> default ''
inputs = '1\n\'\'\n1\n\'\'\n1\n\'\'\n1\n\'\'\n'

print("=== Running makemigrations ===")
print(f"Inputs to send: {repr(inputs)}")
print()

proc = subprocess.Popen(
    [python, 'manage.py', 'makemigrations', 'agentes', '--name', 'logo_icono_marcador'],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True
)
stdout, _ = proc.communicate(input=inputs, timeout=60)
print(stdout)

# Check if migration was created
migrations_dir = os.path.join(os.path.dirname(__file__), 'agentes', 'migrations')
files = sorted([f for f in os.listdir(migrations_dir) if f.endswith('.py') and f != '__init__.py'])
print(f'\n=== Migration files in agentes/migrations: {files} ===')

# Also check if any other migrations were created
for app in ['whatsapp_extractor']:
    app_migrations_dir = os.path.join(os.path.dirname(__file__), app, 'migrations')
    if os.path.isdir(app_migrations_dir):
        app_files = sorted([f for f in os.listdir(app_migrations_dir) if f.endswith('.py') and f != '__init__.py'])
        if len(app_files) > 0:
            print(f'\nMigration files in {app}/migrations: {app_files}')
