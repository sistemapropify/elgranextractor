"""
Servicio de transformación de mensajes WhatsApp a Requerimientos usando DeepSeek.

Convierte el texto crudo de un mensaje de WhatsApp en un objeto Requerimiento
estructurado, extrayendo campos como tipo de propiedad, distrito, presupuesto,
condición (compra/alquiler), y características.

AHORA DELEGA EN EL SKILL 'clasificar_intencion_whatsapp' del sistema de skills
para la extracción y clasificación de intención (vendo vs compro/necesito).

Integración:
    Usa SkillOrchestrator para ejecutar el skill.
    Mantiene compatibilidad hacia atrás con el schema anterior.
"""
import json
import logging
import re
from datetime import datetime
from typing import Dict, Optional, Tuple
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from requerimientos.models import (
    Requerimiento,
    FuenteChoices,
    CondicionChoices,
    TipoPropiedadChoices,
    MonedaChoices,
    FormaPagoChoices,
    TernarioChoices,
)
from intelligence.services.llm import LLMService
from intelligence.skills.cache import SkillCache
from intelligence.skills.orchestrator import SkillOrchestrator
from intelligence.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)


class DeepSeekTransformerError(Exception):
    """Error base del transformador DeepSeek."""
    pass


class DeepSeekTransformer:
    """
    Transforma mensajes de WhatsApp en objetos Requerimiento estructurados.

    AHORA delega en el skill 'clasificar_intencion_whatsapp' para la
    extracción semántica y clasificación de intención (vendo vs compro).

    Mantiene compatibilidad hacia atrás: si el skill no está disponible,
    usa el método anterior con LLMService.extract_structured_data().
    """

    # Schema de extracción legacy (mantenido por compatibilidad)
    SCHEMA_EXTRACCION = {
        "condicion": "¿El cliente busca comprar o alquilar? Valores: compra, alquiler, ambos, no_especificado",
        "tipo_propiedad": "Tipo de propiedad buscada. Valores: departamento, casa, terreno, oficina, local_comercial, almacen, no_especificado",
        "distritos": "Distrito(s) de Arequipa mencionados, separados por coma. Ej: Cayma, Yanahuara",
        "presupuesto_monto": "Monto del presupuesto como número (sin moneda). Ej: 150000",
        "presupuesto_moneda": "Moneda del presupuesto. Valores: USD, PEN, no_especificado",
        "presupuesto_forma_pago": "Forma de pago. Valores: contado, financiado, no_especificado",
        "habitaciones": "Número de habitaciones/dormitorios (número entero)",
        "banos": "Número de baños (número entero)",
        "cochera": "¿Requiere cochera? Valores: si, no, indiferente",
        "ascensor": "¿Requiere ascensor? Valores: si, no, indiferente",
        "amueblado": "¿Requiere amueblado? Valores: si, no, indiferente",
        "area_m2": "Área en metros cuadrados (número entero)",
        "piso_preferencia": "Preferencia de piso. Ej: primer piso, piso 3, etc.",
        "caracteristicas_extra": "Características adicionales separadas por coma. Ej: balcón, jardín, seguridad",
        "agente": (
            "Nombre completo del agente inmobiliario o persona que publica el mensaje. "
            "Busca en el CUERPO del mensaje, NO en el encabezado. "
            "Ej: 'Jessica Castañeda', 'Mery Cahuana', 'Carlos López'. "
            "Si no hay nombre en el cuerpo, dejar vacío."
        ),
        "agente_telefono": "Número de teléfono del agente si está presente en el cuerpo del mensaje",
        "es_requerimiento_valido": "¿Este mensaje es un requerimiento inmobiliario válido? true/false",
    }

    @classmethod
    def transformar(cls, texto: str, fuente: str, autor: str = '',
                    fecha: Optional[str] = None, hora: Optional[str] = None) -> Dict:
        """
        Transforma un mensaje de WhatsApp en un diccionario listo para
        crear un objeto Requerimiento.

        PRIMERO intenta usar el skill 'clasificar_intencion_whatsapp'.
        Si no está disponible, cae al método legacy.

        Args:
            texto: Texto del mensaje de WhatsApp.
            fuente: Identificador de la fuente (grupo WhatsApp).
            autor: Nombre del agente que publicó el mensaje.
            fecha: Fecha del mensaje en formato YYYY-MM-DD (opcional).
                   Si no se proporciona, se usa timezone.now().
            hora: Hora del mensaje en formato HH:MM:SS (opcional).
                  Si no se proporciona, se usa timezone.now().

        Returns:
            Dict con campos del modelo Requerimiento, o dict con error.
        """
        # Intentar usar el skill primero
        skill_result = cls._ejecutar_skill(texto, fuente, autor, fecha, hora)
        if skill_result is not None:
            return skill_result

        # Fallback: método legacy
        logger.info("Usando método legacy de extracción (skill no disponible)")
        return cls._transformar_legacy(texto, fuente, autor, fecha, hora)

    @classmethod
    def _ejecutar_skill(cls, texto: str, fuente: str, autor: str,
                        fecha: Optional[str] = None, hora: Optional[str] = None) -> Optional[Dict]:
        """
        Intenta ejecutar el skill 'clasificar_intencion_whatsapp'.

        Args:
            texto: Texto del mensaje.
            fuente: Fuente del mensaje.
            autor: Autor del mensaje.
            fecha: Fecha del mensaje en formato YYYY-MM-DD (opcional).
            hora: Hora del mensaje en formato HH:MM:SS (opcional).

        Returns:
            Dict con datos si el skill se ejecutó exitosamente, None si falló.
        """
        try:
            # Obtener orchestrator y registry
            registry = SkillRegistry()
            cache = SkillCache()
            orchestrator = SkillOrchestrator(registry=registry, cache=cache)

            # Verificar que el skill existe en el registro
            # El nuevo SkillRegistry almacena las skills en _skill_classes (dict)
            if "clasificar_intencion_whatsapp" not in registry._skill_classes:
                logger.debug("Skill 'clasificar_intencion_whatsapp' no encontrado en registry._skill_classes")
                return None

            # Ejecutar skill
            result = orchestrator.execute_skill(
                skill_name="clasificar_intencion_whatsapp",
                parameters={
                    "texto": texto,
                    "fuente": fuente,
                    "autor": autor,
                    "fecha": fecha,
                    "hora": hora,
                },
            )

            if result.success and result.data:
                logger.info(
                    f"Skill clasificó intención: "
                    f"{result.data.get('_intencion_original', 'N/A')} → "
                    f"{result.data.get('tipo_original', 'N/A')}"
                )
                # Asegurar que fecha/hora del mensaje se preserven
                if fecha and 'fecha' not in result.data:
                    result.data['fecha'] = fecha
                if hora and 'hora' not in result.data:
                    result.data['hora'] = hora
                return result.data

            logger.warning(f"Skill no retornó datos exitosos: {result.error_message}")
            return None

        except Exception as e:
            logger.warning(f"Error ejecutando skill, usando fallback: {e}")
            return None

    @classmethod
    def _transformar_legacy(cls, texto: str, fuente: str, autor: str = '',
                            fecha: Optional[str] = None, hora: Optional[str] = None) -> Dict:
        """
        Método legacy de transformación (llamada directa a LLMService).
        Se mantiene por compatibilidad.

        Args:
            texto: Texto del mensaje.
            fuente: Fuente del mensaje.
            autor: Autor del mensaje.
            fecha: Fecha del mensaje en formato YYYY-MM-DD (opcional).
            hora: Hora del mensaje en formato HH:MM:SS (opcional).
        """
        try:
            success, message, extracted = LLMService.extract_structured_data(
                text=texto,
                schema=cls.SCHEMA_EXTRACCION,
            )

            if not success or not extracted:
                logger.warning(
                    f"DeepSeek no pudo extraer datos del mensaje: {message}"
                )
                return cls._crear_resultado_vacio(
                    texto, fuente, autor,
                    error=f"Extracción fallida: {message}",
                    fecha=fecha, hora=hora,
                )

            if not extracted.get('es_requerimiento_valido', True):
                logger.info("DeepSeek clasificó el mensaje como no válido")
                return cls._crear_resultado_vacio(
                    texto, fuente, autor,
                    error="Mensaje no es un requerimiento válido",
                    es_valido=False,
                    fecha=fecha, hora=hora,
                )

            requerimiento_data = cls._mapear_campos(
                extracted=extracted,
                texto=texto,
                fuente=fuente,
                autor=autor,
                fecha=fecha,
                hora=hora,
            )

            return requerimiento_data

        except Exception as e:
            logger.error(f"Error transformando mensaje: {e}", exc_info=True)
            return cls._crear_resultado_vacio(
                texto, fuente, autor,
                error=f"Error inesperado: {str(e)}",
                fecha=fecha, hora=hora,
            )

    @classmethod
    def _mapear_campos(
        cls,
        extracted: Dict,
        texto: str,
        fuente: str,
        autor: str,
        fecha: Optional[str] = None,
        hora: Optional[str] = None,
    ) -> Dict:
        """
        Mapea los campos extraídos por DeepSeek a los campos del modelo.

        Args:
            extracted: Diccionario con datos extraídos por DeepSeek.
            texto: Texto original del mensaje.
            fuente: Fuente del mensaje.
            autor: Autor del mensaje.
            fecha: Fecha del mensaje en formato YYYY-MM-DD (opcional).
            hora: Hora del mensaje en formato HH:MM:SS (opcional).

        Returns:
            Dict listo para crear un Requerimiento.
        """
        condicion = cls._mapear_choice(
            extracted.get('condicion', ''),
            CondicionChoices,
            CondicionChoices.NO_ESPECIFICADO
        )

        tipo_propiedad = cls._mapear_choice(
            extracted.get('tipo_propiedad', ''),
            TipoPropiedadChoices,
            TipoPropiedadChoices.NO_ESPECIFICADO
        )

        moneda = cls._mapear_choice(
            extracted.get('presupuesto_moneda', ''),
            MonedaChoices,
            MonedaChoices.NO_ESPECIFICADO
        )

        forma_pago = cls._mapear_choice(
            extracted.get('presupuesto_forma_pago', ''),
            FormaPagoChoices,
            FormaPagoChoices.NO_ESPECIFICADO
        )

        cochera = cls._mapear_choice(
            extracted.get('cochera', ''),
            TernarioChoices,
            TernarioChoices.INDIFERENTE
        )
        ascensor = cls._mapear_choice(
            extracted.get('ascensor', ''),
            TernarioChoices,
            TernarioChoices.INDIFERENTE
        )
        amueblado = cls._mapear_choice(
            extracted.get('amueblado', ''),
            TernarioChoices,
            TernarioChoices.INDIFERENTE
        )

        # Usar fecha/hora del mensaje si están disponibles, sino timezone.now()
        if fecha:
            try:
                fecha_date = datetime.strptime(fecha, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                fecha_date = timezone.now().date()
        else:
            fecha_date = timezone.now().date()

        if hora:
            try:
                hora_time = datetime.strptime(hora, '%H:%M:%S').time()
            except (ValueError, TypeError):
                try:
                    hora_time = datetime.strptime(hora, '%H:%M').time()
                except (ValueError, TypeError):
                    hora_time = timezone.now().time()
        else:
            hora_time = timezone.now().time()

        # Determinar el nombre del agente con la prioridad correcta:
        # 1. Si el autor del encabezado NO es un teléfono, usar ese nombre
        # 2. Si es teléfono, usar lo que DeepSeek extrajo del cuerpo del mensaje
        # 3. Si DeepSeek no encontró nombre, usar el teléfono como fallback
        nombre_agente = autor
        if cls._es_telefono(autor):
            nombre_agente = extracted.get('agente', '') or autor

        data = {
            'fuente': cls._mapear_fuente(fuente),
            'fecha': fecha_date,
            'hora': hora_time,
            'agente': nombre_agente,
            'tipo_original': 'EXTRACCION_WHATSAPP',
            'condicion': condicion,
            'tipo_propiedad': tipo_propiedad,
            'distritos': extracted.get('distritos', ''),
            'presupuesto_monto': cls._parsear_decimal(
                extracted.get('presupuesto_monto')
            ),
            'presupuesto_moneda': moneda,
            'presupuesto_forma_pago': forma_pago,
            'habitaciones': cls._parsear_entero(
                extracted.get('habitaciones')
            ),
            'banos': cls._parsear_entero(
                extracted.get('banos')
            ),
            'cochera': cochera,
            'ascensor': ascensor,
            'amueblado': amueblado,
            'area_m2': cls._parsear_entero(
                extracted.get('area_m2')
            ),
            'piso_preferencia': extracted.get('piso_preferencia', ''),
            'caracteristicas_extra': extracted.get('caracteristicas_extra', ''),
            'agente_telefono': extracted.get('agente_telefono', ''),
            'requerimiento': texto,
        }

        return data

    @classmethod
    def _mapear_choice(cls, valor: str, choices_class, default):
        """
        Mapea un valor string a una choice de Django.

        Args:
            valor: Valor a mapear.
            choices_class: Clase TextChoices.
            default: Valor por defecto si no hay match.

        Returns:
            Valor de la choice.
        """
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

    @classmethod
    def _mapear_fuente(cls, fuente: str) -> str:
        """
        Mapea el nombre del grupo WhatsApp a un valor de FuenteChoices.

        Args:
            fuente: Nombre o identificador del grupo.

        Returns:
            Valor de FuenteChoices.
        """
        fuente_lower = fuente.lower().replace(' ', '_')

        for choice in FuenteChoices.values:
            if choice == fuente_lower:
                return choice

        # Si no hay match exacto, buscar parcial
        for choice in FuenteChoices.values:
            if choice in fuente_lower or fuente_lower in choice:
                return choice

        return FuenteChoices.OTRO

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

    @classmethod
    def _parsear_decimal(cls, valor) -> Optional[Decimal]:
        """Convierte un valor a Decimal de forma segura."""
        if valor is None:
            return None
        try:
            return Decimal(str(valor))
        except (ValueError, TypeError, InvalidOperation):
            return None

    @classmethod
    def _parsear_entero(cls, valor) -> Optional[int]:
        """Convierte un valor a entero de forma segura."""
        if valor is None:
            return None
        try:
            return int(float(str(valor)))
        except (ValueError, TypeError):
            return None

    @classmethod
    def _crear_resultado_vacio(
        cls,
        texto: str,
        fuente: str,
        autor: str,
        error: str = '',
        es_valido: bool = False,
        fecha: Optional[str] = None,
        hora: Optional[str] = None,
    ) -> Dict:
        """
        Crea un resultado vacío para cuando la transformación falla.

        Args:
            texto: Texto original.
            fuente: Fuente del mensaje.
            autor: Autor del mensaje.
            error: Mensaje de error.
            es_valido: Si el mensaje es un requerimiento válido.
            fecha: Fecha del mensaje en formato YYYY-MM-DD (opcional).
            hora: Hora del mensaje en formato HH:MM:SS (opcional).

        Returns:
            Dict con estructura mínima.
        """
        # Usar fecha/hora del mensaje si están disponibles
        if fecha:
            try:
                fecha_date = datetime.strptime(fecha, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                fecha_date = timezone.now().date()
        else:
            fecha_date = timezone.now().date()

        if hora:
            try:
                hora_time = datetime.strptime(hora, '%H:%M:%S').time()
            except (ValueError, TypeError):
                try:
                    hora_time = datetime.strptime(hora, '%H:%M').time()
                except (ValueError, TypeError):
                    hora_time = timezone.now().time()
        else:
            hora_time = timezone.now().time()

        return {
            'fuente': cls._mapear_fuente(fuente),
            'fecha': fecha_date,
            'hora': hora_time,
            'agente': autor,
            'tipo_original': 'EXTRACCION_WHATSAPP',
            'condicion': CondicionChoices.NO_ESPECIFICADO,
            'tipo_propiedad': TipoPropiedadChoices.NO_ESPECIFICADO,
            'distritos': '',
            'requerimiento': texto,
            '_error': error,
            '_es_valido': es_valido,
        }
