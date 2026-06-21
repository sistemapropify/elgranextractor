"""
ResolverContextoSkill — Skill intermedia que resuelve referencias ambiguas
en mensajes conversacionales usando el historial y contexto activo de sesión.

⚠️ DEPRECATED desde refactor v2 (arquitectura_chat_inteligente_v2.md).
⚠️ DeepSeek ahora resuelve el contexto conversacional directamente en el
⚠️ prompt de orquestación. Este archivo se mantiene solo para compatibilidad
⚠️ con código legacy. No usar en código nuevo.

Propósito (legacy):
    Antes de llamar a busqueda_propiedades, esta skill enriquece los parámetros
    del mensaje actual con el contexto de turnos anteriores. Resuelve expresiones
    como "el mismo distrito", "y de 3 habitaciones", "y en cayma", "y vendidas"
    sin necesidad de que el usuario repita todos los filtros.

Ubicación: webapp/intelligence/skills/resolver_contexto.py (DEPRECATED)
Pipeline:  Ejecutar ANTES de busqueda_propiedades via execute_skill_pipeline()
"""

import json
import logging
from typing import Dict, Any, Optional

from .base import BaseSkill, SkillResult
from ..services.llm import LLMService

logger = logging.getLogger(__name__)


class ResolverContextoSkill(BaseSkill):
    """
    Resuelve referencias ambiguas en mensajes conversacionales usando
    el historial y contexto activo de la sesión. Devuelve parámetros
    completos y limpios listos para pasar a busqueda_propiedades.

    Ejemplos de resolución:
    - "y de 3 habitaciones"          → hereda distrito y tipo, cambia habitaciones
    - "y en cayma"                   → hereda tipo y habitaciones, cambia distrito
    - "y las vendidas"               → hereda todo, agrega condicion=Vendida
    - "cuántas hay en el mismo"      → resuelve "mismo" al distrito activo
    - "dame terrenos"                → cambia tipo, limpia habitaciones (cambio de tema)
    """

    name = "resolver_contexto"
    description = (
        "Resuelve referencias ambiguas o incompletas en mensajes del usuario usando "
        "el historial de conversación y el contexto activo de la sesión. "
        "Úsala antes de busqueda_propiedades cuando el mensaje contiene pronombres "
        "como 'el mismo', 'ahí', 'esos', 'y de', 'también', o cuando faltan filtros "
        "que se mencionaron en turnos anteriores. "
        "Ejemplos: 'y de 3 habitaciones', 'y en cayma', 'cuántas vendidas en el mismo distrito', "
        "'también muéstrame las de 2 baños', 'y las más baratas'."
    )
    category = "custom"
    access_level = 1
    is_active = True

    # Campos que esta skill puede heredar, reemplazar o limpiar
    CAMPOS_GESTIONADOS = [
        'distrito',
        'tipo_propiedad',
        'operacion',
        'precio_min',
        'precio_max',
        'habitaciones',
        'banos',
        'area_min',
        'area_max',
        'condicion',
        'semantic_query',
    ]

    # Palabras clave que indican cambio de tema (limpian campos relacionados)
    PALABRAS_CAMBIO_TEMA = [
        'terreno', 'terrenos', 'casa', 'casas', 'departamento', 'departamentos',
        'duplex', 'local', 'oficina', 'proyecto',
    ]

    parameters_schema = {
        'mensaje_actual': {
            'type': 'string',
            'description': 'Mensaje actual del usuario que puede contener referencias ambiguas',
            'required': True,
        },
        'contexto_activo': {
            'type': 'object',
            'description': (
                'Diccionario con el estado de la búsqueda activa en la sesión. '
                'Campos posibles: distrito, tipo_propiedad, operacion, precio_min, '
                'precio_max, habitaciones, banos, area_min, condicion, semantic_query. '
                'Puede ser un dict vacío {} si es el primer turno.'
            ),
            'required': True,
        },
        'historial_mensajes': {
            'type': 'array',
            'description': (
                'Lista de los últimos mensajes de la conversación en orden cronológico. '
                'Cada elemento es un string. Máximo recomendado: 6 mensajes. '
                'Ejemplo: ["usuario: qué hay en cerro colorado", "asistente: encontré 16 propiedades..."]'
            ),
            'required': False,
        },
        'llm_service': {
            'type': 'string',
            'description': (
                'Nombre del servicio LLM a usar para la resolución semántica. '
                'Valores posibles: "deepseek", "openai", "anthropic". '
                'Si no se especifica, usa el servicio configurado por defecto.'
            ),
            'required': False,
        },
    }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        if not params:
            return False
        mensaje = params.get('mensaje_actual', '').strip()
        if not mensaje:
            return False
        contexto = params.get('contexto_activo')
        if contexto is None or not isinstance(contexto, dict):
            return False
        return True

    def execute(
        self,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> SkillResult:
        try:
            if not self.validate_params(params):
                return SkillResult.error(
                    message="Se requiere 'mensaje_actual' (string) y 'contexto_activo' (dict)",
                    metadata={'parametros_recibidos': list(params.keys())},
                    skill_name=self.name
                )

            mensaje_actual = params['mensaje_actual'].strip()
            contexto_activo = params.get('contexto_activo', {})
            historial = params.get('historial_mensajes', [])

            # Si el contexto está vacío no hay nada que resolver.
            # Devolvemos los parámetros extraídos del mensaje actual sin modificar.
            if not contexto_activo:
                logger.info(
                    "[resolver_contexto] Contexto vacío, primer turno. "
                    "Retornando mensaje sin enriquecimiento."
                )
                return SkillResult.ok(
                    data={
                        'params_resueltos': {},
                        'contexto_actualizado': {},
                        'campos_heredados': [],
                        'campos_cambiados': [],
                        'cambio_de_tema': False,
                        'requiere_enriquecimiento': False,
                        'mensaje_procesado': mensaje_actual,
                    },
                    message="Primer turno, no hay contexto previo que heredar.",
                    metadata={'contexto_vacio': True},
                    skill_name=self.name
                )

            # Intentar resolución via LLM
            resultado_llm = self._resolver_con_llm(
                mensaje_actual=mensaje_actual,
                contexto_activo=contexto_activo,
                historial=historial,
                llm_service=params.get('llm_service'),
            )

            if resultado_llm is not None:
                return SkillResult.ok(
                    data=resultado_llm,
                    message=self._generar_mensaje_resumen(resultado_llm),
                    metadata={
                        'metodo': 'llm',
                        'campos_gestionados': self.CAMPOS_GESTIONADOS,
                    },
                    skill_name=self.name
                )

            # Fallback: resolución por reglas si el LLM no está disponible
            logger.warning(
                "[resolver_contexto] LLM no disponible, usando resolución por reglas."
            )
            resultado_reglas = self._resolver_por_reglas(
                mensaje_actual=mensaje_actual,
                contexto_activo=contexto_activo,
            )
            return SkillResult.ok(
                data=resultado_reglas,
                message=self._generar_mensaje_resumen(resultado_reglas),
                metadata={
                    'metodo': 'reglas',
                    'advertencia': 'LLM no disponible, resolución limitada por reglas.',
                },
                skill_name=self.name
            )

        except Exception as e:
            logger.error(f"[resolver_contexto] Error inesperado: {e}", exc_info=True)
            return SkillResult.error(
                message=f"Error al resolver contexto: {str(e)}",
                metadata={'mensaje_actual': params.get('mensaje_actual', '')},
                skill_name=self.name
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Resolución via LLM (método principal)
    # ─────────────────────────────────────────────────────────────────────────

    def _resolver_con_llm(
        self,
        mensaje_actual: str,
        contexto_activo: Dict[str, Any],
        historial: list,
        llm_service: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Llama al LLM con un prompt estructurado para resolver referencias
        ambiguas. Retorna el dict con params_resueltos o None si falla.

        Integración:
            Adapta el bloque 'llamar al LLM' según el servicio que uses
            en tu sistema (DeepSeek, OpenAI, etc.). Usa el servicio
            configurado en services/llm.py o el especificado en llm_service.
        """
        try:
            prompt_sistema = self._construir_prompt_sistema()
            prompt_usuario = self._construir_prompt_usuario(
                mensaje_actual=mensaje_actual,
                contexto_activo=contexto_activo,
                historial=historial,
            )

            # ── LLAMADA REAL A DEEPSEEK ──────────────────────────────────────
            # Usa LLMService._call_deepseek_api con temperature=0.0 para
            # respuestas deterministas (siempre el mismo JSON para el mismo input).
            success, message, response_data = LLMService._call_deepseek_api(
                messages=[{"role": "user", "content": prompt_usuario}],
                system_prompt=prompt_sistema,
            )

            if not success or response_data is None:
                logger.warning(
                    f"[resolver_contexto] LLM no disponible: {message}"
                )
                return None

            respuesta_raw = response_data.get('content', '')
            if not respuesta_raw:
                logger.warning(
                    "[resolver_contexto] Respuesta LLM vacía"
                )
                return None

            return self._parsear_respuesta_llm(respuesta_raw, contexto_activo)

        except Exception as e:
            logger.warning(f"[resolver_contexto] Error en llamada LLM: {e}")
            return None

    def _construir_prompt_sistema(self) -> str:
        return """Eres un asistente especializado en búsqueda inmobiliaria en Arequipa, Perú.
Tu única tarea es analizar el mensaje del usuario y determinar qué parámetros de búsqueda
deben aplicarse, considerando el contexto de la conversación anterior.

REGLAS ESTRICTAS:
1. Responde ÚNICAMENTE con JSON válido. Sin texto adicional, sin markdown, sin explicaciones.
2. Si el usuario menciona un filtro nuevo, ese reemplaza al anterior del mismo tipo.
3. Si el usuario no menciona un filtro, hereda el del contexto activo (si existe).
4. Si el usuario cambia de tipo de propiedad (ej: "dame terrenos"), limpia habitaciones y baños.
5. "el mismo", "ahí", "ese distrito", "esa zona" → heredar el valor del contexto activo.
6. "también", "y de", "además" → heredar todo y agregar/cambiar el nuevo filtro.
7. "vendidas", "disponibles", "en venta" → actualizar campo condicion u operacion.
8. Si no hay ningún parámetro aplicable, devolver los campos como null.

CAMPOS DISPONIBLES:
- distrito: string (ej: "Cerro Colorado", "Cayma", "Yanahuara")
- tipo_propiedad: string (ej: "Departamento", "Casa", "Terreno", "Duplex")
- operacion: string ("Venta" | "Alquiler")
- precio_min: number (en la moneda del contexto)
- precio_max: number
- habitaciones: number
- banos: number
- area_min: number (m²)
- condicion: string ("Disponible" | "Vendida" | "Alquilada")
- semantic_query: string (búsqueda por texto libre)
- cambio_de_tema: boolean (true si el usuario cambió completamente de tema/tipo)

FORMATO DE RESPUESTA (siempre este JSON exacto):
{
  "params_resueltos": {
    "distrito": null,
    "tipo_propiedad": null,
    "operacion": null,
    "precio_min": null,
    "precio_max": null,
    "habitaciones": null,
    "banos": null,
    "area_min": null,
    "condicion": null,
    "semantic_query": null
  },
  "campos_heredados": [],
  "campos_cambiados": [],
  "cambio_de_tema": false,
  "requiere_enriquecimiento": true
}"""

    def _construir_prompt_usuario(
        self,
        mensaje_actual: str,
        contexto_activo: Dict[str, Any],
        historial: list,
    ) -> str:
        historial_str = ""
        if historial:
            ultimos = historial[-6:]  # Máximo 6 mensajes para no saturar el contexto
            historial_str = "\n".join(f"  {msg}" for msg in ultimos)
        else:
            historial_str = "  (sin historial previo)"

        contexto_str = json.dumps(
            {k: v for k, v in contexto_activo.items() if v is not None},
            ensure_ascii=False,
            indent=2
        )

        return f"""HISTORIAL DE CONVERSACIÓN (últimos mensajes):
{historial_str}

CONTEXTO ACTIVO DE BÚSQUEDA (filtros del turno anterior):
{contexto_str}

MENSAJE ACTUAL DEL USUARIO:
"{mensaje_actual}"

Analiza el mensaje actual considerando el historial y el contexto activo.
Devuelve el JSON con los parámetros resueltos completos para la próxima búsqueda."""

    def _parsear_respuesta_llm(
        self,
        respuesta_raw: str,
        contexto_activo: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Parsea y valida la respuesta JSON del LLM.
        Aplica fallback al contexto activo si el JSON está incompleto.
        """
        try:
            # Limpiar posibles backticks de markdown si el LLM los incluyó
            limpio = respuesta_raw.strip()
            if limpio.startswith('```'):
                limpio = limpio.split('```')[1]
                if limpio.startswith('json'):
                    limpio = limpio[4:]
            limpio = limpio.strip()

            datos = json.loads(limpio)

            params_resueltos = datos.get('params_resueltos', {})
            cambio_de_tema = datos.get('cambio_de_tema', False)

            # Sanidad: heredar del contexto activo los campos que el LLM dejó en null
            # y que NO fueron explícitamente cambiados por el usuario.
            #
            # - Si es cambio_de_tema (ej: "dame terrenos"), se hereda el distrito
            #   y otros filtros no relacionados, pero se limpian habitaciones/baños.
            # - Si NO es cambio_de_tema, se heredan todos los campos del contexto.
            for campo in self.CAMPOS_GESTIONADOS:
                if params_resueltos.get(campo) is None:
                    valor_contexto = contexto_activo.get(campo)
                    if valor_contexto is not None:
                        if cambio_de_tema:
                            # En cambio de tema: heredar distrito, precio, operacion, condicion
                            # pero NO heredar habitaciones/banos (se limpian al cambiar tipo)
                            if campo not in ('habitaciones', 'banos', 'tipo_propiedad', 'semantic_query'):
                                params_resueltos[campo] = valor_contexto
                        else:
                            # Sin cambio de tema: heredar todo
                            params_resueltos[campo] = valor_contexto

            # Construir contexto actualizado (solo campos no nulos)
            contexto_actualizado = {
                k: v for k, v in params_resueltos.items() if v is not None
            }

            return {
                'params_resueltos': params_resueltos,
                'contexto_actualizado': contexto_actualizado,
                'campos_heredados': datos.get('campos_heredados', []),
                'campos_cambiados': datos.get('campos_cambiados', []),
                'cambio_de_tema': cambio_de_tema,
                'requiere_enriquecimiento': datos.get('requiere_enriquecimiento', True),
                'mensaje_procesado': None,
            }

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"[resolver_contexto] Error parseando respuesta LLM: {e}")
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # Fallback: resolución por reglas simples
    # ─────────────────────────────────────────────────────────────────────────

    def _resolver_por_reglas(
        self,
        mensaje_actual: str,
        contexto_activo: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Resolución básica por reglas cuando el LLM no está disponible.
        Detecta patrones simples y hereda el contexto activo completo.
        Limitación: no entiende semántica compleja, solo patrones directos.
        """
        mensaje_lower = mensaje_actual.lower()
        params_resueltos = dict(contexto_activo)  # Heredar todo por defecto
        campos_cambiados = []
        cambio_de_tema = False

        # Detectar cambio de tipo de propiedad
        for palabra in self.PALABRAS_CAMBIO_TEMA:
            if palabra in mensaje_lower:
                tipo_mapeado = self._mapear_tipo_propiedad(palabra)
                if tipo_mapeado and tipo_mapeado != contexto_activo.get('tipo_propiedad'):
                    params_resueltos['tipo_propiedad'] = tipo_mapeado
                    # Cambio de tipo → limpiar habitaciones y baños
                    params_resueltos['habitaciones'] = None
                    params_resueltos['banos'] = None
                    campos_cambiados.append('tipo_propiedad')
                    cambio_de_tema = True
                break

        # Detectar número de habitaciones explícito (ej: "3 habitaciones", "2 dormitorios")
        import re
        match_hab = re.search(
            r'(\d+)\s*(?:habitacion(?:es)?|dormitorio(?:s)?|cuarto(?:s)?|hab\.?)',
            mensaje_lower
        )
        if match_hab:
            nuevo_valor = int(match_hab.group(1))
            if nuevo_valor != contexto_activo.get('habitaciones'):
                params_resueltos['habitaciones'] = nuevo_valor
                campos_cambiados.append('habitaciones')

        # Detectar condición vendida/disponible
        if any(p in mensaje_lower for p in ['vendida', 'vendidas', 'vendido', 'vendidos']):
            if contexto_activo.get('condicion') != 'Vendida':
                params_resueltos['condicion'] = 'Vendida'
                campos_cambiados.append('condicion')
        elif any(p in mensaje_lower for p in ['disponible', 'disponibles', 'en venta']):
            if contexto_activo.get('condicion') != 'Disponible':
                params_resueltos['condicion'] = 'Disponible'
                campos_cambiados.append('condicion')

        # Campos heredados = los del contexto que no cambiaron
        campos_heredados = [
            c for c in self.CAMPOS_GESTIONADOS
            if c not in campos_cambiados and contexto_activo.get(c) is not None
        ]

        contexto_actualizado = {
            k: v for k, v in params_resueltos.items() if v is not None
        }

        return {
            'params_resueltos': params_resueltos,
            'contexto_actualizado': contexto_actualizado,
            'campos_heredados': campos_heredados,
            'campos_cambiados': campos_cambiados,
            'cambio_de_tema': cambio_de_tema,
            'requiere_enriquecimiento': True,
            'mensaje_procesado': mensaje_actual,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Utilidades
    # ─────────────────────────────────────────────────────────────────────────

    def _mapear_tipo_propiedad(self, palabra: str) -> Optional[str]:
        mapa = {
            'departamento': 'Departamento',
            'departamentos': 'Departamento',
            'casa': 'Casa',
            'casas': 'Casa',
            'terreno': 'Terreno',
            'terrenos': 'Terreno',
            'duplex': 'Duplex',
            'local': 'Local Comercial',
            'oficina': 'Oficina',
            'proyecto': 'Proyecto',
        }
        return mapa.get(palabra.lower())

    def _generar_mensaje_resumen(self, resultado: Dict[str, Any]) -> str:
        heredados = resultado.get('campos_heredados', [])
        cambiados = resultado.get('campos_cambiados', [])
        cambio_tema = resultado.get('cambio_de_tema', False)

        partes = []
        if cambiados:
            partes.append(f"Filtros actualizados: {', '.join(cambiados)}")
        if heredados:
            partes.append(f"Filtros heredados: {', '.join(heredados)}")
        if cambio_tema:
            partes.append("Cambio de tema detectado")

        return ". ".join(partes) if partes else "Contexto procesado sin cambios."
