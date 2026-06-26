"""
HybridMatchingSkill — Skill única de matching híbrido.

Pipeline: FAISS semántico → post-filtrado por field_values → scoring estructural → combinación.
Opera 100% sobre IntelligenceDocument + FAISS. No consulta dbpropify_be directamente.

Arquitectura: plans/matching_hibrido_embeddings.md
"""

from __future__ import annotations

import logging
import numpy as np
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from .base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)


# ── Auxiliares ────────────────────────────────────────────────────────────────

# Mapeo de amenity keywords del requerimiento a campos booleanos en field_values
_AMENITY_MAP = {
    'piscina': 'has_pool',
    'pileta': 'has_pool',
    'jardin': 'has_garden',
    'jardín': 'has_garden',
    'bbq': 'has_bbq',
    'parrilla': 'has_bbq',
    'terraza': 'has_terrace',
    'azotea': 'has_terrace',
    'aire acondicionado': 'has_air_conditioning',
    'aa': 'has_air_conditioning',
    'lavandería': 'has_laundry_area',
    'lavanderia': 'has_laundry_area',
    'cuarto de servicio': 'has_service_room',
    'servicio': 'has_service_room',
    'ascensor': 'has_elevator',
    'elevador': 'has_elevator',
    'seguridad': 'has_security',
    'mascotas': 'pet_friendly',
    'pet friendly': 'pet_friendly',
    'estacionamiento': 'garage_spaces',
    'cochera': 'garage_spaces',
    'garage': 'garage_spaces',
}

# Tipos de operación: 1=Venta, 2=Permuta, 3=Alquiler
_OPERATION_TIPO_MAP = {
    'compra': (1, 2),
    'venta': (1, 2),
    'alquiler': (3,),
    'anticresis': (3,),
}


def _normalize_str(val: Any) -> str:
    """Normaliza un valor a string limpio en minúsculas."""
    if val is None:
        return ''
    return str(val).lower().strip()


def _to_decimal(val: Any) -> Optional[Decimal]:
    """Convierte un valor a Decimal de forma segura."""
    if val is None:
        return None
    try:
        return Decimal(str(val))
    except (ValueError, TypeError):
        return None


def _extract_moneda(field_values: dict) -> str:
    """Extrae la moneda de field_values."""
    currency_name = _normalize_str(field_values.get('currency_name', ''))
    if currency_name in ('dólares', 'usd', 'dolares', '$'):
        return 'USD'
    if currency_name in ('soles', 'pen', 's/.'):
        return 'PEN'
    # Fallback a currency_id
    currency_id = field_values.get('currency_id')
    if currency_id == 1:
        return 'USD'
    if currency_id == 2:
        return 'PEN'
    return 'PEN'


# ── HybridMatchingSkill ──────────────────────────────────────────────────────

class HybridMatchingSkill(BaseSkill):
    """
    Skill única de matching híbrido.

    Pipeline:
    1. Obtener requerimiento desde IntelligenceDocument (colección requerimientos_enbedados)
    2. Extraer su embedding precomputado
    3. Buscar en FAISS propiedadespropify (top-K=500)
    4. Post-filtrar por field_values (tipo, condicion, distrito, presupuesto)
    5. Scoring estructural desde field_values (10 factores ponderados)
    6. Combinar scores: score_final = alpha * struct + (1-alpha) * sem
    7. Ranking por score_final
    """

    name = "matching_hibrido"
    description = (
        "Matching híbrido oferta-demanda: busca propiedades compatibles con un requerimiento "
        "usando búsqueda semántica FAISS + filtros duros + scoring estructural. "
        "Recibe requerimiento_id y retorna propiedades rankeadas."
    )
    category = "crm"
    access_level = 1
    is_active = True

    parameters_schema = {
        'requerimiento_id': {
            'type': 'integer',
            'description': 'ID del requerimiento en la tabla requerimiento',
            'required': True,
        },
        'alpha': {
            'type': 'number',
            'description': 'Peso del scoring estructural (0-1). Default 0.6',
            'required': False,
        },
        'top_n': {
            'type': 'integer',
            'description': 'Número máximo de resultados a retornar. Default 20',
            'required': False,
        },
        'umbral_minimo': {
            'type': 'number',
            'description': 'Score mínimo (0-100) para incluir un match. Default 0',
            'required': False,
        },
    }

    # Pesos estructurales (configurados por el usuario)
    # Prioridad: distrito(30%), tipo(30%), precio(30%), otros 7 factores(10%)
    PESOS = {
        'distrito': 30,
        'tipo_propiedad': 30,
        'precio': 30,
        'area': 2,
        'habitaciones': 2,
        'amenities': 2,
        'banos': 1,
        'antiguedad': 1,
        'estacionamiento': 1,
        'ascensor': 1,
    }

    TOLERANCIA_NUMERICA = 0.10  # 10%
    ALPHA_DEFAULT = 0.6
    FAISS_TOP_K = 500
    FAISS_DIMENSION = 1024

    # ── Validación ─────────────────────────────────────────────────────────

    def validate_params(self, params: Dict[str, Any]) -> bool:
        if not params:
            return False
        requerimiento_id = params.get('requerimiento_id')
        if requerimiento_id is None:
            return False
        try:
            int(str(requerimiento_id))
            return True
        except (ValueError, TypeError):
            return False

    # ── Ejecución principal ────────────────────────────────────────────────

    def execute(
        self,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> SkillResult:
        """
        Ejecuta matching híbrido completo.

        Args:
            params: {
                'requerimiento_id': int,
                'alpha': float (opcional, default 0.6),
                'top_n': int (opcional, default 20),
                'umbral_minimo': float (opcional, default 0),
            }
            context: Contexto opcional

        Returns:
            SkillResult con matches rankeados
        """
        try:
            if not self.validate_params(params):
                return SkillResult.error(
                    message="Parámetro requerido: requerimiento_id",
                    skill_name=self.name,
                )

            requerimiento_id = int(params['requerimiento_id'])
            alpha = float(params.get('alpha', self.ALPHA_DEFAULT))
            top_n = int(params.get('top_n', 20))
            umbral_minimo = float(params.get('umbral_minimo', 0.0))

            # ── Paso 1: Obtener requerimiento embeddeado ────────────────
            req_doc, req_data = self._get_requerimiento_doc(requerimiento_id)
            if req_doc is None:
                return SkillResult.error(
                    message=f"Requerimiento {requerimiento_id} no encontrado en colección requerimientos_enbedados",
                    skill_name=self.name,
                )

            # ── Paso 2-5: Búsqueda híbrida ─────────────────────────────
            matches = self._hybrid_search(
                req_embedding=req_doc.embedding,
                params=params,
                req_data=req_data,
                alpha=alpha,
            )

            if not matches:
                return SkillResult.ok(
                    data={'matches': [], 'total': 0},
                    message=f"No se encontraron propiedades compatibles para requerimiento {requerimiento_id}",
                    metadata={
                        'requerimiento_id': requerimiento_id,
                        'alpha': alpha,
                        'modo': 'hybrid',
                    },
                    skill_name=self.name,
                )

            # ── Paso 6: Ranking ────────────────────────────────────────
            matches.sort(key=lambda x: x['score_total'], reverse=True)
            for i, m in enumerate(matches, 1):
                m['ranking'] = i

            # ── Filtrar por umbral ─────────────────────────────────────
            if umbral_minimo > 0:
                matches = [m for m in matches if m['score_total'] >= umbral_minimo]

            top_matches = matches[:top_n]

            return SkillResult.ok(
                data={
                    'matches': top_matches,
                    'total': len(matches),
                    'requerimiento_id': requerimiento_id,
                },
                message=(
                    f"Matching híbrido completado: {len(matches)} propiedades compatibles, "
                    f"mostrando las {len(top_matches)} mejores."
                ),
                metadata={
                    'requerimiento_id': requerimiento_id,
                    'alpha': alpha,
                    'modo': 'hybrid',
                    'faiss_k': self.FAISS_TOP_K,
                    'total_matches': len(matches),
                    'top_n': top_n,
                    'umbral_minimo': umbral_minimo,
                },
                skill_name=self.name,
            )

        except Exception as e:
            logger.exception(f"[HybridMatchingSkill] Error: {e}")
            return SkillResult.error(
                message=f"Error interno: {str(e)}",
                skill_name=self.name,
            )

    # ── Paso 1: Obtener requerimiento ─────────────────────────────────────

    def _get_requerimiento_doc(
        self, requerimiento_id: int
    ) -> Tuple[Optional[Any], Optional[Dict]]:
        """
        Obtiene el IntelligenceDocument del requerimiento y datos adicionales.

        Returns:
            Tuple[IntelligenceDocument|None, Dict|None]
        """
        from ..models import IntelligenceDocument

        try:
            doc = IntelligenceDocument.objects.get(
                collection__name='requerimientos_enbedados',
                source_id=str(requerimiento_id),
            )

            # Obtener datos adicionales del requerimiento desde el modelo Django
            # para filtros/scoring que requieren datos no embeddeados
            from requerimientos.models import Requerimiento
            try:
                req = Requerimiento.objects.get(id=requerimiento_id)
                req_data = {
                    'id': req.id,
                    'condicion': req.condicion or '',
                    'tipo_propiedad': req.tipo_propiedad or '',
                    'distritos': req.distritos or '',
                    'distritos_lista': req.distritos_lista if hasattr(req, 'distritos_lista') else [],
                    'presupuesto_monto': float(req.presupuesto_monto) if req.presupuesto_monto else None,
                    'presupuesto_moneda': (req.presupuesto_moneda or '').upper(),
                    'habitaciones': req.habitaciones,
                    'banos': req.banos,
                    'area_m2': float(req.area_m2) if req.area_m2 else None,
                    'ascensor': (req.ascensor or '').lower(),
                    'amueblado': (req.amueblado or '').lower(),
                    'cochera': (req.cochera or '').lower(),
                    'caracteristicas_extra': req.caracteristicas_extra or '',
                }
            except Requerimiento.DoesNotExist:
                req_data = {}

            return doc, req_data

        except IntelligenceDocument.DoesNotExist:
            logger.warning(
                f"Requerimiento {requerimiento_id} no tiene IntelligenceDocument "
                f"en colección requerimientos_enbedados"
            )
            return None, None

    # ── Pasos 2-5: Búsqueda híbrida ───────────────────────────────────────

    def _hybrid_search(
        self,
        req_embedding: bytes,
        params: Dict[str, Any],
        req_data: Dict[str, Any],
        alpha: float = 0.6,
    ) -> List[Dict]:
        """
        Búsqueda FAISS + post-filtrado + scoring estructural + combinación.

        Args:
            req_embedding: Embedding precomputado del requerimiento (bytes)
            params: Parámetros originales de la skill
            req_data: Datos del requerimiento
            alpha: Peso estructural (0-1)

        Returns:
            Lista de matches con score combinado
        """
        from ..services.faiss_index import FAISSIndexManager

        # ── Paso 2: Búsqueda FAISS ─────────────────────────────────────
        faiss_idx = FAISSIndexManager.get_instance(
            'propiedadespropify', self.FAISS_DIMENSION
        )
        if not faiss_idx.is_loaded:
            logger.warning("[HybridMatchingSkill] FAISS no cargado para propiedadespropify")
            return []

        query_vector = np.frombuffer(req_embedding, dtype=np.float32)
        faiss_results = faiss_idx.search(query_vector, top_k=self.FAISS_TOP_K)

        if not faiss_results:
            logger.info("[HybridMatchingSkill] Sin resultados FAISS")
            return []

        # ── Batch load: todos los documentos FAISS de una sola vez ─────
        from ..models import IntelligenceDocument

        doc_ids = [r['document_id'] for r in faiss_results]
        docs_qs = IntelligenceDocument.objects.filter(id__in=doc_ids).only(
            'id', 'source_id', 'field_values'
        )
        docs_map = {str(d.id): d for d in docs_qs}

        # ── Post-filtrado + scoring ────────────────────────────────────
        matches = []
        for fr in faiss_results:
            doc = docs_map.get(fr['document_id'])
            if not doc:
                continue

            fv = doc.field_values or {}
            # FAISS retorna distancia L2, no similitud coseno.
            # Para vectores normalizados: cos_sim = 1 - l2²/2
            l2_dist = fr['similarity']
            score_sem = 1.0 - (l2_dist * l2_dist) / 2.0
            if score_sem < 0:
                score_sem = 0.0

            # ── Paso 3: Filtros duros sobre field_values ────────────────
            if not self._pasa_filtros(fv, req_data):
                continue

            # ── Paso 4: Scoring estructural desde field_values ──────────
            score_struct, score_detalle = self._calcular_scoring(fv, req_data)

            # ── Paso 5: Combinar scores ─────────────────────────────────
            # score_struct: 0-100 -> normalizar a 0-1
            # score_sem: 0-1 (de FAISS con Inner Product en vectores normalizados)
            score_final = (alpha * float(score_struct) / 100.0 + (1 - alpha) * score_sem) * 100.0

            matches.append({
                'property_id': self._safe_int(doc.source_id),
                'property_doc_id': str(doc.id),
                'field_values': fv,
                'score_total': round(score_final, 2),
                'score_structural': round(float(score_struct), 2),
                'score_semantico': round(score_sem, 4),
                'score_detalle': {
                    **{k: round(float(v), 4) for k, v in score_detalle.items()},
                    'semantico': round(score_sem, 4),
                    'alpha': alpha,
                },
            })

        return matches

    # ── Paso 3: Filtros duros sobre field_values ─────────────────────────

    def _pasa_filtros(self, fv: Dict, req_data: Dict) -> bool:
        """
        Aplica filtros duros sobre field_values del IntelligenceDocument.

        Filtros:
        1. Tipo de propiedad (property_type_name)
        2. Condición (operation_type_name)
        3. Distrito (district_name)
        4. Presupuesto (price vs presupuesto_monto)
        """
        if not req_data:
            return True

        # ── 1. Tipo de propiedad ───────────────────────────────────────
        tipo_req = _normalize_str(req_data.get('tipo_propiedad', ''))
        if tipo_req and tipo_req not in ('no_especificado', 'no especificado', 'todos', 'cualquiera', ''):
            tipo_prop = _normalize_str(fv.get('property_type_name', ''))
            if tipo_prop and tipo_prop != tipo_req:
                # Intentar también por property_type_id (si field_values lo tiene)
                tipo_id_req = self._tipo_propiedad_name_to_id(tipo_req)
                tipo_id_prop = fv.get('property_type_id')
                if tipo_id_req is None or tipo_id_prop is None or tipo_id_prop != tipo_id_req:
                    return False

        # ── 2. Condición (compra/alquiler) ─────────────────────────────
        condicion_req = _normalize_str(req_data.get('condicion', ''))
        if condicion_req and condicion_req not in ('no_especificado', ''):
            op_name = _normalize_str(fv.get('operation_type_name', ''))
            op_id = fv.get('operation_type_id')

            if condicion_req in ('compra', 'venta'):
                # Aceptar operation_type_id 1 (Venta) o 2 (Permuta)
                if op_id is not None:
                    if op_id not in (1, 2):
                        return False
                elif op_name and op_name not in ('venta', 'compra', 'permuta'):
                    return False
            elif condicion_req in ('alquiler', 'anticresis'):
                if op_id is not None:
                    if op_id != 3:
                        return False
                elif op_name and op_name != 'alquiler':
                    return False

        # ── 3. Distrito ────────────────────────────────────────────────
        distritos_lista = req_data.get('distritos_lista', [])
        if distritos_lista:
            distrito_prop = _normalize_str(fv.get('district_name', ''))
            if distrito_prop:
                coincide = any(
                    d.strip().lower() == distrito_prop
                    or distrito_prop in d.strip().lower()
                    or d.strip().lower() in distrito_prop
                    for d in distritos_lista if d.strip()
                )
                if not coincide:
                    return False

        # ── 4. Presupuesto ─────────────────────────────────────────────
        presupuesto_monto = req_data.get('presupuesto_monto')
        if presupuesto_monto:
            precio = fv.get('price')
            if precio is not None:
                try:
                    precio = float(precio)
                    presupuesto = float(presupuesto_monto)

                    # Convertir monedas si es necesario
                    moneda_req = req_data.get('presupuesto_moneda', 'PEN')
                    moneda_prop = _extract_moneda(fv)

                    if moneda_req != moneda_prop:
                        precio = self._convertir_moneda(precio, moneda_prop, moneda_req)

                    limite_maximo = presupuesto * 1.10  # 10% de tolerancia
                    if precio > limite_maximo:
                        return False
                except (ValueError, TypeError):
                    pass

        return True

    # ── Paso 4: Scoring estructural ───────────────────────────────────────

    def _calcular_scoring(
        self, fv: Dict, req_data: Dict
    ) -> Tuple[Decimal, Dict[str, Decimal]]:
        """
        Calcula score estructural (0-100) desde field_values.

        Args:
            fv: field_values del IntelligenceDocument de la propiedad
            req_data: Datos del requerimiento

        Returns:
            Tuple[score_total Decimal(0-100), score_detalle Dict[str, Decimal]]
        """
        score_detalle = {}
        score_total = Decimal('0.0')

        scorers = [
            ('precio', self._score_precio),
            ('area', self._score_area),
            ('habitaciones', self._score_habitaciones),
            ('banos', self._score_banos),
            ('antiguedad', self._score_antiguedad),
            ('estacionamiento', self._score_estacionamiento),
            ('distrito', self._score_distrito),
            ('amenities', self._score_amenities),
            ('ascensor', self._score_ascensor),
            ('tipo_propiedad', self._score_tipo_propiedad),
        ]

        for factor_name, scorer_fn in scorers:
            try:
                s = scorer_fn(fv, req_data)
            except Exception as e:
                logger.warning(f"[HybridMatchingSkill] Error en score '{factor_name}': {e}")
                s = Decimal('0.5')

            score_detalle[factor_name] = s
            peso = Decimal(str(self.PESOS.get(factor_name, 0)))
            score_total += s * peso / Decimal('100')

        score_total = score_total * Decimal('100.0')
        score_total = max(Decimal('0.0'), min(Decimal('100.0'), score_total))

        return score_total, score_detalle

    # ── Scorers individuales ──────────────────────────────────────────────

    def _score_precio(self, fv: Dict, req_data: Dict) -> Decimal:
        """Score 0-1: qué tan bien el precio calza con el presupuesto."""
        presupuesto_monto = req_data.get('presupuesto_monto')
        price = fv.get('price')

        if not presupuesto_monto or price is None:
            return Decimal('0.5')

        try:
            presupuesto = Decimal(str(presupuesto_monto))
            precio = Decimal(str(price))

            moneda_req = req_data.get('presupuesto_moneda', 'PEN')
            moneda_prop = _extract_moneda(fv)

            if moneda_req != moneda_prop:
                precio = Decimal(str(self._convertir_moneda(
                    float(precio), moneda_prop, moneda_req
                )))

            if precio <= presupuesto:
                return Decimal('1.0')

            limite_maximo = presupuesto * Decimal('1.10')
            if precio > limite_maximo:
                return Decimal('0.0')

            rango_tolerancia = limite_maximo - presupuesto
            if rango_tolerancia > 0:
                diferencia = precio - presupuesto
                return Decimal('1.0') - diferencia / rango_tolerancia
            return Decimal('0.0')

        except (ValueError, TypeError, InvalidOperation):
            return Decimal('0.5')

    def _score_area(self, fv: Dict, req_data: Dict) -> Decimal:
        """Score 0-1: qué tan bien el área calza."""
        area_m2 = req_data.get('area_m2')
        built_area = fv.get('built_area')

        if not area_m2 or not built_area:
            return Decimal('0.5')

        try:
            area_deseada = Decimal(str(area_m2))
            area_propiedad = Decimal(str(built_area))

            if area_propiedad == 0:
                return Decimal('0.0')

            diferencia_porcentual = abs(area_propiedad - area_deseada) / area_deseada

            if diferencia_porcentual <= Decimal(str(self.TOLERANCIA_NUMERICA)):
                return Decimal('1.0')
            if diferencia_porcentual > Decimal('0.5'):
                return Decimal('0.0')

            tolerancia = Decimal(str(self.TOLERANCIA_NUMERICA))
            return Decimal('1.0') - (diferencia_porcentual - tolerancia) / Decimal('0.4')

        except (ValueError, TypeError, InvalidOperation, ZeroDivisionError):
            return Decimal('0.5')

    def _score_habitaciones(self, fv: Dict, req_data: Dict) -> Decimal:
        """Score 0-1: coincidencia de habitaciones."""
        habitaciones_req = req_data.get('habitaciones')
        bedrooms = fv.get('bedrooms')

        if not habitaciones_req or not bedrooms:
            return Decimal('0.5')

        try:
            deseadas = int(habitaciones_req)
            disponibles = int(bedrooms)

            if disponibles >= deseadas:
                return Decimal('1.0')
            diferencia = deseadas - disponibles
            if diferencia >= 3:
                return Decimal('0.0')
            return Decimal('1.0') - Decimal(str(diferencia)) / Decimal('3.0')

        except (ValueError, TypeError):
            return Decimal('0.5')

    def _score_banos(self, fv: Dict, req_data: Dict) -> Decimal:
        """Score 0-1: coincidencia de baños."""
        banos_req = req_data.get('banos')
        bathrooms = fv.get('bathrooms')

        if not banos_req or not bathrooms:
            return Decimal('0.5')

        try:
            deseados = int(banos_req)
            disponibles = int(bathrooms)

            if disponibles >= deseados:
                return Decimal('1.0')
            diferencia = deseados - disponibles
            if diferencia >= 2:
                return Decimal('0.0')
            return Decimal('1.0') - Decimal(str(diferencia)) / Decimal('2.0')

        except (ValueError, TypeError):
            return Decimal('0.5')

    def _score_antiguedad(self, fv: Dict, req_data: Dict) -> Decimal:
        """Score 0-1: antigüedad de la propiedad."""
        antiquity = fv.get('antiquity_years')

        if not antiquity:
            return Decimal('0.5')

        try:
            antiguedad = int(antiquity)
            if antiguedad <= 5:
                return Decimal('1.0')
            elif antiguedad <= 15:
                return Decimal('0.7')
            elif antiguedad <= 30:
                return Decimal('0.4')
            else:
                return Decimal('0.1')
        except (ValueError, TypeError):
            return Decimal('0.5')

    def _score_estacionamiento(self, fv: Dict, req_data: Dict) -> Decimal:
        """Score 0-1: disponibilidad de estacionamiento."""
        cochera_req = _normalize_str(req_data.get('cochera', ''))

        if not cochera_req or cochera_req == 'indiferente':
            return Decimal('0.5')

        garage_spaces = fv.get('garage_spaces', 0)
        tiene_garage = bool(garage_spaces and int(garage_spaces) > 0)

        if cochera_req == 'si':
            return Decimal('1.0') if tiene_garage else Decimal('0.0')
        elif cochera_req == 'no':
            return Decimal('0.0') if tiene_garage else Decimal('1.0')

        return Decimal('0.5')

    def _score_distrito(self, fv: Dict, req_data: Dict) -> Decimal:
        """Score 0-1: coincidencia de distrito."""
        distritos_lista = req_data.get('distritos_lista', [])
        district_name = _normalize_str(fv.get('district_name', ''))

        if not distritos_lista or not district_name:
            return Decimal('0.5')

        for d in distritos_lista:
            d_clean = d.strip().lower()
            if d_clean == district_name or d_clean in district_name or district_name in d_clean:
                return Decimal('1.0')

        return Decimal('0.8')

    def _score_amenities(self, fv: Dict, req_data: Dict) -> Decimal:
        """Score 0-1: qué amenities coinciden."""
        extras = req_data.get('caracteristicas_extra', '')
        if not extras:
            return Decimal('0.5')

        palabras = [p.strip() for p in extras.replace(',', ' ').split() if len(p.strip()) > 2]
        if not palabras:
            return Decimal('0.5')

        coincidencias = 0
        total_buscadas = 0

        for palabra in palabras:
            campo = _AMENITY_MAP.get(palabra.lower())
            if campo:
                total_buscadas += 1
                val = fv.get(campo)
                if campo == 'garage_spaces':
                    if val and int(val) > 0:
                        coincidencias += 1
                elif val is True:
                    coincidencias += 1

        if total_buscadas > 0:
            ratio = coincidencias / total_buscadas
            return Decimal('0.5') + Decimal(str(ratio)) * Decimal('0.5')

        return Decimal('0.5')

    def _score_ascensor(self, fv: Dict, req_data: Dict) -> Decimal:
        """Score 0-1: disponibilidad de ascensor."""
        ascensor_req = _normalize_str(req_data.get('ascensor', ''))

        if not ascensor_req or ascensor_req == 'indiferente':
            return Decimal('0.5')

        has_elevator = fv.get('has_elevator')

        if ascensor_req == 'si':
            return Decimal('1.0') if has_elevator is True else Decimal('0.0')
        elif ascensor_req == 'no':
            return Decimal('1.0') if (has_elevator is False or has_elevator is None) else Decimal('0.0')

        return Decimal('0.5')

    def _score_tipo_propiedad(self, fv: Dict, req_data: Dict) -> Decimal:
        """Score 0-1: coincide el tipo de propiedad."""
        tipo_req = _normalize_str(req_data.get('tipo_propiedad', ''))
        if not tipo_req or tipo_req in ('no_especificado', 'no especificado', 'todos', 'cualquiera', ''):
            return Decimal('0.5')

        tipo_prop = _normalize_str(fv.get('property_type_name', ''))
        if tipo_prop and tipo_prop == tipo_req:
            return Decimal('1.0')

        # Intentar por ID
        tipo_id_req = self._tipo_propiedad_name_to_id(tipo_req)
        tipo_id_prop = fv.get('property_type_id')
        if tipo_id_req is not None and tipo_id_prop is not None and tipo_id_prop == tipo_id_req:
            return Decimal('1.0')

        return Decimal('0.5')

    # ── Helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _safe_int(val: Any) -> int:
        """Convierte un valor a int de forma segura."""
        try:
            return int(float(str(val)))
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _convertir_moneda(
        monto: float, moneda_origen: str, moneda_destino: str
    ) -> float:
        """
        Convierte entre PEN y USD usando tipo de cambio fijo.
        Fuente: tipo de cambio referencial (actualizado periódicamente).
        """
        if moneda_origen == moneda_destino:
            return monto

        # Tipo de cambio fijo (1 USD = 3.75 PEN)
        TIPO_CAMBIO = 3.75

        if moneda_origen == 'USD' and moneda_destino == 'PEN':
            return monto * TIPO_CAMBIO
        elif moneda_origen == 'PEN' and moneda_destino == 'USD':
            return monto / TIPO_CAMBIO
        return monto

    @staticmethod
    def _tipo_propiedad_name_to_id(name: str) -> Optional[int]:
        """
        Resuelve nombre de tipo de propiedad a ID.
        Cachea resultados para no consultar BD repetidamente.
        """
        _CACHE = getattr(HybridMatchingSkill, '_TIPO_CACHE', None)
        if _CACHE is None:
            try:
                from django.db import connections
                with connections['propifai'].cursor() as cursor:
                    cursor.execute("SELECT id, name FROM property_types")
                    rows = cursor.fetchall()
                    HybridMatchingSkill._TIPO_CACHE = {
                        _normalize_str(row[1]): row[0] for row in rows
                    }
            except Exception as e:
                logger.warning(f"[HybridMatchingSkill] Error cargando property_types: {e}")
                HybridMatchingSkill._TIPO_CACHE = {}

        name_norm = _normalize_str(name)
        return HybridMatchingSkill._TIPO_CACHE.get(name_norm)
