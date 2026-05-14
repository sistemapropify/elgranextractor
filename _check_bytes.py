import os

fp = 'd:\\proyectos\\prometeo\\webapp\\whatsapp_extractor\\templates\\whatsapp_extractor\\dashboard.html'
with open(fp, 'rb') as f:
    data = f.read()

# Check bytes around position where 'DISEÑO' should be
idx = data.find(b'DISE')
print(f"'DISE' found at byte offset: {idx}")
print(f"Bytes around 'DISE': {data[idx:idx+20].hex()}")
print(f"Raw: {data[idx:idx+20]}")

# Check bytes for 'Extracción'
idx2 = data.find(b'Extracci')
print(f"\n'Extracci' at: {idx2}")
print(f"Bytes: {data[idx2:idx2+25].hex()}")
print(f"Raw: {data[idx2:idx2+25]}")

# Check bytes for 'Última'
idx3 = data.find(b'ltima Ej')
print(f"\n'ltima Ej' at: {idx3}")
snippet = data[idx3-10:idx3+20]
print(f"Bytes around: {snippet.hex()}")
print(f"Raw: {snippet}")

# Check bytes for the first line
print(f"\nFirst 100 bytes hex: {data[:100].hex()}")
print(f"First 100 bytes: {data[:100]}")
