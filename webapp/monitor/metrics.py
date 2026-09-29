"""Metricas de negocio leidas de ``dbpropify_be`` (solo lectura).

Todas las metricas aceptan un ambito (``area_id`` y/o ``rol_id``) para que el
dashboard se pueda acotar por area y por rol. ``rol_id`` manda sobre ``area_id``:
es el filtro mas especifico.

Cada funcion devuelve datos ya listos para pintar: nada de logica en el template.
"""
from __future__ import annotations

from datetime import date, timedelta

from .db import filas

# `date_joined` es datetimeoffset y el driver ODBC no lo lee directo, asi que se
# convierte a texto en la propia consulta. 23 = 'YYYY-MM-DD'. El alias ``u`` es el
# de la tabla [user] en ``ambito()``.
DIA = 'CONVERT(varchar(10), u.date_joined, 23)'
MES = 'CONVERT(varchar(7), u.date_joined, 23)'

MESES_CORTOS = ('ene', 'feb', 'mar', 'abr', 'may', 'jun',
                'jul', 'ago', 'sep', 'oct', 'nov', 'dic')

# Centinela para filtrar los usuarios que no tienen ningun rol asignado.
SIN_AREA = 'sin'

# Estado de publicacion que cuenta como "publico una propiedad".
ESTADO_DISPONIBLE = 3  # property_status.id de 'Disponible'

# Quien dio de alta la propiedad es quien la publico.
_PUBLICO_DISPONIBLE = (
    'EXISTS (SELECT 1 FROM [property] p '
    f'WHERE p.created_by_id = u.id AND p.property_status_id = {ESTADO_DISPONIBLE})'
)

# Condiciones de cada etapa del embudo. Lista blanca: el nombre del grupo llega
# desde la URL, asi que la consulta nunca se arma con texto del cliente.
FILTROS = {
    'registrados': '1 = 1',
    'email_ok': 'u.email_verified = 1',
    'ingresaron': 'u.last_login IS NOT NULL',
    'publicaron': _PUBLICO_DISPONIBLE,
    'con_crm': 'u.has_crm_access = 1',
    'sin_ingresar': 'u.last_login IS NULL',
    'sin_verificar': 'u.email_verified = 0',
}


# ═══════════════════════════════════════════════════════════════════════════
# Ambito: area y rol
# ═══════════════════════════════════════════════════════════════════════════

def ambito(area_id=None, rol_id=None):
    """Devuelve ``(FROM, condiciones, parametros)`` para acotar por area o rol.

    ``area_id`` puede ser el centinela ``SIN_AREA`` para los usuarios sin rol.
    """
    desde = 'FROM [user] u LEFT JOIN [role] r ON r.id = u.role_id'
    condiciones, parametros = [], []
    if rol_id:
        condiciones.append('u.role_id = %s')
        parametros.append(int(rol_id))
    elif area_id == SIN_AREA:
        condiciones.append('u.role_id IS NULL')
    elif area_id:
        condiciones.append('r.area_id = %s')
        parametros.append(int(area_id))
    return desde, condiciones, parametros


def _where(condiciones, extra=()):
    """Arma el WHERE uniendo las condiciones del ambito con las propias."""
    todas = [*condiciones, *[c for c in extra if c]]
    return ('WHERE ' + ' AND '.join(todas)) if todas else ''


def areas() -> list[dict]:
    """Todas las areas con su cantidad de usuarios."""
    return [{'id': r[0], 'nombre': r[1] or '', 'usuarios': int(r[2] or 0)}
            for r in filas("""
                SELECT a.id, a.name, COUNT(u.id)
                FROM [area] a
                LEFT JOIN [role] r ON r.area_id = a.id
                LEFT JOIN [user] u ON u.role_id = r.id
                GROUP BY a.id, a.name
                ORDER BY a.name
            """)]


def roles_de(area_id) -> list[dict]:
    """Roles de un area con su cantidad de usuarios."""
    return [{'id': r[0], 'nombre': r[1] or '', 'usuarios': int(r[2] or 0)}
            for r in filas("""
                SELECT r.id, r.name, COUNT(u.id)
                FROM [role] r
                LEFT JOIN [user] u ON u.role_id = r.id
                WHERE r.area_id = %s
                GROUP BY r.id, r.name
                ORDER BY r.name
            """, [int(area_id)])]


def sin_rol() -> int:
    """Usuarios que no tienen ningun rol asignado."""
    return int(filas('SELECT COUNT(*) FROM [user] WHERE role_id IS NULL')[0][0] or 0)


def total_usuarios() -> int:
    return int(filas('SELECT COUNT(*) FROM [user]')[0][0] or 0)


# ═══════════════════════════════════════════════════════════════════════════
# Metricas
# ═══════════════════════════════════════════════════════════════════════════

def _uno(sql, parametros=None):
    resultado = filas(sql, parametros)
    return resultado[0] if resultado else None


def resumen_usuarios(area_id=None, rol_id=None) -> dict:
    """Totales y embudo: registrados -> activos -> verificados -> ingresaron -> CRM."""
    desde, condiciones, parametros = ambito(area_id, rol_id)
    fila = _uno(f"""
        SELECT COUNT(*)                                            AS total,
               SUM(CASE WHEN u.is_active = 1 THEN 1 ELSE 0 END)      AS activos,
               SUM(CASE WHEN u.email_verified = 1 THEN 1 ELSE 0 END) AS email_ok,
               SUM(CASE WHEN u.phone_verified = 1 THEN 1 ELSE 0 END) AS telefono_ok,
               SUM(CASE WHEN u.last_login IS NOT NULL THEN 1 ELSE 0 END) AS ingresaron,
               SUM(CASE WHEN u.has_crm_access = 1 THEN 1 ELSE 0 END) AS con_crm,
               SUM(CASE WHEN u.is_staff = 1 THEN 1 ELSE 0 END)       AS staff
        {desde} {_where(condiciones)}
    """, parametros)
    if not fila:
        return {}
    claves = ('total', 'activos', 'email_ok', 'telefono_ok', 'ingresaron', 'con_crm', 'staff')
    datos = {k: int(v or 0) for k, v in zip(claves, fila)}
    # Va aparte: necesita un JOIN contra [property], que inflaria los demas sumandos.
    datos['publicaron'] = publicaron_disponible(area_id, rol_id)
    return datos


def publicaron_disponible(area_id=None, rol_id=None) -> int:
    """Usuarios que dieron de alta al menos una propiedad en estado Disponible."""
    _, condiciones, parametros = ambito(area_id, rol_id)
    fila = _uno(f"""
        SELECT COUNT(DISTINCT u.id)
        FROM [user] u
        JOIN [property] p ON p.created_by_id = u.id
                         AND p.property_status_id = {ESTADO_DISPONIBLE}
        LEFT JOIN [role] r ON r.id = u.role_id
        {_where(condiciones)}
    """, parametros)
    return int((fila or [0])[0] or 0)


def registros_por_dia(dias: int = 60, area_id=None, rol_id=None) -> list[dict]:
    """Registros por dia de los ultimos ``dias``, rellenando los dias sin altas."""
    desde, condiciones, parametros = ambito(area_id, rol_id)
    limite = (date.today() - timedelta(days=dias - 1)).isoformat()
    crudos = {str(d): int(n) for d, n in filas(f"""
        SELECT {DIA} AS dia, COUNT(*) AS total
        {desde} {_where(condiciones, [f'{DIA} >= %s'])}
        GROUP BY {DIA}
    """, [*parametros, limite])}
    return [{'dia': (date.today() - timedelta(days=i)).isoformat(),
             'total': crudos.get((date.today() - timedelta(days=i)).isoformat(), 0)}
            for i in range(dias - 1, -1, -1)]


def registros_por_mes(meses: int = 12, area_id=None, rol_id=None) -> list[dict]:
    """Altas por mes de los ultimos ``meses``, rellenando los meses sin altas."""
    desde, condiciones, parametros = ambito(area_id, rol_id)
    hoy = date.today()
    primero = date(hoy.year, hoy.month, 1)
    for _ in range(meses - 1):
        primero = (primero - timedelta(days=1)).replace(day=1)
    crudos = {str(m): int(n) for m, n in filas(f"""
        SELECT {MES} AS mes, COUNT(*) AS total
        {desde} {_where(condiciones, [f'{DIA} >= %s'])}
        GROUP BY {MES}
    """, [*parametros, primero.isoformat()])}
    serie, cursor = [], primero
    for _ in range(meses):
        serie.append({'mes': cursor.strftime('%Y-%m'), 'total': crudos.get(cursor.strftime('%Y-%m'), 0)})
        cursor = (cursor + timedelta(days=32)).replace(day=1)
    return serie


def por_estado(area_id=None, rol_id=None) -> list[dict]:
    """Reparto por el campo ``status``."""
    desde, condiciones, parametros = ambito(area_id, rol_id)
    return [{'estado': str(estado or '(vacio)'), 'total': int(n)}
            for estado, n in filas(f"""
                SELECT u.status, COUNT(*) {desde} {_where(condiciones)}
                GROUP BY u.status ORDER BY COUNT(*) DESC
            """, parametros)]


def ultimos_registros(limite: int = 15, area_id=None, rol_id=None) -> list[dict]:
    """Ultimas altas, para ver el detalle reciente."""
    desde, condiciones, parametros = ambito(area_id, rol_id)
    return [
        {'dia': str(d), 'usuario': u or '', 'email': e or '', 'estado': s or '',
         'nombre': n or '', 'apellido': a2 or '',
         'activo': bool(a), 'verificado': bool(v)}
        for d, u, e, s, a, v, n, a2 in filas(f"""
            SELECT TOP {int(limite)} {DIA} AS dia, u.username, u.email, u.status,
                   u.is_active, u.email_verified, u.first_name, u.last_name
            {desde} {_where(condiciones)}
            ORDER BY u.date_joined DESC
        """, parametros)
    ]


def usuarios_de(grupo: str, limite: int = 300, area_id=None, rol_id=None) -> list[dict]:
    """Los usuarios que caen en cada etapa del embudo, dentro del ambito."""
    condicion = FILTROS.get(grupo)
    if condicion is None:
        raise ValueError(f'Grupo desconocido: {grupo}')
    desde, condiciones, parametros = ambito(area_id, rol_id)
    return [
        {
            'usuario': u or '', 'email': e or '',
            'nombre': f'{n or ""} {a or ""}'.strip(),
            'estado': s or '', 'activo': bool(act), 'verificado': bool(ver),
            'rol': rol or '', 'area': ar or '',
            'ingreso': str(ult)[:16] if ult else None,
            'dia': str(alta) if alta else '',
        }
        for u, e, n, a, s, act, ver, ult, alta, rol, ar in filas(f"""
            SELECT TOP {int(limite)} u.username, u.email, u.first_name, u.last_name,
                   u.status, u.is_active, u.email_verified,
                   CONVERT(varchar(19), u.last_login, 120), {DIA},
                   r.name, a.name
            {desde}
            LEFT JOIN [area] a ON a.id = r.area_id
            {_where(condiciones, [condicion])}
            ORDER BY u.date_joined DESC
        """, parametros)
    ]


def pulso(area_id=None, rol_id=None) -> dict:
    """Resumen corto para las tarjetas de arriba."""
    desde, condiciones, parametros = ambito(area_id, rol_id)
    hoy = date.today().isoformat()
    ayer = (date.today() - timedelta(days=1)).isoformat()
    fila = _uno(f"""
        SELECT SUM(CASE WHEN {DIA} = %s THEN 1 ELSE 0 END),
               SUM(CASE WHEN {DIA} = %s THEN 1 ELSE 0 END),
               SUM(CASE WHEN {DIA} >= %s THEN 1 ELSE 0 END)
        {desde} {_where(condiciones)}
    """, [hoy, ayer, (date.today() - timedelta(days=6)).isoformat(), *parametros])
    hoy_n, ayer_n, semana_n = (int(v or 0) for v in (fila or (0, 0, 0)))
    return {'hoy': hoy_n, 'ayer': ayer_n, 'semana': semana_n}


def eje_de_dias(serie: list[dict], cada: int = 1) -> dict:
    """Marcas del eje X para la serie diaria: numero de dia y franja de mes.

    Por defecto marca TODOS los dias. Devuelve posiciones ya en porcentaje
    porque el template no puede hacer aritmetica: ``izq`` es el borde izquierdo
    y ``ancho`` el ancho, ambos en %.
    """
    total = max(len(serie), 1)
    ticks, meses = [], []
    for i, punto in enumerate(serie):
        anio, mes, dia = (int(x) for x in punto['dia'].split('-'))
        etiqueta = f'{MESES_CORTOS[mes - 1]} {str(anio)[2:]}'
        if not meses or meses[-1]['etiqueta'] != etiqueta:
            meses.append({'etiqueta': etiqueta, 'desde': i, 'dias': 1})
        else:
            meses[-1]['dias'] += 1
        if dia % cada == 0 or i == total - 1:
            ticks.append({'izq': round((i + 0.5) * 100 / total, 3), 'texto': str(dia)})
    for franja in meses:
        franja['izq'] = round(franja['desde'] * 100 / total, 3)
        franja['ancho'] = round(franja['dias'] * 100 / total, 3)
    # Con marcas separadas (cada > 1) se evita que las dos ultimas se peguen.
    if cada > 1 and len(ticks) > 1 and ticks[-1]['izq'] - ticks[-2]['izq'] < 4:
        ticks.pop(-2)
    return {'ticks': ticks, 'meses': meses}
