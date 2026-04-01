from propifai.models import PropifaiProperty

total = PropifaiProperty.objects.count()
active = PropifaiProperty.objects.filter(is_active=True).count()
draft = PropifaiProperty.objects.filter(is_draft=True).count()
available_status = PropifaiProperty.objects.filter(availability_status='available').count()
active_not_draft = PropifaiProperty.objects.filter(is_active=True, is_draft=False).count()
active_and_available = PropifaiProperty.objects.filter(is_active=True, availability_status='available').count()

print('Total:', total)
print('is_active=True:', active)
print('is_draft=True:', draft)
print('availability_status="available":', available_status)
print('is_active=True AND is_draft=False:', active_not_draft)
print('is_active=True AND availability_status="available":', active_and_available)

# Contar por combinación de is_active y is_draft
from django.db.models import Q
print('\nDesglose:')
print('active & draft:', PropifaiProperty.objects.filter(is_active=True, is_draft=True).count())
print('active & not draft:', PropifaiProperty.objects.filter(is_active=True, is_draft=False).count())
print('not active & draft:', PropifaiProperty.objects.filter(is_active=False, is_draft=True).count())
print('not active & not draft:', PropifaiProperty.objects.filter(is_active=False, is_draft=False).count())