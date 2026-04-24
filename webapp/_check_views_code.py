import os, sys, inspect
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
sys.path.insert(0, '.')
import django
django.setup()
from intelligence.views import chat_web_api
src = inspect.getsource(chat_web_api)
with open('_check_output.txt', 'w', encoding='utf-8') as f:
    for i, line in enumerate(src.split('\n')):
        if '_call_deepseek_api' in line or 'full_prompt' in line:
            f.write(f'Line {i}: {line.strip()[:120]}\n')
    f.write(f'---\nTotal lines in function: {len(src.split(chr(10)))}\n')
print("Done - check _check_output.txt")
