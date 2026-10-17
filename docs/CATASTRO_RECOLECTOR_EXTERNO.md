# Recolector catastral permanente en Azure

## Operación de producción: servicio permanente en Azure

La configuración final usa exclusivamente Azure para ejecutar el recolector.
No depende de PowerShell, de una PC encendida ni de Hostinger. `startup.sh`
arranca y supervisa el recolector cuando `CATASTRO_EXECUTION_MODE=external` y
`CATASTRO_AZURE_WORKER_ENABLED=1`. Usa el token privado ya configurado, el mismo
App Service con Always On, su runtime Python y `/home/data/catastro-worker` como
registro independiente de reanudación. No crea recursos ni costes de cómputo
adicionales. La salida se rota a cuatro archivos de hasta 5 MiB.

El argumento `--wait-source` comprueba la conexión con ambos servidores de
COFOPRI solo cuando hay tareas pendientes. Si no responden, deja la tarea en
cola y comunica el motivo al dashboard. Reintenta automáticamente sin marcar
el distrito como vacío ni consumir la ejecución. Si se recupera la conexión,
reclama el trabajo y continúa la descarga. Las respuestas de acceso denegado
siguen deteniendo la extracción; no se eluden restricciones de COFOPRI.

La independencia de la PC y la conectividad con COFOPRI son comprobaciones
separadas: el servicio puede estar activo en Azure mientras COFOPRI no acepta
sus conexiones. En ese caso el dashboard debe mostrar la espera explícitamente;
no afirmar que una descarga está solucionada por estar el código publicado.

Los comandos manuales de abajo sirven para diagnóstico. No son un requisito
para que un usuario inicie descargas en producción. Hostinger quedó fuera del
alcance por instrucción explícita; allí solo se hicieron consultas de diagnóstico.

El 14/10/2026 Azure no alcanzó por TCP/443 a geoportal.cofopri.gob.pe ni
catastro.cofopri.gob.pe; ambas solicitudes agotaron el tiempo de espera.
Desde el equipo local el inventario de Alto Selva Alegre respondió con 24,705
registros. No se desactiva TLS, se usan proxies públicos ni se eluden respuestas
de acceso denegado. El servicio web puede controlar un recolector ubicado en
una red con acceso normal a COFOPRI.

## Distribución y configuración

- El dashboard conserva su cola SQLite, las acciones administrativas con sesión
  y CSRF, el inventario, el avance, los lotes y el registro de cargas.
- `CATASTRO_EXECUTION_MODE=external` evita lanzar descargas en el servidor web.
  El valor por defecto `server` conserva la operación anterior.
- `CATASTRO_WORKER_TOKEN`: credencial aleatoria de al menos 32 caracteres, igual
  en servidor y recolector. Puede leerse desde `CATASTRO_WORKER_TOKEN_FILE`;
  en local se usa por defecto `~/.codex/secrets/prometeo-catastro-worker.token`.
  Nunca ponerla en Git, argumentos, URLs, capturas o mensajes del dashboard.
- El recolector dispone además de las credenciales R2 existentes, fuera de Git.
  Las credenciales de R2 no pasan por la nueva API ni por el navegador.
- No hace falta abrir un puerto entrante en el equipo recolector. Solo establece
  conexiones salientes HTTPS al dashboard, COFOPRI y R2.

Arranque de prueba contra el dashboard local:

```powershell
D:/PROMETEO/elgranextractor/venv/Scripts/python.exe scripts/catastro_worker.py --url http://127.0.0.1:8000 --once
```

Diagnóstico puntual contra producción; la operación continua pertenece al
proceso supervisado por `startup.sh` en Azure:

```powershell
D:/PROMETEO/elgranextractor/venv/Scripts/python.exe scripts/catastro_worker.py --url https://acm.propifai.com --once
```

En la operación normal el usuario solo utiliza el dashboard. Azure mantiene
el proceso y lo inicia de nuevo tras reiniciar su contenedor. La copia local
no ejecuta el recolector de producción ni instala tareas de inicio en Windows.

## Protocolo y recuperación

La API privada solo acepta POST, un Bearer específico y, tras reclamar un trabajo,
una concesión aleatoria para esa ejecución. Está desactivada fuera del modo
externo. La excepción de sesión del middleware solo cubre las rutas exactas del
recolector; cada vista valida la credencial. Dashboard, documentos y acciones de
administración mantienen sus protecciones anteriores. No hay endpoints nuevos
para leer originales o credenciales con esta clave.

El proceso reclama una única tarea, importa el inventario de reanudación en
páginas de 500 y usa el mismo extractor documental. No existe un límite total
de predios: el tamaño de página solo limita cada intercambio. Los originales,
fotos e índices completos se cargan directamente en R2 con verificación de hash.
El dashboard recibe únicamente resúmenes de lotes, progreso y hashes de carga.
Después se retiran solo las nuevas copias de trabajo verificadas; las anteriores
se conservan. Los directorios de reanudación se separan por origen del dashboard.

La señal Detener se consulta durante la descarga y no cancela una escritura a
mitad de archivo. Se confirma el lote en curso antes de finalizar. Sin conexión
al dashboard se detiene el trabajo y se conserva el avance local. Un siguiente
trabajo reconcilia cargas que quedaron sin confirmación; un equipo nuevo puede
leer originales ya verificados desde R2 y descargar solo documentos pendientes.
Las concesiones antiguas no pueden modificar trabajos terminados o reemplazados.
Un trabajo externo en cola espera al recolector sin caducar por inactividad;
Detener lo cancela antes de comenzar. La presencia se renueva en cada consulta.

## Verificación realizada

- 19 pruebas Django: control privado, CSRF administrativo, exclusión de sesión
  restringida, concesiones, detención, recuperación tras confirmación perdida,
  paginación, aislamiento de distrito/predio y cambio de equipo sin redescargas.
- 17 pruebas existentes del colector siguen pasando.
- Prueba real iniciada desde el dashboard local para el lote 04010206058015:
  un reporte, una fachada y el índice original cargados en R2, avance y lote
  visibles en dashboard. La ficha individual no disponible quedó pendiente.
  Áreas del PDF archivado: terreno 200 m² y construida 20.5 m².
- API local sin credencial: HTTP 403. JavaScript local: HTTP 200 y bytes exactos.

Esta corrección se prepara en local. Activar en producción exige publicar el
código, configurar la credencial/modo en Azure y arrancar el recolector contra
el dominio de producción. Preservar archivos, configuración y tareas anteriores.
Para revertir, detener primero el recolector y conservar los registros y R2;
volver a `server` solo será útil si Azure ya tiene acceso a COFOPRI.

## Concurrencia por ejecución

La respuesta privada claim incluye workers, guardado en el trabajo (1–10).
El mismo motor aplica ese máximo en modo local, servidor y recolector externo.
Un servidor antiguo sin ese campo conserva ejecución secuencial. Los callbacks
heartbeat, progress y lot se ejecutan en el coordinador; ningún hilo de red usa
la conexión SQLite o envía simultáneamente una confirmación del dashboard.
Los lotes terminados fuera de orden se confirman individualmente y reanudar
los omite por su identidad y carga verificada, sin depender de su posición.
