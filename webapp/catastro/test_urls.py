from django.urls import include,path
from django.http import HttpResponse

def empty(request):
    return HttpResponse('test placeholder')

urlpatterns = [path('catastro/',include('catastro.urls'))]
urlpatterns += [path(name+'/',empty,name=name) for name in ['login','logout','register']]
urlpatterns += [path('analisis-crm/',include(([path(name+'/',empty,name=name) for name in ['remarketing_campaigns','remarketing_deliveries','remarketing','dashboard','mobile_updates']],'analisis_crm'),namespace='analisis_crm'))]
urlpatterns += [path('prospects/',include(([path('logout/',empty,name='logout')],'prospects'),namespace='prospects'))]
