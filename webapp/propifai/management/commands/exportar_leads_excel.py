import pandas as pd
from django.core.management.base import BaseCommand
from django.db import connections


class Command(BaseCommand):
    help = 'Exporta todos los leads de dbpropify_be a Excel con nombres resueltos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='leads_propify.xlsx',
            help='Nombre del archivo Excel de salida'
        )

    def handle(self, *args, **options):
        output_file = options['output']
        conn = connections['propifai']

        with conn.cursor() as cursor:
            cursor.execute("SELECT id, name FROM lead_status")
            lead_status_map = {row[0]: row[1] for row in cursor.fetchall()}
            self.stdout.write(f'lead_status: {len(lead_status_map)} registros')

            cursor.execute("SELECT id, name FROM canal_lead")
            canal_lead_map = {row[0]: row[1] for row in cursor.fetchall()}
            self.stdout.write(f'canal_lead: {len(canal_lead_map)} registros')

            cursor.execute("SELECT id, username, first_name, last_name FROM [user]")
            user_map = {row[0]: f"{row[2]} {row[3]}".strip() if row[2] or row[3] else row[1] for row in cursor.fetchall()}
            self.stdout.write(f'user: {len(user_map)} registros')

            cursor.execute("SELECT id, name FROM area")
            area_map = {row[0]: row[1] for row in cursor.fetchall()}
            self.stdout.write(f'area: {len(area_map)} registros')

            cursor.execute("SELECT id, name FROM operation_type")
            op_type_map = {row[0]: row[1] for row in cursor.fetchall()}
            self.stdout.write(f'operation_type: {len(op_type_map)} registros')

            cursor.execute("SELECT id, first_name, last_name, phone, email FROM contact")
            contact_map = {}
            for row in cursor.fetchall():
                full = f"{row[1] or ''} {row[2] or ''}".strip()
                contact_map[row[0]] = {'nombre': full or '—', 'telefono': row[3] or '', 'email': row[4] or ''}
            self.stdout.write(f'contact: {len(contact_map)} registros')

            cursor.execute("SELECT id, name FROM meta_campaign")
            campaign_map = {row[0]: row[1] for row in cursor.fetchall()}
            self.stdout.write(f'meta_campaign: {len(campaign_map)} registros')

            cursor.execute("SELECT id, name FROM meta_ad")
            ad_map = {row[0]: row[1] for row in cursor.fetchall()}
            self.stdout.write(f'meta_ad: {len(ad_map)} registros')

            cursor.execute("SELECT lead_id, operationtype_id FROM lead_operation_types")
            lead_ops = {}
            for row in cursor.fetchall():
                lead_ops.setdefault(row[0], []).append(op_type_map.get(row[1], str(row[1])))
            self.stdout.write(f'lead_operation_types: {sum(len(v) for v in lead_ops.values())} registros')

            cursor.execute("SELECT TOP 1 * FROM property")
            prop_cols = [desc[0] for desc in cursor.description]
            name_col = 'title' if 'title' in prop_cols else ('code' if 'code' in prop_cols else prop_cols[1])
            cursor.execute(f"SELECT id, {name_col}, code FROM property")
            property_map = {}
            for row in cursor.fetchall():
                label = row[1] or row[2] or f"Propiedad #{row[0]}"
                property_map[row[0]] = label
            self.stdout.write(f'property: {len(property_map)} registros')

            cursor.execute("SELECT lead_id, property_id FROM lead_properties")
            lead_props = {}
            for row in cursor.fetchall():
                lead_props.setdefault(row[0], []).append(property_map.get(row[1], f"#{row[1]}"))
            self.stdout.write(f'lead_properties: {sum(len(v) for v in lead_props.values())} registros')

            cursor.execute("SELECT * FROM lead ORDER BY id")
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            self.stdout.write(f'lead: {len(rows)} registros')

        data = []
        for row in rows:
            row_dict = dict(zip(columns, row))
            lead_id = row_dict['id']
            r = {
                'ID': lead_id,
                'Nombre de usuario': row_dict.get('username') or '',
                'Fuente': row_dict.get('source') or '',
                'Detalle fuente': row_dict.get('source_detail') or '',
                'Fecha ingreso': row_dict.get('date_entry'),
                'Presupuesto': float(row_dict['budget']) if row_dict.get('budget') is not None else None,
                'Financiamiento': row_dict.get('financing') or '',
                'Score': row_dict.get('score'),
                'Temperatura': row_dict.get('temperature') or '',
                'Timeline': row_dict.get('timeline') or '',
                'Estado': lead_status_map.get(row_dict.get('lead_status_id'), f"#{row_dict.get('lead_status_id')}"),
                'Canal': canal_lead_map.get(row_dict.get('canal_lead_id'), f"#{row_dict.get('canal_lead_id')}"),
                'Área': area_map.get(row_dict.get('area_id'), f"#{row_dict.get('area_id')}"),
                'Asignado a': user_map.get(row_dict.get('assigned_to_id'), f"#{row_dict.get('assigned_to_id')}"),
                'Creado por': user_map.get(row_dict.get('created_by_id'), f"#{row_dict.get('created_by_id')}"),
                'Actualizado por': user_map.get(row_dict.get('updated_by_id'), f"#{row_dict.get('updated_by_id')}"),
                'Contacto nombre': contact_map.get(row_dict.get('contact_id'), {}).get('nombre', ''),
                'Contacto teléfono': contact_map.get(row_dict.get('contact_id'), {}).get('telefono', ''),
                'Contacto email': contact_map.get(row_dict.get('contact_id'), {}).get('email', ''),
                'Tipo de operación': ', '.join(lead_ops.get(lead_id, [])),
                'Propiedades interesado': ', '.join(lead_props.get(lead_id, [])),
                'Notas': row_dict.get('notes') or '',
                'id_chatwoot': row_dict.get('id_chatwoot') or '',
                'Fecha último mensaje': row_dict.get('date_last_message'),
                'Usuario último mensaje': row_dict.get('user_last_message') or '',
                'Último texto mensaje': row_dict.get('last_message_text') or '',
                'Chatwoot inbox': row_dict.get('chatwoot_inbox_id') or '',
                'Chatwoot label': row_dict.get('chatwoot_label') or '',
                'Chatwoot labels': row_dict.get('chatwoot_labels') or '',
                'Mensajes no leídos': row_dict.get('unread_count'),
                'Activo': 'Sí' if row_dict.get('is_active') else 'No',
                'Meta Lead ID': row_dict.get('meta_lead_id') or '',
                'Meta Form ID': row_dict.get('meta_form_id') or '',
                'Campaña Meta': campaign_map.get(row_dict.get('meta_campaign_ref_id'), ''),
                'Anuncio Meta': ad_map.get(row_dict.get('meta_ad_ref_id'), ''),
                'ctwa_clid': row_dict.get('ctwa_clid') or '',
                'Creado en': row_dict.get('created_at'),
                'Actualizado en': row_dict.get('updated_at'),
            }
            data.append(r)

        df = pd.DataFrame(data)
        df.to_excel(output_file, index=False)

        self.stdout.write(self.style.SUCCESS(f'✅ Excel generado: {output_file}'))
        self.stdout.write(self.style.SUCCESS(f'Total leads exportados: {len(df)}'))
