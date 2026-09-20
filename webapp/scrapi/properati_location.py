"""Properati location evidence, independent of browser and database imports."""
import html as html_lib
import re
from html.parser import HTMLParser


def decoded(value):
    return html_lib.unescape(value or '').replace(r'\"', '"').replace(r'\u00f3', 'ó')


def map_object(value):
    """Read the balanced map object, not a fixed window into other listings."""
    text = decoded(value)
    for key in ('mapData', 'adLocationData'):
        match = re.search(r'["\']?\b' + key + r'["\']?\s*:\s*\{', text)
        if not match:
            continue
        start = match.end() - 1
        depth, quote, escaped = 0, None, False
        for i in range(start, len(text)):
            char = text[i]
            if quote:
                if escaped:
                    escaped = False
                elif char == '\\':
                    escaped = True
                elif char == quote:
                    quote = None
            elif char in ('"', "'"):
                quote = char
            elif char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
    return ''


class MapText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.found = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if self.depth:
            if tag == 'div':
                self.depth += 1
        elif attrs.get('id') == 'location-map':
            self.depth = 1
            self.found = True

    def handle_endtag(self, tag):
        if self.depth and tag == 'div':
            self.depth -= 1

    def handle_data(self, data):
        if self.depth:
            self.parts.append(data)


def precision_from_html(value):
    text = decoded(value)
    parser = MapText()
    parser.feed(text)
    visible_text = ' '.join(parser.parts)
    # The advertiser notice takes precedence over map serialization.
    if re.search(r'prefiere\s+no\s+mostrar\s+la\s+direcci[oó]n\s+exacta',
                 visible_text if parser.found else re.sub('<[^>]+>', ' ', text), re.I):
        return 'aproximada'
    block = map_object(text)
    match = re.search(r'["\']?visibility["\']?\s*:\s*["\']([^"\']+)', block, re.I)
    visibility = match[1].lower() if match else ''
    if visibility in ('approximate', 'approx', 'approximated'):
        return 'aproximada'
    if visibility in ('accurate', 'exact', 'exacta'):
        return 'exacta'
    # Both verified Properati fixtures render the location block in server HTML.
    # Require its address as well: a missing/unrendered block is not evidence.
    if parser.found and re.search(r'location-map__location-address-map[^>]*>\s*[^<\s]', text):
        return 'exacta'
    return 'desconocida'
