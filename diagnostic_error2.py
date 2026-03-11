import urllib.request
import urllib.error
import re

url = "http://localhost:8000/market-analysis/heatmap/"

try:
    req = urllib.request.Request(url)
    response = urllib.request.urlopen(req)
    print("Status:", response.status)
except urllib.error.HTTPError as e:
    print("HTTP Error:", e.code)
    content = e.read().decode('utf-8')
    # Buscar el traceback
    start = content.find('<div id="traceback">')
    if start != -1:
        end = content.find('</div>', start)
        traceback_html = content[start:end]
        # Extraer texto limpio
        from html.parser import HTMLParser
        class MyHTMLParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.result = []
            def handle_data(self, data):
                self.result.append(data)
        parser = MyHTMLParser()
        parser.feed(traceback_html)
        traceback_text = ''.join(parser.result)
        print("\n=== TRACEBACK ===")
        print(traceback_text[:2000])
    else:
        # Si no encuentra, mostrar parte del contenido que contiene el error
        error_section = content.find('NameError')
        if error_section != -1:
            print("\n=== ERROR SECTION ===")
            print(content[error_section:error_section+2000])