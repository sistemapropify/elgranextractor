"""Read property-specific feature sections after the detail URL is validated."""
import asyncio

DETAIL_JS = r"""portal => {
 const selectors = {
  remax: ['.__titlec', '.__text_match'],
  properati: ['.facilities__item', '.facilities__options li'],
  adondevivir: ['#section-icon-features-property li.icon-feature', '.section-icon-features-property li.icon-feature', '.nf-container .item .label', '#section-features-property li'],
  urbania: ['.nf-container .item .label', '#section-icon-features-property li.icon-feature', '#section-features-property li']
 };
 const descriptions = {
  remax: '.__text_match', properati: '#description-text-full, .description .content',
  adondevivir: '#longDescription, #postingDescription, [data-qa="POSTING_DESCRIPTION"]',
  urbania: '#longDescription, #postingDescription, [data-qa="POSTING_DESCRIPTION"]'
 };
 const labels = [];
 for (const selector of selectors[portal] || []) for (const el of document.querySelectorAll(selector)) {
  if (el.closest('[class*="recommend"], [class*="similar"], [data-qa*="RECOMMEND"]')) continue;
  const sibling = el.matches('.__titlec') ? el.nextElementSibling?.textContent || '' : '';
  const checkbox = el.querySelector('input[type="checkbox"]');
  const checked = checkbox ? checkbox.checked : el.getAttribute('aria-checked');
  const state = checked === false || checked === 'false' ? ': No' : '';
  const text = (el.textContent + (sibling ? ': ' + sibling : state)).replace(/\s+/g, ' ').trim();
  if (/cocher|estacionamiento|garaj|garage|parking|ascensor|elevador|elevator/i.test(text) && text.length <= 600 && !labels.includes(text)) labels.push(text);
 }
 const desc = document.querySelector(descriptions[portal] || '.__no_property_description');
 return {features: labels.slice(0,100), description: desc ? desc.textContent.trim().slice(0,30000) : ''};
}"""


async def enrich_building_features(page, raw, portal):
    try:
        detail = await asyncio.wait_for(page.evaluate(DETAIL_JS, portal), timeout=8)
        if isinstance(detail, dict):
            features = detail.get('features')
            if isinstance(features, list):
                raw['_detail_features'] = [text[:600] for text in features[:100] if isinstance(text, str)]
            if isinstance(detail.get('description'), str) and detail['description'].strip():
                raw['_detail_description'] = detail['description'][:30000]
            raw.pop('_building_detail_error', None)
    except Exception as exc:
        # Missing optional attributes must not invalidate an otherwise good ad.
        # Browser navigation itself is still checked by the paged engine.
        raw['_building_detail_error'] = type(exc).__name__
