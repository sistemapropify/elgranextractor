"""Read labeled construction years from the listing, excluding other cards."""
import re

from bs4 import BeautifulSoup
from .normalization import plain


_LABEL = r'ano\s+(?:de\s+)?(?:construccion|edificacion)'
_FEATURE = re.compile(r'^' + _LABEL + r'\s*[:=\-]?\s*(18\d{2}|19\d{2}|20\d{2})\s*$')
_OTHER_LISTINGS = re.compile(r'recommend|related|similar|sugerid|snippet|posting-card', re.I)


def construction_features_from_html(html):
    soup = BeautifulSoup(html or '', 'html.parser')
    years = set()
    for node in soup.find_all(string=re.compile(r'construcci[oó]n|edificaci[oó]n', re.I)):
        if any(parent.name in ('script', 'style', 'template') or _OTHER_LISTINGS.search(
                ' '.join(parent.get('class', [])) + ' ' + str(parent.get('id', '')))
               for parent in node.parents):
            continue
        # The label and value can be sibling spans. Read only their small
        # feature container; never join an entire page or another listing.
        parent = node.parent
        for _ in range(4):
            if parent is None:
                break
            text = plain(parent.get_text(' ', strip=True))
            if len(text) > 140:
                break
            match = _FEATURE.fullmatch(text)
            if match:
                years.add(int(match[1]))
                break
            parent = parent.parent
    return sorted(years)
