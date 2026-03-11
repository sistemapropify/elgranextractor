#!/usr/bin/env python
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
django.setup()

from requerimientos.services import ExtractorInteligenteRequerimientos

texto_ejemplo = "🏢✨ REQUERIMIENTO INMOBILIARIO – CERRO COLORADO ✨🏢 🔎 Cliente bien filtrado 🏦 Crédito hipotecario aprobado 💰 Presupuesto: hasta USD 130,000 📍 Zonas de interés: ✔️ Michell ✔️ La Pradera ✔️ Casa Bella ✔️ La Fonda 🏠 Tipo de inmueble: Departamento 🤝 Cliente listo para comprar – cierre inmediato 📲 Propietarios y colegas inmobiliarios: Enviar propuestas con precio, ubicación, metraje y fotos. 👉📲995880505 Elby Bouroncle"

print("Probando extracción de datos...")
resultado = ExtractorInteligenteRequerimientos.extraer_datos_requerimiento(texto_ejemplo)
print("Resultado:", resultado)