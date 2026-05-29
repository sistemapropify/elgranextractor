import urllib.request
r = urllib.request.urlopen('http://127.0.0.1:8000/matching/calendar/?view=week&year=2026&month=5&day=18', timeout=15)
h = r.read().decode('utf-8')
idx = h.find('const VIEW_MODE')
end = h.find('</script>', idx)
block = h[idx:end]
# Split into lines and find any line with a potential syntax error
for i, line in enumerate(block.split('\n')):
    stripped = line.strip()
    # Find if any string contains unescaped newlines or quotes
    if stripped and not stripped.startswith('//') and not stripped.startswith('/*'):
        # Count quotes
        print(f'{i+1}: {stripped[:200]}')
