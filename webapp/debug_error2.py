import requests
import sys

url = 'http://127.0.0.1:8000/propifai/dashboard/calidad/'
try:
    resp = requests.get(url)
    print('Status:', resp.status_code)
    if resp.status_code == 500:
        # Buscar la sección de traceback
        import re
        if 'Traceback' in resp.text:
            start = resp.text.find('<div class="context">')
            if start != -1:
                # Extraer texto sin HTML
                from html.parser import HTMLParser
                class MLStripper(HTMLParser):
                    def __init__(self):
                        super().__init__()
                        self.strict = False
                        self.convert_charrefs= True
                        self.text = []
                    def handle_data(self, d):
                        self.text.append(d)
                    def get_data(self):
                        return ''.join(self.text)
                stripper = MLStripper()
                stripper.feed(resp.text[start:start+5000])
                print('Error details:')
                print(stripper.get_data()[:2000])
        else:
            print('No traceback found')
    print('Response length:', len(resp.text))
except Exception as e:
    print('Error:', e)
    import traceback
    traceback.print_exc()