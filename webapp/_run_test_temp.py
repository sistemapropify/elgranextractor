import sys  
sys.stdout.reconfigure(encoding='utf-8')  
from django.test import RequestFactory  
from django.contrib.messages.storage.fallback import FallbackStorage  
from intelligence.views import skills_dashboard_view  
from intelligence.models import User, Role  
  
role, _ = Role.objects.get_or_create(name='Admin', defaults={'allowed_levels': [1,2,3,4,5]})  
user = User.objects.filter(role=role).first()  
if not user:  
    user = User.objects.create(phone='999999999', role=role, username='test_admin')  
  
factory = RequestFactory()  
request = factory.get('/skills/dashboard/')  
request.current_user = user  
setattr(request, 'session', 'session')  
messages = FallbackStorage(request)  
setattr(request, '_messages', messages)  
  
response = skills_dashboard_view(request)  
content = response.content.decode('utf-8')  
print(f'Status: {response.status_code}')  
print(f'Length: {len(content)}')  
print(f'sd-wrapper: {"sd-wrapper" in content}')  
print(f'CSS: {"skills_dashboard.css" in content}')  
print(f'JS: {"skills_dashboard.js" in content}')  
print(f'Chart.js: {"Chart.js" in content}')  
print(f'KPIs: {"sd-kpi" in content}')  
print(f'Table: {"sd-table" in content}')  
