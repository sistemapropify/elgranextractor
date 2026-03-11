#!/usr/bin/env python
"""
Prueba del extractor inteligente de requerimientos.
"""
import sys
sys.path.insert(0, '.')

from webapp.requerimientos.services import ExtractorInteligenteRequerimientos

texto_ejemplo = "🏢✨ REQUERIMIENTO INMOBILIARIO – CERRO COLORADO ✨🏢 🔎 Cliente bien filtrado 🏦 Crédito hipotecario aprobado 💰 Presupuesto: hasta USD 130,000 📍 Zonas de interés: ✔️ Michell ✔️ La Pradera ✔️ Casa Bella ✔️ La Fonda 🏠 Tipo de inmueble: Departamento 🤝 Cliente listo para comprar – cierre inmediato 📲 Propietarios y colegas inmobiliarios: Enviar propuestas con precio, ubicación, metraje y fotos. 👉📲995880505 Elby Bouroncle"

print("Probando extracción de datos...")
resultado = ExtractorInteligenteRequerimientos.extraer_datos_requerimiento(texto_ejemplo)
print("Resultado:", resultado)