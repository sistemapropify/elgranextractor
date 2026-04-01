import sys
sys.path.insert(0, 'webapp')
try:
    import webapp
    print('webapp import ok')
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()