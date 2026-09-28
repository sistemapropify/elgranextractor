"""Agente de triaje de alertas de calidad.

Revisa una propiedad con alertas y decide si la alerta **es real, es ruido o no
alcanza para decidir**. No decide por el humano: ordena el trabajo para que la
revision manual empiece por lo que importa.

El agente **insiste**: si en el primer intento no alcanza para decidir, vuelve a
analizar con mas contexto antes de rendirse.

    Intento 1  descripcion + campos            -> veredicto
    Intento 2  + datos crudos del scraper      -> busca valores traspuestos u olvidados
    Intento 3  + propiedades comparables       -> para las alertas de valor atipico

Termina cuando logra confianza suficiente o agota ``MAX_INTENTOS``.
"""
from __future__ import annotations

import json
import logging
import re

from .property_quality import DATA_FIELDS, analyze

logger = logging.getLogger(__name__)

MAX_INTENTOS = 3
CONFIANZA_SUFICIENTE = 0.7
REINTENTOS_LLM = 3          # el API devuelve vacio de vez en cuando; se insiste

CAMPOS_TEXTO = ('id', 'fuente', 'id_origen', 'titulo', 'tipo_inmueble', 'tipo_operacion',
                'precio_usd', 'precio_soles', 'area_m2', 'area_terreno', 'area_construida',
                'dormitorios', 'banos', 'estacionamientos', 'distrito', 'descripcion')

_SISTEMA = """Eres un auditor de datos inmobiliarios. Revisas UNA propiedad que quedo marcada
con alertas automaticas y decides si esas alertas son reales o son falsos positivos.

Es falso positivo (ruido) cuando:
- la alerta nace de una mencion incidental ("terreno ideal para casa de campo" no vuelve
  la propiedad una casa)
- es redondeo ("18 m2" frente a 18.37), o un precio por m2 y no el precio total
- el campo esta vacio o en cero, que en estos datos significa "sin dato", no "cero"
- el dato simplemente falta en el anuncio, pero no se contradice

Es alerta real cuando el anuncio afirma un valor y el campo guarda otro distinto para el
mismo dato, o cuando el campo es imposible (un terreno de 1.52 m2 en una casa con piscina),
o esta claramente traspuesto (el area de terreno quedo en el campo de construida).

Responde SOLO con JSON, sin texto alrededor:
{"veredicto":"real|ruido|dudoso","motivo":"una o dos frases",
 "correccion":{"campo":"valor sugerido"},"confianza":0.0}"""


def _campos(propiedad: dict) -> dict:
    return {k: (str(propiedad.get(k)) if propiedad.get(k) is not None else None)
            for k in CAMPOS_TEXTO}


def _preguntar(prompt: str) -> tuple[dict | None, str]:
    """Llama al modelo con reintentos. Devuelve (json, respuesta_cruda)."""
    from intelligence.services.llm import LLMService

    ultimo = ''
    for intento in range(1, REINTENTOS_LLM + 1):
        ok, msg, resp = LLMService._call_deepseek_api(
            messages=[{'role': 'user', 'content': prompt}],
            system_prompt=_SISTEMA,
            max_tokens=1200,
        )
        crudo = (resp or {}).get('content', '') or '' if ok else ''
        if not crudo.strip():
            ultimo = f'respuesta vacia (intento {intento}): {str(msg)[:120]}'
            continue
        coincidencia = re.search(r'\{[\s\S]*\}', crudo)
        if not coincidencia:
            ultimo = f'sin JSON (intento {intento}): {crudo[:120]}'
            continue
        try:
            return json.loads(coincidencia.group()), crudo
        except json.JSONDecodeError as exc:
            ultimo = f'JSON invalido (intento {intento}): {exc}'
    return None, ultimo


def _intento(propiedad: dict, alertas: list[str], extra: str = '') -> tuple[dict | None, str]:
    prompt = 'CAMPOS EXTRAIDOS:\n%s\n\nDESCRIPCION:\n%s\n\nALERTAS AUTOMATICAS:\n%s\n%s' % (
        json.dumps(_campos(propiedad), ensure_ascii=False),
        (propiedad.get('descripcion') or '(vacia)')[:2500],
        '\n'.join('- %s' % a for a in alertas) or '(ninguna)',
        ('\nCONTEXTO ADICIONAL:\n%s' % extra) if extra else '',
    )
    return _preguntar(prompt)


def _comparables(propiedad: dict, limite: int = 8) -> str:
    """Propiedades parecidas, para juzgar las alertas de valor atipico."""
    from .models import PropiedadesCompetencia

    parecidas = (PropiedadesCompetencia.objects
                 .filter(tipo_inmueble=propiedad.get('tipo_inmueble'),
                         tipo_operacion=propiedad.get('tipo_operacion'),
                         distrito=propiedad.get('distrito'))
                 .exclude(pk=propiedad.get('id'))
                 .values('id_origen', 'precio_usd', 'area_m2', 'area_terreno', 'area_construida')[:limite])
    return 'Propiedades parecidas del mismo distrito y tipo:\n%s' % json.dumps(
        [{k: (str(v) if v is not None else None) for k, v in p.items()} for p in parecidas],
        ensure_ascii=False)


def analizar(propiedad: dict) -> dict:
    """Corre los intentos sobre una propiedad y devuelve el veredicto final."""
    alertas = propiedad.get('alertas') or []
    if isinstance(alertas, dict):
        alertas = list(alertas)

    resultado = {'veredicto': 'error', 'motivo': '', 'correccion': {},
                 'confianza': None, 'intentos': 0, 'respuesta_cruda': ''}
    if not alertas:
        resultado.update(veredicto='ruido', motivo='Sin alertas que revisar.', intentos=1)
        return resultado

    extra = ''
    for n in range(1, MAX_INTENTOS + 1):
        # Cada intento agrega contexto: el 2 los datos crudos, el 3 los comparables.
        if n == 2:
            extra = 'Datos crudos que guardo el scraper:\n%s' % json.dumps(
                propiedad.get('datos_crudos') or {}, ensure_ascii=False)[:1800]
        elif n == 3:
            extra = _comparables(propiedad)

        datos, crudo = _intento(propiedad, alertas, extra)
        resultado['intentos'] = n
        resultado['respuesta_cruda'] = crudo

        if datos is None:
            resultado['motivo'] = crudo
            if n == 1:
                resultado['veredicto'] = 'error'
            continue

        veredicto = str(datos.get('veredicto') or '').strip().lower()
        if veredicto not in ('real', 'ruido', 'dudoso'):
            resultado['motivo'] = 'veredicto no reconocido: %r' % veredicto
            continue

        confianza = datos.get('confianza')
        try:
            confianza = float(confianza)
        except (TypeError, ValueError):
            confianza = None

        resultado.update(veredicto=veredicto, motivo=str(datos.get('motivo') or '')[:2000],
                         correccion=datos.get('correccion') or {}, confianza=confianza)
        # Si ya tiene veredicto firme, no gasta mas intentos.
        if veredicto in ('real', 'ruido') and (confianza is None or confianza >= CONFIANZA_SUFICIENTE):
            return resultado

    return resultado


def propiedades_con_alertas(sin_veredicto=True):
    """Propiedades con alertas, opcionalmente solo las que aun no tienen veredicto."""
    from .models import PropiedadesCompetencia, RevisionIAAlerta

    campos = DATA_FIELDS + ('datos_crudos', 'descripcion', 'dormitorios',
                            'banos', 'estacionamientos')
    filas = list(PropiedadesCompetencia.objects.values(*campos))
    revisadas = set(RevisionIAAlerta.objects.values_list('propiedad_id', flat=True)) if sin_veredicto else set()
    con_alertas = [r for r in analyze(filas) if r['alertas']]
    if sin_veredicto:
        con_alertas = [r for r in con_alertas if r['id'] not in revisadas]
    return con_alertas
