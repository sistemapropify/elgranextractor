import inspect  
from intelligence.views import chat_web_api  
src = inspect.getsource(chat_web_api)  
for i, line in enumerate(src.split('\n')):  
    if '_call_deepseek_api' in line or 'full_prompt' in line:  
        print(f'Line {i}: {line.strip()[:120]}')  
