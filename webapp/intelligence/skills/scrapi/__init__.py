"""
Skills de scraping de portales inmobiliarios.

Cada scraper es una skill independiente (hereda de BaseSkill).
El orquestador las ejecuta en secuencia.

Scrapers disponibles:
- scraper_remax
- scraper_adondevivir
- scraper_properati
- scraper_urbania
- scraper_orchestrator (ejecuta las 4 en secuencia)
"""
