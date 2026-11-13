from django.urls import path

from . import views

app_name = 'external_agents'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('cierres/', views.cierres, name='cierres'),
    path('cierres/cobrar/', views.collection_add, name='collection_add'),
    path('cierres/pagar/', views.payment_add, name='payment_add'),
    path('pagos-servicios/', views.service_payments, name='service_payments'),
    path('pagos-servicios/nuevo/', views.service_payment_add, name='service_payment_add'),
    path('pagos-servicios/<int:pk>/pagar/', views.service_payment_pay, name='service_payment_pay'),
    path('gastos-fijos/', views.fixed_expenses, name='fixed_expenses'),
    path('gastos-marketing/', views.marketing_expenses, name='marketing_expenses'),
    path('gastos/<str:kind>/nuevo/', views.operating_expense_add, name='operating_expense_add'),
    path('gastos/<str:kind>/<int:pk>/pagar/', views.operating_expense_pay, name='operating_expense_pay'),
    path('balance/', views.financial_balance, name='financial_balance'),
    path('planillas/', views.payroll_dashboard, name='payroll_dashboard'),
    path('planillas/trabajadores/nuevo/', views.payroll_employee_add, name='payroll_employee_add'),
    path('planillas/generar/', views.payroll_generate, name='payroll_generate'),
    path('planillas/<int:pk>/editar/', views.payroll_entry_update, name='payroll_entry_update'),
    path('planillas/<int:pk>/pagar/', views.payroll_entry_pay, name='payroll_entry_pay'),
    path('nuevo/', views.agent_create, name='agent_create'),
    path('configuracion/', views.configuration, name='configuration'),
    path(
        'configuracion/tipos/crear/',
        views.document_type_create,
        name='document_type_create',
    ),
    path(
        'configuracion/tipos/<int:pk>/editar/',
        views.document_type_update,
        name='document_type_update',
    ),
    path(
        'configuracion/tipos/<int:pk>/activar/',
        views.document_type_toggle,
        name='document_type_toggle',
    ),
    path('<int:pk>/', views.agent_detail, name='agent_detail'),
    path('<int:pk>/editar/', views.agent_edit, name='agent_edit'),
    path('<int:pk>/estado/', views.agent_toggle_active, name='agent_toggle_active'),
    path('<int:pk>/eliminar/', views.agent_delete, name='agent_delete'),
    path(
        '<int:pk>/adjuntos/',
        views.attachment_upload,
        name='attachment_upload',
    ),
    path(
        '<int:pk>/adjuntos/<int:attachment_pk>/descargar/',
        views.attachment_download,
        name='attachment_download',
    ),
    path(
        '<int:pk>/adjuntos/<int:attachment_pk>/ver/',
        views.attachment_preview,
        name='attachment_preview',
    ),
    path(
        '<int:pk>/adjuntos/<int:attachment_pk>/eliminar/',
        views.attachment_delete,
        name='attachment_delete',
    ),
]
