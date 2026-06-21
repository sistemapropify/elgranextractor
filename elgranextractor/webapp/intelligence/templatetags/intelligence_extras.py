from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Accede a un diccionario por clave variable en templates Django.
    
    Uso: {{ doc.field_values|get_item:field_name }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)
