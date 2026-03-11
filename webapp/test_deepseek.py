import requests
import json
import re

API_KEY = "sk-460d28e38c7e4b05a13fa2bebd27159c"
API_URL = "https://api.deepseek.com/chat/completions"

texto = '🏢✨ REQUERIMIENTO INMOBILIARIO – CERRO COLORADO ✨🏢 🔎 Cliente bien filtrado 🏦 Crédito hipotecario aprobado 💰 Presupuesto: hasta USD 130,000 📍 Zonas de interés: ✔️ Michell ✔️ La Pradera ✔️ Casa Bella ✔️ La Fonda 🏠 Tipo de inmueble: Departamento 🤝 Cliente listo para comprar – cierre inmediato 📲 Propietarios y colegas inmobiliarios: Enviar propuestas con precio, ubicación, metraje y fotos. 👉📲995880505 Elby Bouroncle'

campos_solicitados = [
    'presupuesto', 'tipo_inmueble', 'ubicacion', 'zonas_interes',
    'banos', 'habitaciones', 'contacto', 'cliente', 'estado_credito',
    'moneda', 'fecha_requerimiento', 'notas'
]

prompt = f"""Eres un experto en extracción de datos de requerimientos inmobiliarios. Extrae la información estructurada del siguiente texto y devuélvela en formato JSON válido.

Texto del requerimiento:
{texto}

Campos a extraer (si están presentes en el texto):
{', '.join(campos_solicitados)}

Instrucciones:
1. Extrae solo los datos que aparecen explícitamente en el texto.
2. Si un campo no está presente, omítelo del JSON.
3. Convierte valores monetarios a números (ej: "USD 130,000" → 130000).
4. Normaliza tipos de inmueble: "Departamento", "Casa", "Oficina", "Local", "Terreno".
5. Para ubicaciones, extrae distrito, ciudad, departamento si están mencionados.
6. Para contactos, extrae teléfono y nombre si están presentes.
7. Devuelve un objeto JSON con los campos extraídos.

Respuesta debe ser SOLO el JSON, sin explicaciones."""

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

payload = {
    "model": "deepseek-chat",
    "messages": [
        {"role": "system", "content": "Eres un asistente especializado en extracción estructurada de datos de textos inmobiliarios. Siempre respondes con JSON válido."},
        {"role": "user", "content": prompt}
    ],
    "temperature": 0.1,
    "max_tokens": 1000
}

print("Enviando solicitud a DeepSeek API...")
try:
    response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
    print(f"Status code: {response.status_code}")
    print(f"Response headers: {response.headers}")
    if response.status_code != 200:
        print(f"Error: {response.text}")
    else:
        data = response.json()
        print(f"Response keys: {data.keys()}")
        content = data["choices"][0]["message"]["content"]
        print(f"Content: {content}")
        # Extraer JSON
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            datos = json.loads(json_match.group())
            print("Datos extraídos:")
            for k, v in datos.items():
                print(f"  {k}: {v}")
        else:
            print("No se encontró JSON en la respuesta")
except Exception as e:
    print(f"Excepción: {e}")