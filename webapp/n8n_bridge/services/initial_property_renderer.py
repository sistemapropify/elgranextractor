"""Plantillas literales aprobadas para la respuesta nocturna inicial."""

from decimal import Decimal


TEMPLATES = {
    "casa": "¡Gracias por escribirnos! 😊\nEsta casa se encuentra en {location}, tiene {features} y un precio de {price}.\n\nEn este momento estamos fuera del horario de atención. Apenas uno de nuestros asesores esté disponible, continuará la conversación contigo.\n\nMientras tanto, ¿qué es indispensable para ti en tu nueva casa? Así podemos decirte si esta propiedad cumple con lo que buscas.",
    "departamento": "¡Gracias por escribirnos! 😊\nEste departamento está ubicado en {location}, cuenta con {features} y tiene un precio de {price}.\n\nEn este momento estamos fuera del horario de atención. Apenas uno de nuestros asesores esté disponible, continuará la conversación contigo.\n\nMientras tanto, ¿qué es indispensable para ti en un departamento? Así puedo decirte si esta propiedad cumple con lo que necesitas.",
    "terreno": "¡Gracias por escribirnos! 😊\nEste terreno se encuentra en {location}, tiene un área de {area} y un precio de {price}.\n\nEn este momento estamos fuera del horario de atención. Apenas uno de nuestros asesores esté disponible, continuará la conversación contigo.\n\nMientras tanto, ¿estás pensando en construir tu vivienda o te interesa conocer los parámetros para desarrollar un proyecto?",
    "local_comercial": "¡Gracias por escribirnos! 😊\nEste local comercial está ubicado en {location}, cuenta con {features} y tiene un precio de {price}.\n\nEn este momento estamos fuera del horario de atención. Apenas uno de nuestros asesores esté disponible, continuará la conversación contigo.\n\nMientras tanto, ¿qué tipo de negocio tienes pensado y qué características son indispensables para ti? Así puedo decirte si este local se adapta a lo que buscas.",
    "otro": "¡Gracias por escribirnos! 😊\nEsta propiedad está ubicada en {location}, cuenta con {features} y tiene un precio de {price}.\n\nEn este momento estamos fuera del horario de atención. Apenas uno de nuestros asesores esté disponible, continuará la conversación contigo.\n\nMientras tanto, ¿qué es indispensable para ti en esta propiedad? Así podemos decirte si cumple con lo que buscas.",
}


def format_number(value):
    number = Decimal(str(value))
    return f"{int(number):,}" if number == number.to_integral() else f"{number:,.2f}".rstrip("0").rstrip(".")


def format_price(price):
    symbol = "US$" if price["currency"] == "USD" else "S/"
    return f"{symbol} {format_number(price['amount'])}"


def format_feature(feature):
    value, field = feature["value"], feature["field"]
    if field == "bedrooms":
        return f"{value} dormitorio" if int(value) == 1 else f"{value} dormitorios"
    if field == "bathrooms":
        return f"{value} baño" if int(value) == 1 else f"{value} baños"
    if field == "garage_spaces":
        return f"{value} estacionamiento" if int(value) == 1 else f"{value} estacionamientos"
    if field == "built_area":
        return f"{format_number(value)} m² de área construida"
    if field == "land_area":
        return f"{format_number(value)} m²"
    raise ValueError(f"Característica no permitida: {field}")


def render_initial_response(data, config=None):
    values = {"location": data["location"], "price": format_price(data["price"])}
    if data["property_type"] == "terreno":
        values["area"] = format_feature(data["features"][0])
    else:
        values["features"] = " y ".join(format_feature(item) for item in data["features"][:2])

    # Plantillas personalizadas (editables desde el dashboard) si existen.
    templates = TEMPLATES
    if config is not None:
        custom = getattr(config, "message_templates", None)
        if isinstance(custom, dict) and custom.get(data["property_type"]):
            templates = custom
    return templates[data["property_type"]].format(**values)
