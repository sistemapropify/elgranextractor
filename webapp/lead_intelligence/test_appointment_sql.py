"""Execute the CRM SELECT against a disposable SQL Server schema."""
from unittest import skipUnless
from unittest.mock import patch

from django.db import connection
from django.test import TransactionTestCase

from .visit_resolution import apply_visit_resolutions, load_visit_resolutions, resolve_visits_for_leads


@skipUnless(connection.vendor == 'microsoft', 'Requires isolated SQL Server')
class AppointmentSQLTests(TransactionTestCase):
    databases = {'default'}

    def setUp(self):
        self.assertTrue(connection.settings_dict['NAME'].startswith('test_'))
        with connection.cursor() as cursor:
            cursor.execute('CREATE TABLE dbo.event_type (id int PRIMARY KEY, name nvarchar(100))')
            cursor.execute('CREATE TABLE dbo.contact (id int PRIMARY KEY, first_name nvarchar(100), last_name nvarchar(100), business_name nvarchar(100), phone nvarchar(50))')
            cursor.execute('CREATE TABLE dbo.lead (id int PRIMARY KEY, contact_id int, date_entry datetime2, created_at datetime2)')
            cursor.execute('CREATE TABLE dbo.lead_properties (lead_id int, property_id int)')
            cursor.execute('CREATE TABLE dbo.[event] (id int PRIMARY KEY, lead_id int, contact_id int, property_id int, created_at datetime2, start_time datetime2, event_type_id int)')
            cursor.execute("INSERT INTO dbo.event_type VALUES (1,N'Visita'),(2,N'Captación'),(3,N'Captacion'),(4,N'Otro')")
            cursor.execute("INSERT INTO dbo.contact VALUES (1,N'Ana',N'Perez',NULL,'999123456')")
            cursor.execute("INSERT INTO dbo.lead VALUES (10,1,'2026-08-01','2026-08-01')")
            cursor.execute('INSERT INTO dbo.lead_properties VALUES (10,100)')
            cursor.execute("INSERT INTO dbo.[event] VALUES (1,10,1,100,'2026-08-05','2026-08-10',1),(2,10,1,100,'2026-08-03','2026-08-08',2),(3,NULL,1,100,'2026-08-04','2026-08-09',3),(4,10,1,100,'2026-08-02','2026-08-07',4)")
        self.crm = patch('lead_intelligence.visit_resolution.connections', {'propifai': connection})
        self.crm.start()

    def tearDown(self):
        self.crm.stop()
        with connection.cursor() as cursor:
            for table in ('event', 'lead_properties', 'lead', 'contact', 'event_type'):
                cursor.execute(f'DROP TABLE dbo.[{table}]')

    def test_sql_types_and_confidence_keep_visits_separate(self):
        rows = load_visit_resolutions()
        self.assertEqual({row['event_id']: row['event_kind'] for row in rows}, {1: 'visit', 2: 'capture', 3: 'capture'})
        inferred = next(row for row in rows if row['event_id'] == 3)
        self.assertEqual(inferred['resolved_lead_id'], 10)
        self.assertEqual(inferred['resolution_status'], 'confirmed')
        visits = resolve_visits_for_leads([10], persist=False)
        self.assertEqual([row['event_id'] for row in visits], [1])

    def test_first_dates_and_audit_persist_without_writing_crm_events(self):
        from .models import LeadEventResolution
        row = apply_visit_resolutions([{'id': 10}], persist=True)[0]
        self.assertEqual(row['first_capture_at'].day, 3)
        self.assertEqual(row['first_visit_at'].day, 5)
        self.assertEqual(row['first_appointment_at'], row['first_capture_at'])
        self.assertEqual(LeadEventResolution.objects.count(), 3)
        self.assertEqual({r.evidence['event_kind'] for r in LeadEventResolution.objects.all()}, {'visit', 'capture'})
        with connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM dbo.[event]')
            self.assertEqual(cursor.fetchone()[0], 4)
