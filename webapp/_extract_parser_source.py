"""Script para extraer el source del parser desde el .pyc o desde el módulo en memoria."""
import sys
import os
import marshal
import struct
import importlib.util

# Add webapp to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

# Method 1: Try to load from pyc directly by manipulating sys.modules
pyc_path = os.path.join(os.path.dirname(__file__), 
    'whatsapp_extractor', 'services', '__pycache__', 
    'whatsapp_txt_parser.cpython-314.pyc')

print(f"PYC path: {pyc_path}")
print(f"PYC exists: {os.path.exists(pyc_path)}")
print(f"PYC size: {os.path.getsize(pyc_path)}")

# Read the pyc header
with open(pyc_path, 'rb') as f:
    data = f.read()

print(f"Total PYC size: {len(data)} bytes")

# Parse header
magic = data[:4]
print(f"Magic: {magic.hex()}")
flags = struct.unpack('<I', data[4:8])[0]
print(f"Flags: {flags}")

pos = 8
if flags & 0x1:
    hash_val = data[pos:pos+8]
    pos += 8
    print(f"Hash: {hash_val.hex()}")
else:
    timestamp = struct.unpack('<I', data[pos:pos+4])[0]
    size = struct.unpack('<I', data[pos+4:pos+8])[0]
    pos += 8
    print(f"Timestamp: {timestamp}, Size: {size}")

# Load the code object
code = marshal.loads(data[pos:])
print(f"\nCode object: {code}")
print(f"co_filename: {code.co_filename}")
print(f"co_names: {code.co_names}")
print(f"co_varnames: {code.co_varnames}")
print(f"co_consts count: {len(code.co_consts)}")

# Try to decompile using dis
import dis
print("\n=== DISASSEMBLY ===")
dis.dis(code)

# Print all string constants
print("\n=== STRING CONSTANTS ===")
for i, c in enumerate(code.co_consts):
    if isinstance(c, str):
        print(f"\n--- CONST[{i}] (len={len(c)}) ---")
        print(c)
    elif hasattr(c, 'co_code'):
        print(f"\n--- CONST[{i}] CODE: {c.co_name} ---")
        print(f"  co_varnames: {c.co_varnames}")
        print(f"  co_names: {c.co_names}")
        # Print first few string consts of this code
        for j, sc in enumerate(c.co_consts):
            if isinstance(sc, str) and len(sc) > 10:
                print(f"  sub_const[{j}]: {sc[:200]}")
            elif hasattr(sc, 'co_code'):
                print(f"  sub_const[{j}]: CODE={sc.co_name}")
