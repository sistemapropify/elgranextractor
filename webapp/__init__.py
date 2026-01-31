"""
Monkey patch simple para corregir el error 'super' object has no attribute 'dicts'
en Django 5.0.6 con Python 3.14.2.
"""
import django.template.context

def patched_copy(self):
    """Versión simple de __copy__ que evita usar super().__copy__()."""
    # Crear nueva instancia sin llamar a __init__ (para RequestContext)
    duplicate = self.__class__.__new__(self.__class__)
    # Copiar todos los atributos existentes
    duplicate.__dict__.update(self.__dict__)
    # Asegurar que dicts sea una copia superficial (lista nueva)
    duplicate.dicts = self.dicts[:]
    return duplicate

# Aplicar el patch
django.template.context.BaseContext.__copy__ = patched_copy

print("Monkey patch simple aplicado a django.template.context.BaseContext.__copy__")