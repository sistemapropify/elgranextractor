import requests
import json

# URL del endpoint
url = "http://127.0.0.1:8000/api/v1/intelligence/chat-workflows/"

# Definir el flow de compra-venta inmobiliaria
flow_data = {
    "name": "Flujo Compra-Venta Inmobiliaria",
    "description": "Flujo conversacional para clientes interesados en comprar o vender propiedades",
    "states": {
        "saludo": {
            "message": "¡Hola! Soy tu asistente inmobiliario. ¿Estás interesado en comprar o vender una propiedad?",
            "buttons": [
                {"text": "Comprar", "next_state": "comprar"},
                {"text": "Vender", "next_state": "vender"}
            ],
            "data_collection": []
        },
        "comprar": {
            "message": "¡Excelente! Vamos a encontrar la propiedad perfecta para ti. ¿Qué tipo de propiedad buscas?",
            "buttons": [
                {"text": "Casa", "next_state": "tipo_casa"},
                {"text": "Apartamento", "next_state": "tipo_apartamento"},
                {"text": "Terreno", "next_state": "tipo_terreno"}
            ],
            "data_collection": []
        },
        "tipo_casa": {
            "message": "¿Cuántas habitaciones necesitas?",
            "buttons": [],
            "data_collection": [
                {
                    "field": "habitaciones",
                    "type": "number",
                    "required": True,
                    "next_state": "presupuesto"
                }
            ]
        },
        "presupuesto": {
            "message": "¿Cuál es tu presupuesto aproximado?",
            "buttons": [],
            "data_collection": [
                {
                    "field": "presupuesto",
                    "type": "number",
                    "required": True,
                    "next_state": "ubicacion"
                }
            ]
        },
        "ubicacion": {
            "message": "¿En qué zona te gustaría vivir?",
            "buttons": [],
            "data_collection": [
                {
                    "field": "ubicacion",
                    "type": "text",
                    "required": True,
                    "next_state": "contacto"
                }
            ]
        },
        "contacto": {
            "message": "¡Perfecto! Te contactaremos pronto con opciones que se ajusten a tus necesidades. ¿Cuál es tu número de teléfono?",
            "buttons": [],
            "data_collection": [
                {
                    "field": "telefono",
                    "type": "text",
                    "required": True,
                    "next_state": "final"
                }
            ]
        },
        "final": {
            "message": "¡Gracias por tu información! Un agente se pondrá en contacto contigo en las próximas 24 horas.",
            "buttons": [],
            "data_collection": []
        },
        "vender": {
            "message": "¡Genial! Vamos a vender tu propiedad al mejor precio. ¿Qué tipo de propiedad tienes?",
            "buttons": [
                {"text": "Casa", "next_state": "vender_casa"},
                {"text": "Apartamento", "next_state": "vender_apartamento"},
                {"text": "Terreno", "next_state": "vender_terreno"}
            ],
            "data_collection": []
        },
        "vender_casa": {
            "message": "¿Cuántas habitaciones tiene tu casa?",
            "buttons": [],
            "data_collection": [
                {
                    "field": "habitaciones",
                    "type": "number",
                    "required": True,
                    "next_state": "valor_estimado"
                }
            ]
        },
        "valor_estimado": {
            "message": "¿Cuál crees que es el valor aproximado de tu propiedad?",
            "buttons": [],
            "data_collection": [
                {
                    "field": "valor_estimado",
                    "type": "number",
                    "required": True,
                    "next_state": "contacto_vendedor"
                }
            ]
        },
        "contacto_vendedor": {
            "message": "¡Excelente! Te ayudaremos a vender tu propiedad. ¿Cuál es tu número de teléfono?",
            "buttons": [],
            "data_collection": [
                {
                    "field": "telefono",
                    "type": "text",
                    "required": True,
                    "next_state": "final_vendedor"
                }
            ]
        },
        "final_vendedor": {
            "message": "¡Gracias! Un agente especializado te contactará pronto para hacer una evaluación gratuita de tu propiedad.",
            "buttons": [],
            "data_collection": []
        }
    },
    "initial_state": "saludo",
    "is_active": True
}

# Enviar la solicitud POST
try:
    response = requests.post(url, json=flow_data, headers={'Content-Type': 'application/json'})
    print(f"Status Code: {response.status_code}")
    if response.status_code == 201:
        print("Flow creado exitosamente!")
        print("Respuesta:", json.dumps(response.json(), indent=2, ensure_ascii=False))
    else:
        print("Error al crear el flow:")
        print("Respuesta:", response.text)
except Exception as e:
    print(f"Error de conexión: {e}")