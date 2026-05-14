import os
import glob

def fix_file_bytes(filepath):
    """Fix double-encoded UTF-8 at the byte level."""
    with open(filepath, 'rb') as f:
        data = bytearray(f.read())
    
    # Remove BOM if present
    if data[:3] == b'\xef\xbb\xbf':
        data = data[3:]
    
    # Convert back to bytes for processing
    data = bytes(data)
    
    # The fix: decode as UTF-8, then manually handle bytes
    garbled = data.decode('utf-8', errors='replace')
    
    # Build the correct bytes by encoding each character
    result = bytearray()
    i = 0
    while i < len(garbled):
        cp = ord(garbled[i])
        if cp <= 255:
            # Could be a single-byte character or part of double-encoding
            result.append(cp)
        elif cp == 0xFFFD:
            # Replacement character - try to figure out original
            # In practice, this was likely byte 0x81 or 0x8D etc that is unmapped in cp1252
            # For emoji bytes that couldn't be mapped, the original byte was lost
            # We'll need to handle known cases
            result.append(0x3F)  # '?' placeholder
        else:
            # Character > 255 - encode as UTF-8
            result.extend(garbled[i].encode('utf-8'))
        i += 1
    
    # Now decode result as Latin-1 to get the original UTF-8 bytes
    try:
        recovered = bytes(result).decode('latin-1')
        final = recovered.encode('utf-8')
        
        # Check for improvement
        if final == data:
            return False
        
        with open(filepath, 'wb') as f:
            f.write(final)
        print(f"FIXED: {os.path.basename(filepath)}")
        return True
    except Exception as e:
        print(f"ERROR {os.path.basename(filepath)}: {e}")
        return False

template_dir = 'd:\\proyectos\\prometeo\\webapp\\whatsapp_extractor\\templates\\whatsapp_extractor'
html_files = glob.glob(os.path.join(template_dir, '*.html'))

fixed_count = 0
for fp in html_files:
    if fix_file_bytes(fp):
        fixed_count += 1

print(f"Fixed {fixed_count}/{len(html_files)} files.")
