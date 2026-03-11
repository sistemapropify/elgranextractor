import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Python path:", sys.path)
print("Current dir:", os.getcwd())

try:
    import webapp.settings
    print("Import successful")
except Exception as e:
    print(f"Import error: {e}")
    import traceback
    traceback.print_exc()