import os; os.environ['DJANGO_SETTINGS_MODULE']='settings'; os.environ.setdefault('PROPIFAI_DB_NAME','dbpropify_be')
import django; django.setup()
from intelligence.models import User, UserIntelligenceProfile
u = User.objects.filter(username='mercurio2008').first()
if u:
    u.level = 5
    u.save()
    print(f'User {u.username}: level={u.level}')
    profile = UserIntelligenceProfile.objects.filter(user=u).first()
    if profile:
        profile.level = 5
        profile.save()
        print(f'Profile actualizado: level={profile.level}')
    else:
        print(f'Creando perfil...')
        profile = UserIntelligenceProfile.objects.create(user=u, level=5)
        print(f'Profile creado: level={profile.level}')
else:
    print('Usuario no encontrado')
