"""Consulta exacta de datos para la primera respuesta nocturna de WhatsApp."""

import re
import unicodedata

from django.db import connections

from ..base import BaseSkill, SkillResult


TYPE_ALIASES = {
    "casa": "casa",
    "departamento": "departamento",
    "departamentos": "departamento",
    "depa": "departamento",
    "terreno": "terreno",
    "local": "local_comercial",
    "local comercial": "local_comercial",
    "localcomercial": "local_comercial",
}


def _plain(value):
    value = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in value if not unicodedata.combining(ch)).lower().strip()


def normalize_property_type(value):
    normalized = re.sub(r"\s+", " ", _plain(value))
    if normalized in TYPE_ALIASES:
        return TYPE_ALIASES[normalized]
    for candidate, canonical in TYPE_ALIASES.items():
        if candidate in normalized:
            return canonical
    return ""


def normalize_currency(value):
    normalized = _plain(value)
    if normalized in {"usd", "dolar", "dolares", "us$", "$"} or "dolar" in normalized:
        return "USD"
    if normalized in {"pen", "sol", "soles", "s/"} or "sol" in normalized:
        return "PEN"
    return ""


def public_location(row):
    urbanization = str(row.get("urbanization_name") or "").strip()
    district = str(row.get("district_name") or "").strip()
    if urbanization and district and _plain(urbanization) != _plain(district):
        return f"{urbanization}, {district}"
    return urbanization or str(row.get("display_address") or "").strip() or district


class InformacionInicialPropiedadSkill(BaseSkill):
    name = "informacion_inicial_propiedad"
    description = "Obtiene datos verificados de una propiedad por código exacto para la respuesta inicial de WhatsApp"
    category = "busqueda"
    access_level = 1
    parameters_schema = {
        "property_code": {
            "type": "string",
            "required": True,
            "description": "Código exacto, por ejemplo PROP000261",
        }
    }

    def validate_params(self, params):
        return bool(re.fullmatch(r"PROP\d{6,9}", str(params.get("property_code") or "").upper()))

    def execute(self, params, context=None):
        if not self.validate_params(params):
            return SkillResult.error("Código de propiedad inválido", {"reason_code": "NO_PROPERTY_CODE"}, self.name)

        code = str(params["property_code"]).upper()
        query = """
            SELECT TOP 2
                p.id, p.code, p.title, p.price, p.display_address,
                p.description, p.is_visible, pt.name AS property_type_name,
                c.name AS currency_name, d.name AS district_name,
                u.name AS urbanization_name, ps.bedrooms, ps.bathrooms,
                ps.built_area, ps.land_area, ps.garage_spaces,
                st.name AS property_status_name
            FROM property p
            LEFT JOIN property_specs ps ON ps.property_id = p.id
            LEFT JOIN property_type pt ON pt.id = p.property_type_id
            LEFT JOIN currency c ON c.id = p.currency_id
            LEFT JOIN district d ON d.id = p.district_id
            LEFT JOIN urbanization u ON u.id = p.urbanization_id
            LEFT JOIN property_status st ON st.id = p.property_status_id
            WHERE UPPER(p.code) = %s
        """
        try:
            with connections["propifai"].cursor() as cursor:
                cursor.execute(query, [code])
                rows = cursor.fetchall()
                columns = [item[0] for item in cursor.description]
        except Exception as exc:
            return SkillResult.error(
                "No se pudo consultar el inventario",
                {"reason_code": "INTERNAL_ERROR", "error_type": type(exc).__name__},
                self.name,
            )

        if not rows:
            return SkillResult.error("Propiedad no encontrada", {"reason_code": "PROPERTY_NOT_FOUND"}, self.name)
        if len(rows) != 1:
            return SkillResult.error("Código duplicado", {"reason_code": "PROPERTY_NOT_FOUND"}, self.name)

        row = dict(zip(columns, rows[0]))
        property_type = normalize_property_type(row.get("property_type_name"))
        if not property_type:
            return SkillResult.error(
                "Tipo de propiedad no soportado",
                {"reason_code": "UNSUPPORTED_PROPERTY_TYPE"},
                self.name,
            )

        feature_order = {
            "casa": ("bedrooms", "built_area", "bathrooms"),
            "departamento": ("bedrooms", "built_area", "bathrooms"),
            "terreno": ("land_area",),
            "local_comercial": ("built_area", "bathrooms", "garage_spaces"),
        }[property_type]
        features = [
            {"field": field, "value": row[field], "source": f"property_specs.{field}"}
            for field in feature_order
            if row.get(field) is not None
        ][:2]

        data = {
            "property_id": int(row["id"]),
            "code": row["code"],
            "title": row.get("title") or "",
            "description": row.get("description") or "",
            "property_type": property_type,
            "location": public_location(row),
            "price": {
                "amount": row.get("price"),
                "currency": normalize_currency(row.get("currency_name")),
                "source": "property.price+currency.name",
            },
            "features": features,
            "is_visible": row.get("is_visible"),
            "property_status": row.get("property_status_name") or "",
        }
        return SkillResult.ok(data=data, metadata={"resolution": "exact_code"}, skill_name=self.name)
