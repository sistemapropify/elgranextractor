import urllib.request, re, html
r = urllib.request.urlopen('http://127.0.0.1:8000/matching/calendar/?view=week&year=2026&month=5&day=18', timeout=15)
h = r.read().decode('utf-8')
# Extract the extra_js block content
m = re.search(r'{% block extra_js %}(.*?){% endblock %}', h, re.DOTALL)
if m:
    js = m.group(1)
else:
    # Fallback: find script after VIEW_MODE
    idx = h.find('const VIEW_MODE')
    end = h.find('</script>', idx)
    js = h[idx:end]

# Write to a temp file for inspection
with open('_rendered_script.js', 'w', encoding='utf-8') as f:
    f.write(js)
print(f'Script length: {len(js)}')
print(f'First 100 chars: {js[:100]}')
