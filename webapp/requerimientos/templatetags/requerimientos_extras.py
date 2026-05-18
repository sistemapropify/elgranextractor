from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def split(value, separator=','):
    """Divide un string por el separador y retorna una lista."""
    if not value:
        return []
    return [item.strip() for item in value.split(separator) if item.strip()]


@register.filter
def render_tags(value, separator=','):
    """Convierte un string separado por comas en tags HTML (badges)."""
    if not value:
        return mark_safe('<span style="color:#484f58;">—</span>')
    partes = [p.strip() for p in value.split(separator) if p.strip()]
    if not partes:
        return mark_safe('<span style="color:#484f58;">—</span>')
    tags_html = ' '.join(
        '<span class="tag-item">{}</span>'.format(p)
        for p in partes
    )
    return mark_safe('<div class="tags-container">{}</div>'.format(tags_html))
