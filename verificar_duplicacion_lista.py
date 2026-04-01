#!/usr/bin/env python
"""
Verificar duplicación de leads en la lista de últimos 100 leads.
"""
import sys
import os

sys.path.append('webapp')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

try:
    import django
    django.setup()
    
    from analisis_crm.models import Lead
    from django.db.models import Count
    
    print("=== VERIFICACIÓN DE DUPLICACIÓN EN LISTA ===")
    
    # Obtener últimos 100 leads como lo hace la vista
    recent_leads = Lead.objects.all().order_by('-date_entry', '-created_at')[:100]
    
    print(f"Total en lista: {recent_leads.count()} leads")
    
    # Verificar duplicados por diferentes criterios
    print("\n1. Duplicados por teléfono:")
    phone_counts = {}
    for lead in recent_leads:
        phone = lead.phone
        if phone:
            phone_counts[phone] = phone_counts.get(phone, 0) + 1
    
    duplicate_phones = {phone: count for phone, count in phone_counts.items() if count > 1}
    print(f"   Teléfonos duplicados: {len(duplicate_phones)}")
    for phone, count in list(duplicate_phones.items())[:5]:
        print(f"   - {phone}: {count} veces")
    
    print("\n2. Duplicados por email:")
    email_counts = {}
    for lead in recent_leads:
        email = lead.email
        if email:
            email_counts[email] = email_counts.get(email, 0) + 1
    
    duplicate_emails = {email: count for email, count in email_counts.items() if count > 1}
    print(f"   Emails duplicados: {len(duplicate_emails)}")
    for email, count in list(duplicate_emails.items())[:5]:
        print(f"   - {email}: {count} veces")
    
    print("\n3. Duplicados por nombre y teléfono:")
    name_phone_counts = {}
    for lead in recent_leads:
        key = f"{lead.full_name}|{lead.phone}"
        name_phone_counts[key] = name_phone_counts.get(key, 0) + 1
    
    duplicate_name_phone = {key: count for key, count in name_phone_counts.items() if count > 1}
    print(f"   Nombre+teléfono duplicados: {len(duplicate_name_phone)}")
    for key, count in list(duplicate_name_phone.items())[:5]:
        name, phone = key.split('|')
        print(f"   - {name} ({phone}): {count} veces")
    
    print("\n4. Leads con misma fecha y hora exacta:")
    datetime_counts = {}
    for lead in recent_leads:
        if lead.date_entry:
            dt_key = lead.date_entry.strftime('%Y-%m-%d %H:%M')
            datetime_counts[dt_key] = datetime_counts.get(dt_key, 0) + 1
    
    duplicate_datetime = {dt: count for dt, count in datetime_counts.items() if count > 1}
    print(f"   Fechas-horas duplicadas: {len(duplicate_datetime)}")
    for dt, count in list(duplicate_datetime.items())[:5]:
        print(f"   - {dt}: {count} leads")
    
    # Calcular porcentaje de duplicación
    total_duplicates = sum(count - 1 for count in phone_counts.values() if count > 1)
    total_leads = recent_leads.count()
    duplicate_percentage = (total_duplicates / total_leads) * 100 if total_leads > 0 else 0
    
    print(f"\n5. RESUMEN DE DUPLICACIÓN:")
    print(f"   Total leads en lista: {total_leads}")
    print(f"   Leads duplicados (por teléfono): {total_duplicates}")
    print(f"   Porcentaje de duplicación: {duplicate_percentage:.1f}%")
    
    if duplicate_percentage > 20:
        print("   ⚠️ ALTA DUPLICACIÓN: Más del 20% de leads están duplicados")
    
    print("\n6. RECOMENDACIONES:")
    print("   - Considerar agregar validación para evitar insertar leads duplicados")
    print("   - Implementar deduplicación en la vista o en el proceso de importación")
    print("   - Mostrar advertencia en el dashboard sobre datos duplicados")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()