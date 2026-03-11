import sys
sys.path.insert(0, '.')
from requerimientos.services import ExtractorInteligenteRequerimientos

texto = '🏢✨ REQUERIMIENTO INMOBILIARIO – CERRO COLORADO ✨🏢 🔎 Cliente bien filtrado 🏦 Crédito hipotecario aprobado 💰 Presupuesto: hasta USD 130,000 📍 Zonas de interés: ✔️ Michell ✔️ La Pradera ✔️ Casa Bella ✔️ La Fonda 🏠 Tipo de inmueble: Departamento 🤝 Cliente listo para comprar – cierre inmediato 📲 Propietarios y colegas inmobiliarios: Enviar propuestas con precio, ubicación, metraje y fotos. 👉📲995880505 Elby Bouroncle'
resultado = ExtractorInteligenteRequerimientos.extraer_datos_requerimiento(texto)
print('Resultado:', resultado)
print('Tipo:', type(resultado))
if isinstance(resultado, dict):
    for k, v in resultado.items():
        print(f'  {k}: {v}')