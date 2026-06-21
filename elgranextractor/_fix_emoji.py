import os, sys

# Force UTF-8 for stdout
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

filepath = os.path.join('webapp', 'whatsapp_extractor', 'templates', 'whatsapp_extractor', 'dashboard.html')
abs_path = os.path.abspath(filepath)

with open(abs_path, 'rb') as f:
    data = f.read()

FOLDER_EMOJI = bytes([0xF0, 0x9F, 0x93, 0x81])  # 📁 UTF-8: F0 9F 93 81

targets = [
    # Pattern: U+FFFD (EF BF BD) + '?' (3F) + ' Archivos'
    (b'\xef\xbf\xbd\x3f\x20Archivos', FOLDER_EMOJI + b' Archivos'),
    # Pattern: U+FFFD U+FFFD (EF BF BD EF BF BD) + ' Archivos'
    (b'\xef\xbf\xbd\xef\xbf\xbd\x20Archivos', FOLDER_EMOJI + b' Archivos'),
    # Pattern: '?' '?' (3F 3F) + ' Archivos'
    (b'\x3f\x3f\x20Archivos', FOLDER_EMOJI + b' Archivos'),
]

fixed = False
for pattern, replacement in targets:
    if pattern in data:
        data = data.replace(pattern, replacement)
        print(f"Fixed: replaced pattern at byte offset {data.find(pattern)}")
        fixed = True

if not fixed:
    print("No known patterns found. Searching for corrupted bytes near 'Archivos'...")
    idx = data.find(b'Archivos')
    if idx > 0:
        start = max(0, idx - 20)
        surrounding = data[start:idx+10]
        print(f"Found 'Archivos' at byte offset {idx}")
        print(f"Hex: {surrounding.hex()}")
        
        # Try broader replacement: any U+FFFD + optional '?' + ' Archivos'
        import re
        # U+FFFD in UTF-8 = EF BF BD
        corrupted_pattern = re.compile(b'\xef\xbf\xbd.?Archivos')
        matches = corrupted_pattern.findall(data)
        for m in matches:
            print(f"Found corrupted match: {m.hex()} = {m}")

if fixed:
    with open(abs_path, 'wb') as f:
        f.write(data)
    print(f"File updated successfully!")
else:
    print("No changes made.")
