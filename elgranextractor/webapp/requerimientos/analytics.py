"""
Módulo de análisis temporal para requerimientos inmobiliarios.
Contiene funciones para calcular métricas, tendencias y generar insights.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Tuple, Optional, Any
from django.db.models import (
    Count, Avg, Max, Min, Sum, Q, F, Value,
    Case, When, IntegerField, DecimalField,
    ExpressionWrapper, Func, Subquery, OuterRef
)
from django.db.models.functions import TruncMonth, TruncYear, TruncDay, ExtractMonth, ExtractYear
from django.utils import timezone
from .models import Requerimiento, CondicionChoices, TipoPropiedadChoices, TernarioChoices
import statistics
import math


# ─────────────────────────────────────────────
#  FUNCIONES DE AGRUPACIÓN TEMPORAL
# ─────────────────────────────────────────────

def obtener_requerimientos_por_mes(fecha_inicio=None, fecha_fin=None, filtros=None):
    """
    Retorna un QuerySet agrupado por mes con conteo de requerimientos.
    
    Args:
        fecha_inicio (date): Fecha inicial para filtrar
        fecha_fin (date): Fecha final para filtrar
        filtros (dict): Diccionario con filtros adicionales (condicion, tipo_propiedad, etc.)
    
    Returns:
        QuerySet annotado con 'mes', 'total', y otras métricas
    """
    queryset = Requerimiento.objects.all()
    
    # Aplicar filtros de fecha
    if fecha_inicio:
        queryset = queryset.filter(fecha__gte=fecha_inicio)
    if fecha_fin:
        queryset = queryset.filter(fecha__lte=fecha_fin)
    
    # Aplicar filtros adicionales
    if filtros:
        if 'condicion' in filtros and filtros['condicion']:
            queryset = queryset.filter(condicion=filtros['condicion'])
        if 'tipo_propiedad' in filtros and filtros['tipo_propiedad']:
            queryset = queryset.filter(tipo_propiedad=filtros['tipo_propiedad'])
        if 'distrito' in filtros and filtros['distrito']:
            queryset = queryset.filter(distritos__icontains=filtros['distrito'])
        if 'fuente' in filtros and filtros['fuente']:
            queryset = queryset.filter(fuente=filtros['fuente'])
    
    # Agrupar por mes
    return queryset.annotate(
        mes=TruncMonth('fecha')
    ).values('mes').annotate(
        total=Count('id'),
        compra=Count('id', filter=Q(condicion=CondicionChoices.COMPRA)),
        alquiler=Count('id', filter=Q(condicion=CondicionChoices.ALQUILER)),
        departamento=Count('id', filter=Q(tipo_propiedad=TipoPropiedadChoices.DEPARTAMENTO)),
        casa=Count('id', filter=Q(tipo_propiedad=TipoPropiedadChoices.CASA)),
        terreno=Count('id', filter=Q(tipo_propiedad=TipoPropiedadChoices.TERRENO)),
        presupuesto_promedio=Avg('presupuesto_monto'),
        presupuesto_mediano=Value(None, output_field=DecimalField()),  # Se calculará después
        cochera_si=Count('id', filter=Q(cochera=TernarioChoices.SI)),
        ascensor_si=Count('id', filter=Q(ascensor=TernarioChoices.SI)),
        amueblado_si=Count('id', filter=Q(amueblado=TernarioChoices.SI)),
    ).order_by('mes')


def obtener_requerimientos_por_dia(fecha_inicio=None, fecha_fin=None, filtros=None):
    """
    Retorna un QuerySet agrupado por día con conteo de requerimientos.
    
    Args:
        fecha_inicio (date): Fecha inicial para filtrar
        fecha_fin (date): Fecha final para filtrar
        filtros (dict): Diccionario con filtros adicionales (condicion, tipo_propiedad, etc.)
    
    Returns:
        QuerySet annotado con 'dia', 'total', y otras métricas
    """
    queryset = Requerimiento.objects.all()
    
    # Aplicar filtros de fecha
    if fecha_inicio:
        queryset = queryset.filter(fecha__gte=fecha_inicio)
    if fecha_fin:
        queryset = queryset.filter(fecha__lte=fecha_fin)
    
    # Aplicar filtros adicionales
    if filtros:
        if 'condicion' in filtros and filtros['condicion']:
            queryset = queryset.filter(condicion=filtros['condicion'])
        if 'tipo_propiedad' in filtros and filtros['tipo_propiedad']:
            queryset = queryset.filter(tipo_propiedad=filtros['tipo_propiedad'])
        if 'distrito' in filtros and filtros['distrito']:
            queryset = queryset.filter(distritos__icontains=filtros['distrito'])
        if 'fuente' in filtros and filtros['fuente']:
            queryset = queryset.filter(fuente=filtros['fuente'])
    
    # Agrupar por día
    return queryset.annotate(
        dia=TruncDay('fecha')
    ).values('dia').annotate(
        total=Count('id'),
        compra=Count('id', filter=Q(condicion=CondicionChoices.COMPRA)),
        alquiler=Count('id', filter=Q(condicion=CondicionChoices.ALQUILER)),
        departamento=Count('id', filter=Q(tipo_propiedad=TipoPropiedadChoices.DEPARTAMENTO)),
        casa=Count('id', filter=Q(tipo_propiedad=TipoPropiedadChoices.CASA)),
        terreno=Count('id', filter=Q(tipo_propiedad=TipoPropiedadChoices.TERRENO)),
        presupuesto_promedio=Avg('presupuesto_monto'),
        cochera_si=Count('id', filter=Q(cochera=TernarioChoices.SI)),
        ascensor_si=Count('id', filter=Q(ascensor=TernarioChoices.SI)),
        amueblado_si=Count('id', filter=Q(amueblado=TernarioChoices.SI)),
    ).order_by('dia')


def calcular_crecimiento_porcentual(valores: List[float]) -> List[Optional[float]]:
    """
    Calcula el crecimiento porcentual mes a mes.
    
    Args:
        valores: Lista de valores (ej: totales por mes)
    
    Returns:
        Lista de porcentajes de crecimiento (primer elemento es None)
    """
    if len(valores) < 2:
        return [None] * len(valores)
    
    crecimiento = [None]
    for i in range(1, len(valores)):
        if valores[i-1] and valores[i-1] != 0:
            crecimiento.append(((valores[i] - valores[i-1]) / valores[i-1]) * 100)
        else:
            crecimiento.append(None)
    return crecimiento


def obtener_distritos_por_mes(fecha_inicio=None, fecha_fin=None, top_n=10):
    """
    Retorna un diccionario con la cantidad de requerimientos por distrito por mes.
    
    Returns:
        dict: {
            'distritos': ['Cayma', 'Yanahuara', ...],
            'meses': ['2025-01', '2025-02', ...],
            'data': matriz[distrito][mes] = cantidad
        }
    """
    queryset = Requerimiento.objects.all()
    if fecha_inicio:
        queryset = queryset.filter(fecha__gte=fecha_inicio)
    if fecha_fin:
        queryset = queryset.filter(fecha__lte=fecha_fin)
    
    # Obtener todos los distritos únicos
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT DISTINCT TRIM(value) as distrito
            FROM requerimiento
            CROSS APPLY STRING_SPLIT(distritos, ',')
            WHERE TRIM(value) != ''
            ORDER BY distrito
        """)
        distritos = [row[0] for row in cursor.fetchall()]
    
    # Limitar a top_n distritos más frecuentes
    if len(distritos) > top_n:
        # Contar frecuencia total por distrito
        distrito_counts = {}
        for d in distritos:
            count = Requerimiento.objects.filter(distritos__icontains=d).count()
            distrito_counts[d] = count
        distritos = sorted(distrito_counts.keys(), key=lambda x: distrito_counts[x], reverse=True)[:top_n]
    
    # Obtener meses únicos
    meses_qs = queryset.dates('fecha', 'month').order_by('fecha')
    meses = [m.strftime('%Y-%m') for m in meses_qs]
    
    # Construir matriz de datos
    data = {distrito: {mes: 0 for mes in meses} for distrito in distritos}
    
    # Consulta optimizada para contar por distrito y mes
    for mes in meses:
        year, month = map(int, mes.split('-'))
        mes_start = datetime(year, month, 1)
        if month == 12:
            mes_end = datetime(year+1, 1, 1) - timedelta(days=1)
        else:
            mes_end = datetime(year, month+1, 1) - timedelta(days=1)
        
        for distrito in distritos:
            count = queryset.filter(
                fecha__range=[mes_start, mes_end],
                distritos__icontains=distrito
            ).count()
            data[distrito][mes] = count
    
    return {
        'distritos': distritos,
        'meses': meses,
        'data': data
    }


def obtener_tipos_propiedad_por_mes(fecha_inicio=None, fecha_fin=None):
    """
    Retorna la evolución de tipos de propiedad por mes.
    
    Returns:
        dict: {
            'meses': ['2025-01', ...],
            'tipos': ['departamento', 'casa', 'terreno', ...],
            'data': {tipo: [counts por mes]}
        }
    """
    queryset = Requerimiento.objects.all()
    if fecha_inicio:
        queryset = queryset.filter(fecha__gte=fecha_inicio)
    if fecha_fin:
        queryset = queryset.filter(fecha__lte=fecha_fin)
    
    tipos = [TipoPropiedadChoices.DEPARTAMENTO, TipoPropiedadChoices.CASA, 
             TipoPropiedadChoices.TERRENO, TipoPropiedadChoices.OFICINA,
             TipoPropiedadChoices.LOCAL_COMERCIAL]
    
    meses_qs = queryset.dates('fecha', 'month').order_by('fecha')
    meses = [m.strftime('%Y-%m') for m in meses_qs]
    
    data = {tipo: [0] * len(meses) for tipo in tipos}
    
    for i, mes in enumerate(meses):
        year, month = map(int, mes.split('-'))
        mes_start = datetime(year, month, 1)
        if month == 12:
            mes_end = datetime(year+1, 1, 1) - timedelta(days=1)
        else:
            mes_end = datetime(year, month+1, 1) - timedelta(days=1)
        
        for tipo in tipos:
            count = queryset.filter(
                fecha__range=[mes_start, mes_end],
                tipo_propiedad=tipo
            ).count()
            data[tipo][i] = count
    
    return {
        'meses': meses,
        'tipos': tipos,
        'data': data
    }


def obtener_presupuesto_por_mes(fecha_inicio=None, fecha_fin=None):
    """
    Retorna estadísticas de presupuesto por mes.
    
    Returns:
        dict: {
            'meses': ['2025-01', ...],
            'promedio': [valores],
            'mediano': [valores],
            'max': [valores],
            'min': [valores],
            'rangos': {rango: [counts]}
        }
    """
    queryset = Requerimiento.objects.filter(presupuesto_monto__isnull=False)
    if fecha_inicio:
        queryset = queryset.filter(fecha__gte=fecha_inicio)
    if fecha_fin:
        queryset = queryset.filter(fecha__lte=fecha_fin)
    
    meses_qs = queryset.dates('fecha', 'month').order_by('fecha')
    meses = [m.strftime('%Y-%m') for m in meses_qs]
    
    # Inicializar listas
    promedio = []
    mediano = []
    maximo = []
    minimo = []
    
    # Rangos de presupuesto
    rangos = {
        '<100k': [0] * len(meses),
        '100k-150k': [0] * len(meses),
        '150k-200k': [0] * len(meses),
        '200k-300k': [0] * len(meses),
        '300k-500k': [0] * len(meses),
        '>500k': [0] * len(meses)
    }
    
    for i, mes in enumerate(meses):
        year, month = map(int, mes.split('-'))
        mes_start = datetime(year, month, 1)
        if month == 12:
            mes_end = datetime(year+1, 1, 1) - timedelta(days=1)
        else:
            mes_end = datetime(year, month+1, 1) - timedelta(days=1)
        
        mes_queryset = queryset.filter(fecha__range=[mes_start, mes_end])
        
        # Calcular estadísticas
        stats = mes_queryset.aggregate(
            avg=Avg('presupuesto_monto'),
            max=Max('presupuesto_monto'),
            min=Min('presupuesto_monto')
        )
        
        promedio.append(float(stats['avg']) if stats['avg'] else 0)
        maximo.append(float(stats['max']) if stats['max'] else 0)
        minimo.append(float(stats['min']) if stats['min'] else 0)
        
        # Calcular mediana (aproximada)
        valores = list(mes_queryset.values_list('presupuesto_monto', flat=True))
        if valores:
            sorted_vals = sorted(valores)
            mediana = float(sorted_vals[len(sorted_vals) // 2])
            mediano.append(mediana)
        else:
            mediano.append(0)
        
        # Contar por rangos
        for req in mes_queryset:
            monto = req.presupuesto_monto
            if monto < 100000:
                rangos['<100k'][i] += 1
            elif monto < 150000:
                rangos['100k-150k'][i] += 1
            elif monto < 200000:
                rangos['150k-200k'][i] += 1
            elif monto < 300000:
                rangos['200k-300k'][i] += 1
            elif monto < 500000:
                rangos['300k-500k'][i] += 1
            else:
                rangos['>500k'][i] += 1
    
    return {
        'meses': meses,
        'promedio': promedio,
        'mediano': mediano,
        'max': maximo,
        'min': minimo,
        'rangos': rangos
    }


def obtener_caracteristicas_demandadas(fecha_inicio=None, fecha_fin=None):
    """
    Retorna las características más demandadas por mes.
    
    Returns:
        dict: {
            'meses': ['2025-01', ...],
            'caracteristicas': ['cochera', 'ascensor', 'amueblado', 'habitaciones_3+', 'banos_2+'],
            'data': {caracteristica: [counts]}
        }
    """
    queryset = Requerimiento.objects.all()
    if fecha_inicio:
        queryset = queryset.filter(fecha__gte=fecha_inicio)
    if fecha_fin:
        queryset = queryset.filter(fecha__lte=fecha_fin)
    
    meses_qs = queryset.dates('fecha', 'month').order_by('fecha')
    meses = [m.strftime('%Y-%m') for m in meses_qs]
    
    caracteristicas = ['cochera_si', 'ascensor_si', 'amueblado_si', 'habitaciones_3+', 'banos_2+']
    data = {car: [0] * len(meses) for car in caracteristicas}
    
    for i, mes in enumerate(meses):
        year, month = map(int, mes.split('-'))
        mes_start = datetime(year, month, 1)
        if month == 12:
            mes_end = datetime(year+1, 1, 1) - timedelta(days=1)
        else:
            mes_end = datetime(year, month+1, 1) - timedelta(days=1)
        
        mes_queryset = queryset.filter(fecha__range=[mes_start, mes_end])
        
        # Contar características
        data['cochera_si'][i] = mes_queryset.filter(cochera=TernarioChoices.SI).count()
        data['ascensor_si'][i] = mes_queryset.filter(ascensor=TernarioChoices.SI).count()
        data['amueblado_si'][i] = mes_queryset.filter(amueblado=TernarioChoices.SI).count()
        data['habitaciones_3+'][i] = mes_queryset.filter(habitaciones__gte=3).count()
        data['banos_2+'][i] = mes_queryset.filter(banos__gte=2).count()
    
    return {
        'meses': meses,
        'caracteristicas': caracteristicas,
        'data': data
    }


# ─────────────────────────────────────────────
#  FUNCIONES DE ANÁLISIS Y DETECCIÓN
# ─────────────────────────────────────────────

def detectar_picos_y_valles(valores: List[float], umbral_desviacion=1.5):
    """
    Detecta picos (valores atípicamente altos) y valles (atípicamente bajos).
    
    Args:
        valores: Lista de valores numéricos
        umbral_desviacion: Número de desviaciones estándar para considerar atípico
    
    Returns:
        tuple: (picos_indices, valles_indices)
    """
    if len(valores) < 3:
        return [], []
    
    # Filtrar valores None
    valores_validos = [v for v in valores if v is not None]
    if len(valores_validos) < 3:
        return [], []
    
    media = statistics.mean(valores_validos)
    desviacion = statistics.stdev(valores_validos) if len(valores_validos) > 1 else 0
    
    picos = []
    valles = []
    
    for i, val in enumerate(valores):
        if val is None:
            continue
        if desviacion > 0:
            z_score = (val - media) / desviacion
            if z_score > umbral_desviacion:
                picos.append(i)
            elif z_score < -umbral_desviacion:
                valles.append(i)
    
    return picos, valles


def calcular_tendencia(valores: List[float]) -> str:
    """
    Determina si la tendencia es ascendente, descendente o estable.
    
    Returns:
        '📈 subiendo', '📉 bajando', '➡️ estable'
    """
    if len(valores) < 2:
        return '➡️ estable'
    
    # Usar regresión lineal simple
    x = list(range(len(valores)))
    y = [v for v in valores if v is not None]
    x_filtered = [x[i] for i, v in enumerate(valores) if v is not None]
    
    if len(y) < 2:
        return '➡️ estable'
    
    n = len(y)
    sum_x = sum(x_filtered)
    sum_y = sum(y)
    sum_xy = sum(xi * yi for xi, yi in zip(x_filtered, y))
    sum_x2 = sum(xi * xi for xi in x_filtered)
    
    # Pendiente de la regresión
    try:
        pendiente = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
    except ZeroDivisionError:
        pendiente = 0
    
    # Determinar tendencia basada en pendiente
    if pendiente > 0.1:
        return '📈 subiendo'
    elif pendiente < -0.1:
        return '📉 bajando'
    else:
        return '➡️ estable'


# ═════════════════════════════════════════════
#  FUNCIONES DE QUALITY SCORE
# ═════════════════════════════════════════════

def _get_calidad_config():
    """Retorna la configuración activa de calidad o los defaults."""
    from .models import ConfiguracionCalidad
    return ConfiguracionCalidad.get_config()


def calcular_completitud(req, config=None) -> float:
    """
    Calcula el score de completitud (0-100) basado en campos llenos.
    
    Los campos se dividen en 3 tiers con diferentes pesos:
    - Críticos (3 pts c/u): distritos, tipo_propiedad, condicion
    - Importantes (2 pts c/u): presupuesto_monto, habitaciones, urbanizacion, agente
    - Complementarios (1 pt c/u): presupuesto_moneda, presupuesto_forma_pago, banos,
      area_m2, zona, cochera, ascensor, amueblado
    
    Returns:
        float: Score de 0 a 100
    """
    if config is None:
        config = _get_calidad_config()
    
    tiers = config.get('completitud_tiers', {})
    max_puntos = 0
    puntos_obtenidos = 0
    
    for tier_key, tier_data in tiers.items():
        puntos_por_campo = tier_data.get('puntos_por_campo', 1)
        campos = tier_data.get('campos', [])
        for campo in campos:
            max_puntos += puntos_por_campo
            valor = getattr(req, campo, None)
            if valor is not None and valor != '' and valor != []:
                # Para campos ternarios (None/'' no cuenta, 'no' sí cuenta)
                if campo in ('cochera', 'ascensor', 'amueblado'):
                    if valor and str(valor) != '':
                        puntos_obtenidos += puntos_por_campo
                elif campo == 'distritos':
                    # distritos es un campo separado por comas
                    if isinstance(valor, str) and valor.strip():
                        puntos_obtenidos += puntos_por_campo
                else:
                    puntos_obtenidos += puntos_por_campo
    
    if max_puntos == 0:
        return 0.0
    
    return round((puntos_obtenidos / max_puntos) * 100, 1)


def calcular_especificidad(req, config=None) -> float:
    """
    Calcula el score de especificidad geográfica (0-100).
    
    Niveles:
    - Muy específico (100): zona + urbanización + al menos 1 distrito
    - Específico (75): urbanización o zona
    - Preciso (50): exactamente 1 distrito
    - Amplio (30): múltiples distritos
    - Sin ubicación (0): sin distritos
    
    Returns:
        float: Score de 0 a 100
    """
    if config is None:
        config = _get_calidad_config()
    
    niveles = config.get('especificidad_niveles', [])
    
    # Obtener datos del requerimiento
    distritos_raw = getattr(req, 'distritos', '') or ''
    distritos = [d.strip() for d in distritos_raw.split(',') if d.strip()]
    num_distritos = len(distritos)
    
    urbanizacion = getattr(req, 'urbanizacion', '') or ''
    zona = getattr(req, 'zona', '') or ''
    tiene_urbanizacion = bool(urbanizacion.strip())
    tiene_zona = bool(zona.strip())
    
    # Determinar nivel
    if tiene_zona and tiene_urbanizacion and num_distritos >= 1:
        # Muy específico
        for nivel in niveles:
            if nivel.get('requisito') == 'zona+urbanizacion+1distrito':
                return float(nivel.get('score', 100))
    
    if tiene_urbanizacion or tiene_zona:
        # Específico
        for nivel in niveles:
            if nivel.get('requisito') == 'urbanizacion_o_zona':
                return float(nivel.get('score', 75))
    
    if num_distritos == 1:
        # Preciso
        for nivel in niveles:
            if nivel.get('requisito') == '1_distrito':
                return float(nivel.get('score', 50))
    
    if num_distritos > 1:
        # Amplio
        for nivel in niveles:
            if nivel.get('requisito') == 'multi_distrito':
                return float(nivel.get('score', 30))
    
    # Sin ubicación
    for nivel in niveles:
        if nivel.get('requisito') == 'sin_distrito':
            return float(nivel.get('score', 0))
    
    return 0.0


def calcular_presupuesto_score(req, config=None) -> float:
    """
    Calcula el score de presupuesto (0-100) basado en percentiles.
    
    Compara el presupuesto del requerimiento contra todos los requerimientos
    con presupuesto para determinar si está en percentil alto (menos calidad
    porque es menos realista) o bajo (más calidad).
    
    Usa P25, P50, P75 para categorizar.
    
    Returns:
        float: Score de 0 a 100
    """
    if config is None:
        config = _get_calidad_config()
    
    monto = getattr(req, 'presupuesto_monto', None)
    if monto is None or monto == '' or monto == 0:
        return float(config.get('presupuesto_percentiles', {}).get('sin_presupuesto_score', 0))
    
    try:
        monto = float(monto)
    except (TypeError, ValueError):
        return float(config.get('presupuesto_percentiles', {}).get('sin_presupuesto_score', 0))
    
    if monto <= 0:
        return float(config.get('presupuesto_percentiles', {}).get('sin_presupuesto_score', 0))
    
    percentiles_config = config.get('presupuesto_percentiles', {})
    min_muestras = percentiles_config.get('min_muestras', 10)
    
    # Obtener todos los montos de presupuesto (misma moneda)
    moneda = getattr(req, 'presupuesto_moneda', None)
    montos_qs = Requerimiento.objects.filter(
        presupuesto_monto__isnull=False,
        presupuesto_monto__gt=0
    )
    if moneda:
        montos_qs = montos_qs.filter(presupuesto_moneda=moneda)
    
    montos = list(montos_qs.values_list('presupuesto_monto', flat=True))
    montos = [float(m) for m in montos if m is not None]
    
    if len(montos) < min_muestras:
        # Pocas muestras, score neutral
        return 50.0
    
    montos.sort()
    n = len(montos)
    
    # Calcular percentiles
    def percentile(data, p):
        k = (len(data) - 1) * p / 100
        f = int(k)
        c = k - f
        if f + 1 < len(data):
            return data[f] * (1 - c) + data[f + 1] * c
        return data[-1]
    
    p25 = percentile(montos, 25)
    p50 = percentile(montos, 50)
    p75 = percentile(montos, 75)
    
    # Asignar score según percentil del monto
    if monto <= p25:
        return float(percentiles_config.get('p25_score', 100))
    elif monto <= p50:
        return float(percentiles_config.get('p25_a_p50_score', 80))
    elif monto <= p75:
        return float(percentiles_config.get('p50_a_p75_score', 50))
    else:
        return float(percentiles_config.get('mayor_p75_score', 20))


def calcular_antiguedad_score(req, config=None) -> float:
    """
    Calcula el score de antigüedad (0-100) basado en días desde creación.
    
    Mientras más reciente, mejor score.
    
    Rangos por defecto:
    - ≤7 días: 100
    - ≤30 días: 75
    - ≤90 días: 40
    - ≤180 días: 15
    - >180 días: 5
    
    Returns:
        float: Score de 0 a 100
    """
    if config is None:
        config = _get_calidad_config()
    
    fecha = getattr(req, 'fecha', None) or getattr(req, 'creado_en', None)
    if fecha is None:
        return 0.0
    
    if isinstance(fecha, str):
        from datetime import datetime
        try:
            fecha = datetime.strptime(fecha, '%Y-%m-%d')
        except ValueError:
            return 0.0
    
    # Normalizar: si fecha es datetime, convertir a date para evitar TypeError
    if hasattr(fecha, 'date'):
        fecha = fecha.date() if hasattr(fecha, 'time') else fecha
    dias = (timezone.now().date() - fecha).days if not isinstance(fecha, str) else 0
    if dias < 0:
        dias = 0
    
    rangos = config.get('antiguedad_rangos', [])
    for rango in sorted(rangos, key=lambda r: r.get('dias_max', 999999)):
        if dias <= rango.get('dias_max', 0):
            return float(rango.get('score', 0))
    
    return 0.0


def calcular_quality_score(req, config=None) -> Dict[str, Any]:
    """
    Calcula el Quality Score completo de un requerimiento.
    
    Evalúa 4 dimensiones:
    1. Completitud (35%) - qué tan llenos están los campos
    2. Especificidad (25%) - qué tan específico es geográficamente
    3. Presupuesto (25%) - qué tan realista es el presupuesto
    4. Antigüedad (15%) - qué tan reciente es
    
    Args:
        req: Instancia de Requerimiento
        config: Dict de configuración (opcional, usa defaults si no se provee)
    
    Returns:
        dict: {
            'score': float (0-100),
            'nivel': str (Excelente/Bueno/Regular/Malo),
            'dimensiones': {
                'completitud': float,
                'especificidad': float,
                'presupuesto': float,
                'antiguedad': float
            },
            'pesos': {
                'completitud': int,
                'especificidad': int,
                'presupuesto': int,
                'antiguedad': int
            }
        }
    """
    if config is None:
        config = _get_calidad_config()
    
    pesos = config.get('pesos_dimensiones', {})
    peso_completitud = pesos.get('completitud', 35)
    peso_especificidad = pesos.get('especificidad', 25)
    peso_presupuesto = pesos.get('presupuesto', 25)
    peso_antiguedad = pesos.get('antiguedad', 15)
    
    # Calcular cada dimensión
    score_completitud = calcular_completitud(req, config)
    score_especificidad = calcular_especificidad(req, config)
    score_presupuesto = calcular_presupuesto_score(req, config)
    score_antiguedad = calcular_antiguedad_score(req, config)
    
    # Ponderar
    peso_total = peso_completitud + peso_especificidad + peso_presupuesto + peso_antiguedad
    if peso_total == 0:
        peso_total = 100  # fallback
    
    score_final = (
        (score_completitud * peso_completitud) +
        (score_especificidad * peso_especificidad) +
        (score_presupuesto * peso_presupuesto) +
        (score_antiguedad * peso_antiguedad)
    ) / peso_total
    
    score_final = round(score_final, 1)
    
    # Determinar nivel textual
    if score_final >= 80:
        nivel = 'Excelente'
    elif score_final >= 60:
        nivel = 'Bueno'
    elif score_final >= 40:
        nivel = 'Regular'
    else:
        nivel = 'Malo'
    
    return {
        'score': score_final,
        'nivel': nivel,
        'dimensiones': {
            'completitud': score_completitud,
            'especificidad': score_especificidad,
            'presupuesto': score_presupuesto,
            'antiguedad': score_antiguedad,
        },
        'pesos': {
            'completitud': peso_completitud,
            'especificidad': peso_especificidad,
            'presupuesto': peso_presupuesto,
            'antiguedad': peso_antiguedad,
        },
    }