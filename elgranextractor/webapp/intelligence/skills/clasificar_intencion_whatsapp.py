"""
Skill: Clasificar Intención WhatsApp

Clasifica la intención de un mensaje de WhatsApp inmobiliario y extrae
datos estructurados usando DeepSeek API.

Diferencia entre:
- OFERTA: agente vendiendo/alquilando una propiedad ("Vendo casa...")
- DEMANDA: cliente buscando/comprando una propiedad ("Necesito terreno...")

Integración:
    Usa LLMService.extract_structured_data() para la extracción.
    Se registra automáticamente via SkillRegistry.register().
"""

import json
import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Dict, Optional, Any

from django.utils import timezone

from intelligence.skills.base import BaseSkill, SkillResult
from intelligence.services.llm import LLMService
from requerimientos.models import (
    CondicionChoices,
    TipoPropiedadChoices,
    MonedaChoices,
    FormaPagoChoices,
    TernarioChoices,
    FuenteChoices,
    TipoOriginalChoices,
)

logger = logging.getLogger(__name__)


class ClasificarIntencionWhatsAppSkill(BaseSkill):
    """
    Skill que clasifica la intención de un mensaje de WhatsApp inmobiliario
    y extrae datos estructurados para crear un Requerimiento.

    La clasificación de intención es el diferenciador clave:
    - 'oferta_venta' / 'oferta_alquiler' → agente publicando propiedad
    - 'demanda_compra' / 'demanda_alquiler' → cliente buscando propiedad
    """

    name = "clasificar_intencion_whatsapp"
    description = (
        "Clasifica la intención de un mensaje de WhatsApp inmobiliario "
        "(¿es un agente vendiendo o un cliente comprando?) y extrae "
        "datos estructurados como tipo de propiedad, distrito, presupuesto, etc."
    )
    category = "crm"
    access_level = 1
    is_active = True

    parameters_schema = {
        "texto": {
            "type": "string",
            "description": "Texto del mensaje de WhatsApp a analizar",
            "required": True,
        },
        "fuente": {
            "type": "string",
            "description": "Nombre del grupo WhatsApp de origen",
            "required": False,
            "default": "",
        },
        "autor": {
            "type": "string",
            "description": "Nombre del autor/agente del mensaje",
            "required": False,
            "default": "",
        },
        "fecha": {
            "type": "string",
            "description": "Fecha del mensaje en formato YYYY-MM-DD",
            "required": False,
            "default": "",
        },
        "hora": {
            "type": "string",
            "description": "Hora del mensaje en formato HH:MM:SS",
            "required": False,
            "default": "",
        },
    }

    # ── Schema de extracción MEJORADO ──────────────────────────────
    # La clave está en los campos 'intencion' y 'tipo_original' que
    # fuerzan al LLM a distinguir entre oferta (vendo) y demanda (compro).
    SCHEMA_EXTRACCION = {
        "intencion": (
            "CLASIFICACIÓN DE INTENCIÓN - CRÍTICO: Determina si el mensaje es de un "
            "agente vendiendo una propiedad o de un cliente buscando. "
            "Valores posibles: "
            "oferta_venta (agente dice 'VENDO', 'SE VENDE', 'OFREZCO', 'PONGO A LA VENTA', 'TENGO UN'), "
            "oferta_alquiler (agente dice 'ALQUILO', 'SE ALQUILA', 'RENTO'), "
            "demanda_compra (cliente dice 'NECESITO', 'BUSCO', 'COMPRO', 'QUIERO COMPRAR', 'ESTOY BUSCANDO'), "
            "demanda_alquiler (cliente dice 'BUSCO ALQUILER', 'NECESITO ALQUILAR', 'QUIERO ALQUILAR'), "
            "basura (mensaje irrelevante, publicidad, spam), "
            "no_determinado (no se puede determinar)"
        ),
        "tipo_original": (
            "Clasificación según el emisor del mensaje. "
            "Valores: "
            "PROPIEDAD VENTA (si es agente vendiendo una propiedad), "
            "REQUERIMIENTO COMPRA (si es cliente buscando comprar), "
            "REQUERIMIENTO ALQUILER (si es cliente buscando alquilar), "
            "BASURA (si es irrelevante), "
            "OTRO (no se puede clasificar)"
        ),
        "condicion": (
            "¿El cliente busca comprar o alquilar? (aplica solo si es demanda). "
            "Valores: compra, alquiler, ambos, no_especificado"
        ),
        "tipo_propiedad": (
            "Tipo de propiedad. "
            "Valores: departamento, casa, terreno, oficina, local_comercial, almacen, no_especificado"
        ),
        "distritos": (
            "Distrito(s) de Arequipa mencionados, separados por coma. "
            "Ej: Cayma, Yanahuara, Cercado, Miraflores, José Luis Bustamante y Rivero"
        ),
        "presupuesto_monto": (
            "Monto del presupuesto (si es demanda) o precio (si es oferta) como número, "
            "sin moneda. Ej: 150000"
        ),
        "presupuesto_moneda": "Moneda. Valores: USD, PEN, no_especificado",
        "presupuesto_forma_pago": "Forma de pago. Valores: contado, financiado, no_especificado",
        "habitaciones": "Número de habitaciones/dormitorios (número entero)",
        "banos": "Número de baños (número entero)",
        "cochera": "¿Tiene cochera? Valores: si, no, indiferente",
        "ascensor": "¿Tiene ascensor? Valores: si, no, indiferente",
        "amueblado": "¿Está amueblado? Valores: si, no, indiferente",
        "area_m2": "Área en metros cuadrados (número entero)",
        "piso_preferencia": "Preferencia de piso. Ej: primer piso, piso 3, etc.",
        "caracteristicas_extra": (
            "Características adicionales separadas por coma. "
            "Ej: balcón, jardín, seguridad, URGENTE"
        ),
        "agente": (
            "Nombre completo del agente inmobiliario o persona que publica el mensaje. "
            "Busca en el CUERPO del mensaje, NO en el encabezado. "
            "Ej: 'Jessica Castañeda', 'Mery Cahuana', 'Carlos López'. "
            "Si no hay nombre en el cuerpo, dejar vacío."
        ),
        "agente_telefono": "Número de teléfono del agente si está presente en el cuerpo del mensaje",
        "es_requerimiento_valido": (
            "¿Este mensaje es un requerimiento inmobiliario válido? "
            "(true si habla de propiedades, false si es spam/saludo/irrelevante). "
            "Valores: true, false"
        ),
    }

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Valida que los parámetros sean correctos."""
        if not params or "texto" not in params:
            return False
        texto = params.get("texto", "")
        if not texto or not texto.strip():
            return False
        return True

    def execute(self, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> SkillResult:
        """
        Ejecuta la clasificación y extracción de datos del mensaje.

        Args:
            params: Diccionario con:
                texto: Texto del mensaje WhatsApp.
                fuente: Grupo WhatsApp de origen (opcional).
                autor: Autor del mensaje (opcional).
                fecha: Fecha del mensaje en formato YYYY-MM-DD (opcional).
                hora: Hora del mensaje en formato HH:MM:SS (opcional).
            context: Contexto de ejecución (no usado).

        Returns:
            SkillResult con los datos estructurados listos para crear un Requerimiento.
        """
        try:
            if not self.validate_params(params):
                return SkillResult.error(
                    "El parámetro 'texto' es requerido y no debe estar vacío"
                )

            texto = params["texto"]
            fuente = params.get("fuente", "")
            autor = params.get("autor", "")
            fecha = params.get("fecha", "")
            hora = params.get("hora", "")

            if not texto or not texto.strip():
                return SkillResult.error("El texto del mensaje está vacío")

            # 1. Llamar a DeepSeek para extracción estructurada
            success, message, extracted = LLMService.extract_structured_data(
                text=texto,
                schema=self.SCHEMA_EXTRACCION,
            )

            if not success or not extracted:
                logger.warning(
                    f"DeepSeek no pudo extraer datos: {message}"
                )
                return SkillResult.ok(
                    data=self._crear_resultado_vacio(
                        texto, fuente, autor,
                        error=f"Extracción fallida: {message}",
                        fecha=fecha, hora=hora,
                    ),
                    message="Extracción fallida, datos vacíos devueltos",
                    metadata={"es_valido": False, "error": message},
                    skill_name=self.name,
                )

            # 2. Validar si es un requerimiento válido
            # Previously, messages flagged as not valid were discarded, causing empty results.
            # We now treat missing or false flags as still attempt to map fields, allowing partial data extraction.
            es_valido = str(extracted.get("es_requerimiento_valido", "true")).lower() == "true"
            if not es_valido:
                logger.info("Mensaje clasificado como no válido, pero se intentará extraer campos disponibles.")
            # Continue to mapping regardless of es_valido flag.

            # 3. Mapear campos extraídos al modelo Requerimiento
            requerimiento_data = self._mapear_campos(
                extracted=extracted,
                texto=texto,
                fuente=fuente,
                autor=autor,
                fecha=fecha,
                hora=hora,
            )

            return SkillResult.ok(
                data=requerimiento_data,
                message="Mensaje procesado, datos extraídos (validación opcional).",
                metadata={
                    "es_valido": es_valido,
                    "intencion": extracted.get("intencion", "no_determinado"),
                    "tipo_original": requerimiento_data.get("tipo_original", "OTRO"),
                },
                skill_name=self.name,
            )

        except Exception as e:
            logger.error(f"Error ejecutando skill: {e}", exc_info=True)
            return SkillResult.error(f"Error inesperado: {str(e)}")

    # ── Métodos de mapeo (adaptados de DeepSeekTransformer) ────────

    def _mapear_campos(
        self,
        extracted: Dict,
        texto: str,
        fuente: str,
        autor: str,
        fecha: str = "",
        hora: str = "",
    ) -> Dict:
        """
        Mapea los campos extraídos por DeepSeek a los campos del modelo Requerimiento.

        La diferencia clave con DeepSeekTransformer._mapear_campos() es que
        aquí se usa 'intencion' y 'tipo_original' para clasificar correctamente
        si es oferta (agente vendiendo) o demanda (cliente comprando).

        Args:
            extracted: Diccionario con datos extraídos por DeepSeek.
            texto: Texto original del mensaje.
            fuente: Fuente del mensaje.
            autor: Autor del mensaje.
            fecha: Fecha del mensaje en formato YYYY-MM-DD (opcional).
            hora: Hora del mensaje en formato HH:MM:SS (opcional).
        """
        # ── Determinar tipo_original desde la intención ──
        intencion = extracted.get("intencion", "").strip().lower()
        tipo_original = self._determinar_tipo_original(intencion, extracted)

        # ── Mapear condicion ──
        # Si es oferta_venta, la condicion es irrelevante (no es cliente comprando)
        # pero mapeamos igual para mantener compatibilidad
        condicion = self._mapear_choice(
            extracted.get("condicion", ""),
            CondicionChoices,
            CondicionChoices.NO_ESPECIFICADO,
        )

        # ── Mapear tipo_propiedad ──
        tipo_propiedad = self._mapear_choice(
            extracted.get("tipo_propiedad", ""),
            TipoPropiedadChoices,
            TipoPropiedadChoices.NO_ESPECIFICADO,
        )

        # ── Mapear moneda ──
        moneda = self._mapear_choice(
            extracted.get("presupuesto_moneda", ""),
            MonedaChoices,
            MonedaChoices.NO_ESPECIFICADO,
        )

        # ── Mapear forma de pago ──
        forma_pago = self._mapear_choice(
            extracted.get("presupuesto_forma_pago", ""),
            FormaPagoChoices,
            FormaPagoChoices.NO_ESPECIFICADO,
        )

        # ── Mapear ternarios ──
        cochera = self._mapear_choice(
            extracted.get("cochera", ""),
            TernarioChoices,
            TernarioChoices.INDIFERENTE,
        )
        ascensor = self._mapear_choice(
            extracted.get("ascensor", ""),
            TernarioChoices,
            TernarioChoices.INDIFERENTE,
        )
        amueblado = self._mapear_choice(
            extracted.get("amueblado", ""),
            TernarioChoices,
            TernarioChoices.INDIFERENTE,
        )

        # ── Construir diccionario final ──
        # Usar fecha/hora del mensaje si están disponibles, sino timezone.now()
        from datetime import date, time
        fecha_final = None
        hora_final = None
        if fecha:
            try:
                fecha_final = date.fromisoformat(fecha) if isinstance(fecha, str) else fecha
            except (ValueError, TypeError):
                pass
        if hora:
            try:
                # La hora puede venir como "HH:MM:SS" o "HH:MM"
                hora_str = hora if isinstance(hora, str) else str(hora)
                parts = hora_str.split(':')
                if len(parts) >= 2:
                    hora_final = time(int(parts[0]), int(parts[1]))
            except (ValueError, TypeError):
                pass
        if fecha_final is None:
            fecha_final = timezone.now().date()
        if hora_final is None:
            hora_final = timezone.now().time()

        # Determinar el nombre del agente con la prioridad correcta:
        # 1. Si el autor del encabezado NO es un teléfono, usar ese nombre
        # 2. Si es teléfono, usar lo que DeepSeek extrajo del cuerpo del mensaje
        # 3. Si DeepSeek no encontró nombre, usar el teléfono como fallback
        nombre_agente = autor
        if self._es_telefono(autor):
            nombre_agente = extracted.get("agente", "") or autor

        data = {
            "fuente": self._mapear_fuente(fuente),
            "fecha": fecha_final,
            "hora": hora_final,
            "agente": nombre_agente,
            "tipo_original": tipo_original,
            "condicion": condicion,
            "tipo_propiedad": tipo_propiedad,
            "distritos": extracted.get("distritos", ""),
            "presupuesto_monto": self._parsear_decimal(
                extracted.get("presupuesto_monto")
            ),
            "presupuesto_moneda": moneda,
            "presupuesto_forma_pago": forma_pago,
            "habitaciones": self._parsear_entero(
                extracted.get("habitaciones")
            ),
            "banos": self._parsear_entero(
                extracted.get("banos")
            ),
            "cochera": cochera,
            "ascensor": ascensor,
            "amueblado": amueblado,
            "area_m2": self._parsear_entero(
                extracted.get("area_m2")
            ),
            "piso_preferencia": extracted.get("piso_preferencia", ""),
            "caracteristicas_extra": extracted.get("caracteristicas_extra", ""),
            "agente_telefono": extracted.get("agente_telefono", ""),
            "requerimiento": texto,
            # Metadata adicional para depuración
            "_intencion_original": intencion,
        }

        return data

    def _determinar_tipo_original(self, intencion: str, extracted: Dict) -> str:
        """
        Determina el valor de tipo_original basado en la intención clasificada.

        Mapeo:
            oferta_venta     → PROPIEDAD VENTA
            oferta_alquiler  → PROPIEDAD VENTA (se alquila pero es oferta)
            demanda_compra   → REQUERIMIENTO COMPRA
            demanda_alquiler → REQUERIMIENTO ALQUILER
            basura           → BASURA
            otro/default     → OTRO
        """
        mapping = {
            "oferta_venta": TipoOriginalChoices.PROPIEDAD_VENTA,
            "oferta_alquiler": TipoOriginalChoices.PROPIEDAD_VENTA,
            "demanda_compra": TipoOriginalChoices.REQ_COMPRA,
            "demanda_alquiler": TipoOriginalChoices.REQ_ALQUILER,
            "basura": TipoOriginalChoices.BASURA,
        }

        tipo = mapping.get(intencion)
        if tipo:
            return tipo

        # Fallback: usar tipo_original del extracted si existe
        tipo_extraido = extracted.get("tipo_original", "").strip().upper()
        if tipo_extraido:
            for choice in TipoOriginalChoices.values:
                if choice == tipo_extraido:
                    return choice

        return TipoOriginalChoices.OTRO

    @staticmethod
    def _es_telefono(texto: str) -> bool:
        """Determina si un texto es un número de teléfono (no un nombre).

        Detecta formatos como:
        - +51 958 063 438
        - 958063438
        - +51 958063438
        - 959 729 594
        """
        if not texto:
            return False
        # Limpiar caracteres de control Unicode
        limpio = re.sub(r'[\u2068\u2069\u200e\u200f]', '', texto)
        # Quitar espacios y el prefijo +51
        solo_digitos = re.sub(r'[\s\+]', '', limpio)
        # Si después de limpiar, el resultado son solo dígitos y tiene 7+ dígitos, es teléfono
        if solo_digitos.isdigit() and len(solo_digitos) >= 7:
            return True
        return False

    def _mapear_choice(self, valor: str, choices_class, default):
        """Mapea un valor string a una choice de Django."""
        if not valor:
            return default

        valor = valor.strip().lower()

        # Buscar match directo
        for choice in choices_class.values:
            if choice == valor:
                return choice

        # Buscar match por label
        for choice in choices_class.choices:
            if valor in choice[1].lower():
                return choice[0]

        return default

    def _mapear_fuente(self, fuente: str) -> str:
        """Mapea el nombre del grupo WhatsApp a un valor de FuenteChoices."""
        if not fuente:
            return FuenteChoices.OTRO

        fuente_lower = fuente.lower().replace(" ", "_")

        for choice in FuenteChoices.values:
            if choice == fuente_lower:
                return choice

        # Match parcial
        for choice in FuenteChoices.values:
            if choice in fuente_lower or fuente_lower in choice:
                return choice

        return FuenteChoices.OTRO

    def _parsear_decimal(self, valor) -> Optional[Decimal]:
        """Convierte un valor a Decimal de forma segura."""
        if valor is None:
            return None
        try:
            return Decimal(str(valor))
        except (ValueError, TypeError, InvalidOperation):
            return None

    def _parsear_entero(self, valor) -> Optional[int]:
        """Convierte un valor a entero de forma segura."""
        if valor is None:
            return None
        try:
            return int(float(str(valor)))
        except (ValueError, TypeError):
            return None

    def _crear_resultado_vacio(
        self,
        texto: str,
        fuente: str,
        autor: str,
        error: str = "",
        es_valido: bool = False,
        fecha: str = "",
        hora: str = "",
    ) -> Dict:
        """Crea un resultado vacío para cuando la transformación falla.

        Args:
            texto: Texto original del mensaje.
            fuente: Grupo de origen.
            autor: Autor del mensaje.
            error: Mensaje de error descriptivo.
            es_valido: Si el mensaje se considera un requerimiento válido.
            fecha: Fecha del mensaje en formato YYYY-MM-DD (opcional).
            hora: Hora del mensaje en formato HH:MM:SS (opcional).
        """
        # Usar fecha/hora del mensaje si están disponibles, sino timezone.now()
        from datetime import date, time
        fecha_final = None
        hora_final = None
        if fecha:
            try:
                fecha_final = date.fromisoformat(fecha) if isinstance(fecha, str) else fecha
            except (ValueError, TypeError):
                pass
        if hora:
            try:
                hora_str = hora if isinstance(hora, str) else str(hora)
                parts = hora_str.split(':')
                if len(parts) >= 2:
                    hora_final = time(int(parts[0]), int(parts[1]))
            except (ValueError, TypeError):
                pass
        if fecha_final is None:
            fecha_final = timezone.now().date()
        if hora_final is None:
            hora_final = timezone.now().time()

        return {
            "fuente": self._mapear_fuente(fuente),
            "fecha": fecha_final,
            "hora": hora_final,
            "agente": autor,
            "tipo_original": TipoOriginalChoices.OTRO,
            "condicion": CondicionChoices.NO_ESPECIFICADO,
            "tipo_propiedad": TipoPropiedadChoices.NO_ESPECIFICADO,
            "distritos": "",
            "requerimiento": texto,
            "agente_telefono": "",
            "_error": error,
            "_es_valido": es_valido,
        }
