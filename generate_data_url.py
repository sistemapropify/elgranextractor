import base64
import os

# Leer el archivo PNG y convertirlo a data URL
png_path = 'webapp/static/requerimientos/data/Pin-propify.png'
with open(png_path, 'rb') as f:
    png_data = f.read()
    
# Convertir a base64
b64_data = base64.b64encode(png_data).decode('utf-8')
data_url = f'data:image/png;base64,{b64_data}'

# Imprimir información
print(f'Data URL length: {len(data_url)}')
print(f'PNG file size: {len(png_data)} bytes')

# Guardar la data URL en un archivo para usar en el template
output_path = 'pin_propify_data_url.txt'
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(data_url)
    
print(f'Data URL saved to {output_path}')

# También crear una versión truncada para mostrar
print(f'\nFirst 200 chars of data URL:')
print(data_url[:200])