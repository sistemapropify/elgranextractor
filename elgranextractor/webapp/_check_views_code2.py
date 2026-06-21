import os, sys, inspect
os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
sys.path.insert(0, '.')
import django
django.setup()
from intelligence.views import chat_web_api
with open('_check_output2.txt', 'w', encoding='utf-8') as f:
    f.write(f'Type: {type(chat_web_api)}\n')
    f.write(f'Has __wrapped__: {hasattr(chat_web_api, "__wrapped__")}\n')
    if hasattr(chat_web_api, '__wrapped__'):
        f.write(f'Wrapped: {chat_web_api.__wrapped__}\n')
    f.write(f'Has __closure__: {hasattr(chat_web_api, "__closure__")}\n')
    # Try to get the original function
    if hasattr(chat_web_api, '__wrapped__'):
        real_func = chat_web_api.__wrapped__
    else:
        real_func = chat_web_api
    try:
        src = inspect.getsource(real_func)
        f.write(f'Source lines: {len(src.split(chr(10)))}\n')
        for i, line in enumerate(src.split('\n')):
            if '_call_deepseek_api' in line or 'full_prompt' in line or 'generate_rag_response' in line:
                f.write(f'Line {i}: {line.strip()[:150]}\n')
    except Exception as e:
        f.write(f'Error getting source: {e}\n')
print("Done")
