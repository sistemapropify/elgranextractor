from django import template

register = template.Library()

@register.filter
def split(value, delimiter=','):
    """Split a string by delimiter and return list."""
    if not value:
        return []
    return [v.strip() for v in str(value).split(delimiter)]

@register.filter
def first(value):
    """Return first element of a list."""
    if value and isinstance(value, (list, tuple)):
        return value[0] if len(value) > 0 else ''
    return value


@register.filter(name="getattr")
def get_attribute(value, attribute):
    """Obtiene de forma segura un atributo dinámico para tablas configurables."""
    if value is None or not attribute:
        return ""
    return getattr(value, str(attribute), "")
