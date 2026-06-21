import urllib.request
r = urllib.request.urlopen('http://127.0.0.1:8000/matching/calendar/?view=week&year=2026&month=5&day=18', timeout=15)
h = r.read().decode('utf-8')
idx = h.find('const VIEW_MODE')
end = h.find('</script>', idx)
block = h[idx:end]
lines = block.split('\n')
for i, line in enumerate(lines):
    if '📊' in line:
        print(f'Line {i+1}: {line.strip()}')
