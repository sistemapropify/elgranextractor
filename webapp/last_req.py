from requerimientos.models import Requerimiento
r = Requerimiento.objects.order_by('-id').first()
print('ID:', r.id)
print('Requerimiento:', r.requerimiento[:100] if r.requerimiento else 'VACIO')
print('Longitud:', len(r.requerimiento) if r.requerimiento else 0)