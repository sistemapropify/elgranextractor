"""
Auditor de extracción — Detecta errores silenciosos en la extracción de requerimientos.

Filosofía:
    "Si el campo quedó vacío en BD pero el texto original lo menciona → registra un ERROR"

Esto permite que errores que antes pasaban desapercibidos (DeepSeek no extrajo el área
pero el texto decía "160m2") ahora se registren como LogEntry con nivel WARNING,
y aparezcan automáticamente en /intelligence/errors/.

Puntos de inyección:
    Punto A: deepseek_transformer.py → _mapear_campos() (justo antes de return data)
    Punto B: tasks.py → después de Requerimiento.objects.create()

Uso:
    from .auditor_extraccion import auditar_campos_mapeados, auditar_campos_finales
"""

import re
import logging
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

# ─── CÓDIGOS DE ERROR ────────────────────────────────────────────────────────
# Se usan como nivel en LogEntry para que el template /intelligence/errors/
# los muestre automáticamente (ya filtra por nivel WARNING/ERROR).

SILENT_FAIL_AREA = 'SILENT_FAIL_AREA'
SILENT_FAIL_HABITACIONES = 'SILENT_FAIL_HABITACIONES'
SILENT_FAIL_BANOS = 'SILENT_FAIL_BANOS'
SILENT_FAIL_PRECIO = 'SILENT_FAIL_PRECIO'
SILENT_FAIL_DISTRITOS = 'SILENT_FAIL_DISTRITOS'
SILENT_FAIL_TIPO = 'SILENT_FAIL_TIPO'
SILENT_FAIL_CONDICION = 'SILENT_FAIL_CONDICION'

# ─── PATRONES DE DETECCIÓN ───────────────────────────────────────────────────
# Buscan menciones en el texto original para determinar si un campo DEBERÍA
# tener valor pero quedó vacío.

# Área: "160m2", "200 m²", "80 metros cuadrados", "120 mts"
_PATRON_AREA = re.compile(
    r'(\d{1,4}(?:[.,]\d{1,4})?)\s*(?:m[²2]|metros?\s*cuadrados?|metros|mts?|mt)\b',
    re.IGNORECASE | re.UNICODE
)

# Habitaciones: "3 dormitorios", "2 cuartos", "4 hab", "1 dorm"
_PATRON_HABITACIONES = re.compile(
    r'(\d+)\s*(?:dormitorios?|cuartos?|habitaciones?|hab\.?\s*|dorm\.?\s*|hab\b|dorm\b)',
    re.IGNORECASE | re.UNICODE
)

# Baños: "2 baños", "1 baño", "2 ss.hh.", "2 ba"
_PATRON_BANOS = re.compile(
    r'(\d+)\s*(?:baños?|banos?|bañ\.?\s*|ba\.?\s*|ss\.?\s*hh\.?|servicios\s+higiénicos)',
    re.IGNORECASE | re.UNICODE
)

# Precio: "S/ 2000", "S/. 2000", "USD 500", "$ 500", "2000 soles", "alquiler 1500"
_PATRON_PRECIO = re.compile(
    r'(?:S/?[./]?\s*|USD\s*|\$\s*|dólares?\s*|soles?\s*)?'
    r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,4})?)\s*'
    r'(?:S/?[./]?\s*|USD\s*|\$\s*|dólares?|soles?)?',
    re.IGNORECASE | re.UNICODE
)

# Distritos conocidos de Arequipa
_DISTRITOS_AREQUIPA = [
    'cayma', 'yanahuara', 'cercado', 'miraflores', 'jose luis bustamante',
    'bustamante', 'sachaca', 'cerro colorado', 'mariano melgar', 'paucarpata',
    'socabaya', 'jacobo hunter', 'tiabaya', 'sabandia', 'characato',
    'mollebaya', 'quebrada', 'umacollo', 'vallecito', 'selva alegre',
    'san luis', 'alameda', 'lara', 'tambo', 'deán valdivia', 'san camilo',
]

# Tipo de propiedad
_PATRON_TIPO = re.compile(
    r'\b(casa|departamento|terreno|lote|oficina|local\s*comercial|duplex|'
    r'penthouse|suite|habitación|habitacion|cuarto|piso|chalet|villa|'
    r'edificio|flat|estudio|loft)\b',
    re.IGNORECASE | re.UNICODE
)

# Condición (compra/venta/alquiler)
_PATRON_CONDICION = re.compile(
    r'\b(vendo|vende|venta|compro|compra|busco|necesito|requiero|alquilo|'
    r'alquila|alquiler|rento|renta|arriendo|arrienda|leasing|'
    r'busco\s+(?:un\s+)?(?:terreno|casa|departamento|local)|'
    r'necesito\s+(?:un\s+)?(?:terreno|casa|departamento|local)|'
    r'requiero\s+(?:un\s+)?(?:terreno|casa|departamento|local))\b',
    re.IGNORECASE | re.UNICODE
)


# ─── FUNCIÓN PRINCIPAL: PUNTO A ──────────────────────────────────────────────

def auditar_campos_mapeados(
    data: Dict[str, Any],
    texto: str,
    extractor_log_id: Optional[int] = None,
    mensaje_idx: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Auditoría PUNTO A — Se llama dentro de _mapear_campos(), justo antes de
    'return data'.

    Detecta campos que quedaron vacíos en el dict 'data' pero que el texto
    original sí menciona. Si hay extractor_log_id, crea LogEntry.

    Retorna el mismo 'data' sin modificar (es solo una función de auditoría).
    """
    from ..models import LogEntry

    errores = []

    # --- area_m2 ---
    if not data.get('area_m2'):
        match = _PATRON_AREA.search(texto)
        if match:
            valor_encontrado = match.group(1)
            errores.append({
                'codigo': SILENT_FAIL_AREA,
                'campo': 'area_m2',
                'valor_encontrado': valor_encontrado,
                'contexto': match.group(0),
            })

    # --- habitaciones ---
    if not data.get('habitaciones'):
        match = _PATRON_HABITACIONES.search(texto)
        if match:
            valor_encontrado = match.group(1)
            errores.append({
                'codigo': SILENT_FAIL_HABITACIONES,
                'campo': 'habitaciones',
                'valor_encontrado': valor_encontrado,
                'contexto': match.group(0),
            })

    # --- banos ---
    if not data.get('banos'):
        match = _PATRON_BANOS.search(texto)
        if match:
            valor_encontrado = match.group(1)
            errores.append({
                'codigo': SILENT_FAIL_BANOS,
                'campo': 'banos',
                'valor_encontrado': valor_encontrado,
                'contexto': match.group(0),
            })

    # --- distritos ---
    if not data.get('distritos'):
        distritos_encontrados = []
        for distrito in _DISTRITOS_AREQUIPA:
            if distrito in texto.lower():
                distritos_encontrados.append(distrito)
        if distritos_encontrados:
            errores.append({
                'codigo': SILENT_FAIL_DISTRITOS,
                'campo': 'distritos',
                'valor_encontrado': ', '.join(distritos_encontrados),
                'contexto': ', '.join(distritos_encontrados),
            })

    # --- tipo_propiedad ---
    if not data.get('tipo_propiedad') or data.get('tipo_propiedad') == 'no_especificado':
        match = _PATRON_TIPO.search(texto)
        if match:
            errores.append({
                'codigo': SILENT_FAIL_TIPO,
                'campo': 'tipo_propiedad',
                'valor_encontrado': match.group(1),
                'contexto': match.group(0),
            })

    # --- condicion ---
    if not data.get('condicion') or data.get('condicion') == 'no_especificado':
        match = _PATRON_CONDICION.search(texto)
        if match:
            errores.append({
                'codigo': SILENT_FAIL_CONDICION,
                'campo': 'condicion',
                'valor_encontrado': match.group(1),
                'contexto': match.group(0),
            })

    # --- presupuesto_monto ---
    if not data.get('presupuesto_monto'):
        match = _PATRON_PRECIO.search(texto)
        if match:
            errores.append({
                'codigo': SILENT_FAIL_PRECIO,
                'campo': 'presupuesto_monto',
                'valor_encontrado': match.group(1),
                'contexto': match.group(0),
            })

    # ─── Registrar en LogEntry si hay extractor_log_id ──────────────────────
    if errores and extractor_log_id:
        try:
            LogEntry.objects.create(
                extractor_log_id=extractor_log_id,
                nivel='WARNING',
                mensaje=(
                    f"[AUDITOR] {len(errores)} campo(s) con posible error silencioso "
                    f"(texto menciona valor pero extracción quedó vacía)"
                ),
                detalles={
                    'tipo': 'AUDITORIA_SILENT_FAIL',
                    'punto': 'A_mapear_campos',
                    'mensaje_idx': mensaje_idx,
                    'errores': errores,
                    'texto_preview': texto[:200],
                },
            )
            logger.warning(
                f"[AUDITOR PUNTO A] {len(errores)} error(es) silencioso(s) detectado(s): "
                f"{[e['codigo'] for e in errores]}"
            )
        except Exception as e:
            logger.error(f"[AUDITOR] Error al crear LogEntry: {e}")

    return data


# ─── FUNCIÓN PRINCIPAL: PUNTO B ──────────────────────────────────────────────

def auditar_campos_finales(
    requerimiento_id: int,
    datos_extraidos: Dict[str, Any],
    texto_original: str,
    extractor_log_id: int,
    mensaje_idx: Optional[int] = None,
) -> None:
    """
    Auditoría PUNTO B — Se llama DESPUÉS de Requerimiento.objects.create().

    Verifica que los campos que quedaron en la BD coincidan con lo que el
    texto original menciona. Si hay discrepancias, crea LogEntry.

    A diferencia de Punto A, aquí ya tenemos el Requerimiento creado, así que
    podemos verificar el valor REAL en BD.
    """
    from ..models import LogEntry, Requerimiento

    try:
        req = Requerimiento.objects.get(pk=requerimiento_id)
    except Requerimiento.DoesNotExist:
        logger.error(f"[AUDITOR PUNTO B] Requerimiento {requerimiento_id} no encontrado")
        return

    errores = []

    # --- area_m2 ---
    if not req.area_m2:
        match = _PATRON_AREA.search(texto_original)
        if match:
            errores.append({
                'codigo': SILENT_FAIL_AREA,
                'campo': 'area_m2',
                'valor_en_bd': None,
                'valor_en_texto': match.group(1),
                'contexto': match.group(0),
            })

    # --- habitaciones ---
    if not req.habitaciones:
        match = _PATRON_HABITACIONES.search(texto_original)
        if match:
            errores.append({
                'codigo': SILENT_FAIL_HABITACIONES,
                'campo': 'habitaciones',
                'valor_en_bd': None,
                'valor_en_texto': match.group(1),
                'contexto': match.group(0),
            })

    # --- banos ---
    if not req.banos:
        match = _PATRON_BANOS.search(texto_original)
        if match:
            errores.append({
                'codigo': SILENT_FAIL_BANOS,
                'campo': 'banos',
                'valor_en_bd': None,
                'valor_en_texto': match.group(1),
                'contexto': match.group(0),
            })

    # --- distritos ---
    if not req.distritos:
        distritos_encontrados = []
        for distrito in _DISTRITOS_AREQUIPA:
            if distrito in texto_original.lower():
                distritos_encontrados.append(distrito)
        if distritos_encontrados:
            errores.append({
                'codigo': SILENT_FAIL_DISTRITOS,
                'campo': 'distritos',
                'valor_en_bd': None,
                'valor_en_texto': ', '.join(distritos_encontrados),
                'contexto': ', '.join(distritos_encontrados),
            })

    # --- tipo_propiedad ---
    if not req.tipo_propiedad or req.tipo_propiedad == 'no_especificado':
        match = _PATRON_TIPO.search(texto_original)
        if match:
            errores.append({
                'codigo': SILENT_FAIL_TIPO,
                'campo': 'tipo_propiedad',
                'valor_en_bd': req.tipo_propiedad,
                'valor_en_texto': match.group(1),
                'contexto': match.group(0),
            })

    # --- condicion ---
    if not req.condicion or req.condicion == 'no_especificado':
        match = _PATRON_CONDICION.search(texto_original)
        if match:
            errores.append({
                'codigo': SILENT_FAIL_CONDICION,
                'campo': 'condicion',
                'valor_en_bd': req.condicion,
                'valor_en_texto': match.group(1),
                'contexto': match.group(0),
            })

    # --- presupuesto_monto ---
    if not req.presupuesto_monto:
        match = _PATRON_PRECIO.search(texto_original)
        if match:
            errores.append({
                'codigo': SILENT_FAIL_PRECIO,
                'campo': 'presupuesto_monto',
                'valor_en_bd': None,
                'valor_en_texto': match.group(1),
                'contexto': match.group(0),
            })

    # ─── Registrar en LogEntry ──────────────────────────────────────────────
    if errores:
        try:
            LogEntry.objects.create(
                extractor_log_id=extractor_log_id,
                nivel='WARNING',
                mensaje=(
                    f"[AUDITOR] Requerimiento #{requerimiento_id}: "
                    f"{len(errores)} campo(s) con posible error silencioso "
                    f"(texto menciona valor pero BD quedó vacío)"
                ),
                detalles={
                    'tipo': 'AUDITORIA_SILENT_FAIL',
                    'punto': 'B_post_create',
                    'requerimiento_id': requerimiento_id,
                    'mensaje_idx': mensaje_idx,
                    'errores': errores,
                    'texto_preview': texto_original[:200],
                },
            )
            logger.warning(
                f"[AUDITOR PUNTO B] Requerimiento #{requerimiento_id}: "
                f"{len(errores)} error(es) silencioso(s): "
                f"{[e['codigo'] for e in errores]}"
            )
        except Exception as e:
            logger.error(f"[AUDITOR] Error al crear LogEntry: {e}")
