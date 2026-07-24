# Registro de implementaciones pendientes

Esta carpeta es la fuente única para recordar trabajo todavía no terminado.
No reemplaza los specs técnicos: los referencia y registra su estado operativo.

## Reglas de mantenimiento

1. Toda implementación nueva debe aparecer en `REGISTRO_MAESTRO.md`.
2. Estados válidos: `propuesto`, `especificado`, `en_desarrollo`,
   `implementado_shadow`, `implementado`, `bloqueado`, `descartado`.
3. `implementado` exige código, pruebas y criterio de aceptación verificado.
4. Un despliegue pendiente se registra por separado de la implementación.
5. Cada actualización debe incluir fecha, evidencia y siguiente acción.
6. Los dos sistemas de niveles se registran como tracks distintos:
   - Track A: robustez agentic durante una conversación.
   - Track B: aprendizaje operativo entre conversaciones.

## Archivos

- [REGISTRO_MAESTRO.md](REGISTRO_MAESTRO.md): inventario y prioridad.
- [TRACK_A_CICLO_AGENTIC.md](TRACK_A_CICLO_AGENTIC.md): niveles runtime.
- [TRACK_B_APRENDIZAJE_GLOBAL.md](TRACK_B_APRENDIZAJE_GLOBAL.md): aprendizaje seguro.

