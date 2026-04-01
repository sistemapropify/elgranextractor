#!/usr/bin/env python
import pyodbc

def main():
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost;DATABASE=Propifai;Trusted_Connection=yes;')
    cursor = conn.cursor()
    
    # Contar eventos
    cursor.execute('SELECT COUNT(*) FROM events')
    event_count = cursor.fetchone()[0]
    print(f'Total eventos en tabla events: {event_count}')
    
    # Contar eventos con property_id no nulo
    cursor.execute('SELECT COUNT(*) FROM events WHERE property_id IS NOT NULL')
    event_with_property = cursor.fetchone()[0]
    print(f'Eventos con property_id no nulo: {event_with_property}')
    
    # Contar propiedades
    cursor.execute('SELECT COUNT(*) FROM properties')
    property_count = cursor.fetchone()[0]
    print(f'Total propiedades en tabla properties: {property_count}')
    
    # Mostrar algunos eventos con property_id
    cursor.execute('''
        SELECT TOP 10 e.id, e.property_id, e.titulo, e.fecha_evento, p.code 
        FROM events e 
        LEFT JOIN properties p ON e.property_id = p.id 
        WHERE e.property_id IS NOT NULL
        ORDER BY e.fecha_evento DESC
    ''')
    rows = cursor.fetchall()
    print('\nÚltimos 10 eventos con propiedad:')
    for row in rows:
        print(f'  Evento {row.id}: propiedad {row.property_id} ({row.code}) - {row.titulo} - {row.fecha_evento}')
    
    # Mostrar algunas propiedades con conteo de eventos
    cursor.execute('''
        SELECT TOP 10 p.id, p.code, p.real_address, COUNT(e.id) as event_count
        FROM properties p 
        LEFT JOIN events e ON p.id = e.property_id 
        GROUP BY p.id, p.code, p.real_address
        ORDER BY event_count DESC
    ''')
    rows = cursor.fetchall()
    print('\nTop 10 propiedades por cantidad de eventos:')
    for row in rows:
        print(f'  Propiedad {row.code} ({row.id}): {row.event_count} eventos - {row.real_address}')
    
    conn.close()

if __name__ == '__main__':
    main()