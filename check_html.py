#!/usr/bin/env python3
import urllib.request

url = 'http://127.0.0.1:8000/market-analysis/heatmap/'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
response = urllib.request.urlopen(req)
html = response.read().decode('utf-8')

# Buscar líneas clave
lines = html.split('\n')
for i, line in enumerate(lines):
    if 'google' in line.lower() or 'heatmap' in line.lower() or 'script' in line.lower():
        print(f"{i+1}: {line.strip()[:100]}")