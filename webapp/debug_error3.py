import requests
from bs4 import BeautifulSoup

url = 'http://127.0.0.1:8000/propifai/dashboard/calidad/'
resp = requests.get(url)
if resp.status_code == 500:
    soup = BeautifulSoup(resp.text, 'html.parser')
    # Encontrar el div con clase 'traceback'
    traceback_div = soup.find('div', {'class': 'traceback'})
    if traceback_div:
        print('Traceback:')
        print(traceback_div.get_text())
    else:
        # Buscar el título del error
        title = soup.find('title')
        if title:
            print('Error title:', title.get_text())
        # Buscar el mensaje de error
        pre = soup.find('pre', {'class': 'exception_value'})
        if pre:
            print('Exception:', pre.get_text())
        else:
            # Imprimir algunas líneas que contengan 'NameError'
            import re
            lines = resp.text.split('\n')
            for line in lines:
                if 'NameError' in line:
                    print(line[:200])
                    break
else:
    print('Status:', resp.status_code)