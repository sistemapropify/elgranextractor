import os
import glob

def fix_mojibake(filepath):
    """Fix double-encoded UTF-8 (mojibake via Windows-1252) in a file."""
    with open(filepath, 'rb') as f:
        raw_bytes = f.read()
    
    # Remove BOM if present
    if raw_bytes[:3] == b'\xef\xbb\xbf':
        raw_bytes = raw_bytes[3:]
    
    try:
        # Step 1: Decode the file as UTF-8 (this gives us the garbled text)
        garbled = raw_bytes.decode('utf-8')
        
        # Step 2: Try to recover original by encoding as cp1252 (Windows encoding)
        # Use 'replace' for any chars outside cp1252 range (emojis, etc.)
        recovered_bytes = garbled.encode('cp1252', errors='replace')
        
        # Step 3: Decode as UTF-8 to get correct text
        fixed_text = recovered_bytes.decode('utf-8', errors='replace')
        
        # Check if anything actually changed
        if fixed_text.encode('utf-8') == raw_bytes:
            return False
        
        with open(filepath, 'wb') as f:
            f.write(fixed_text.encode('utf-8'))
        print(f"FIXED: {os.path.basename(filepath)}")
        return True
    except Exception as e:
        print(f"ERROR {os.path.basename(filepath)}: {e}")
        return False

template_dir = 'd:\\proyectos\\prometeo\\webapp\\whatsapp_extractor\\templates\\whatsapp_extractor'
html_files = glob.glob(os.path.join(template_dir, '*.html'))

fixed_count = 0
for fp in html_files:
    if fix_mojibake(fp):
        fixed_count += 1

print(f"\nFixed {fixed_count}/{len(html_files)} files.")
