import urllib.request, re
r = urllib.request.urlopen('http://127.0.0.1:8000/matching/calendar/?view=week&year=2026&month=5&day=29', timeout=15)
html = r.read().decode('utf-8')
# Find the script block with VIEW_MODE
idx = html.find('const VIEW_MODE')
if idx >= 0:
    end = html.find('</script>', idx)
    block = html[idx:end]
    # print line by line
    for i, line in enumerate(block.split('\n')):
        print(f'{i+1}: {line}')
    print(f'\n--- Total lines: {len(block.split(chr(10)))} ---')
else:
    print('VIEW_MODE not found')
