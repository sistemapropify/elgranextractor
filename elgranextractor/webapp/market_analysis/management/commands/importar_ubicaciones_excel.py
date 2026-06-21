"""
Comando de management para importar ubicaciones geograficas desde un archivo Excel.

Soporta dos modos:

Modo 1 — Columnas: departamento, provincia, distrito (y opcional: codigo_postal, fuente)
    python manage.py importar_ubicaciones_excel --ruta=ruta.xlsx

Modo 2 — Columnas: distrito, urbanizacion/zona/barrio (y opcional: codigo_postal, fuente)
    Asume departamento=Arequipa, provincia=Arequipa.
    python manage.py importar_ubicaciones_excel --ruta=D:/Urbanizaciones_Arequipa_v2.xlsx

Modo 3 — Fuerza 4 niveles con valores por defecto para dep/prov:
    python manage.py importar_ubicaciones_excel --ruta=ruta.xlsx --departamento=Arequipa --provincia=Arequipa
"""

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from market_analysis.models import UbicacionGeografica


class Command(BaseCommand):
    help = 'Importa ubicaciones geograficas (departamento → provincia → distrito → zona/urbanizacion) desde Excel'

    def add_arguments(self, parser):
        parser.add_argument(
            '--ruta',
            type=str,
            required=True,
            help='Ruta completa del archivo Excel'
        )
        parser.add_argument(
            '--sheet',
            type=str,
            default=None,
            help='Nombre del sheet (opcional, usa el primero por defecto)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo mostrar lo que se importaria sin guardar'
        )
        parser.add_argument(
            '--departamento',
            type=str,
            default=None,
            help='Valor por defecto para departamento (si no existe columna)'
        )
        parser.add_argument(
            '--provincia',
            type=str,
            default=None,
            help='Valor por defecto para provincia (si no existe columna)'
        )

    def _detectar_columnas(self, df):
        """
        Detecta automaticamente las columnas del Excel.
        Retorna un dict con los nombres normalizados de las columnas encontradas.
        """
        cols = {c: c for c in df.columns}

        # Buscar columna de urbanizacion/zona/barrio
        for c in df.columns:
            c_lower = c.lower()
            if any(kw in c_lower for kw in ['urbanizacion', 'urbanización', 'zona', 'barrio']):
                cols['zona_urbanizacion'] = c
                break

        return cols

    def handle(self, *args, **options):
        ruta = options['ruta']
        sheet = options['sheet']
        dry_run = options['dry_run']
        dep_default = options['departamento']
        prov_default = options['provincia']

        self.stdout.write(f"[+] Leyendo archivo: {ruta}")
        try:
            if sheet:
                df = pd.read_excel(ruta, sheet_name=sheet, dtype=str)
            else:
                df = pd.read_excel(ruta, dtype=str)
        except Exception as e:
            raise CommandError(f"Error al leer el Excel: {e}")

        # Normalizar nombres de columnas a minusculas
        df.columns = df.columns.str.strip().str.lower()
        col_map = self._detectar_columnas(df)

        # Detectar modo de operacion
        tiene_departamento = 'departamento' in df.columns
        tiene_provincia = 'provincia' in df.columns
        tiene_distrito = 'distrito' in df.columns
        tiene_zona = 'zona_urbanizacion' in col_map

        if not tiene_distrito:
            raise CommandError(
                "Columna 'distrito' no encontrada. "
                f"Columnas disponibles: {list(df.columns)}"
            )

        if not tiene_zona:
            self.stdout.write(self.style.WARNING(
                "[!] No se detecto columna de urbanizacion/zona/barrio. "
                "Solo se importaran niveles hasta distrito."
            ))

        # Valores por defecto para departamento/provincia
        if not tiene_departamento:
            if dep_default:
                df['departamento'] = dep_default
                tiene_departamento = True
                self.stdout.write(f"[*] Usando departamento por defecto: {dep_default}")
            else:
                self.stdout.write(self.style.WARNING(
                    "[!] Sin columna 'departamento'. Se usara 'Arequipa' por defecto. "
                    "Usa --departamento=Nombre para cambiarlo."
                ))
                df['departamento'] = 'Arequipa'
                tiene_departamento = True

        if not tiene_provincia:
            if prov_default:
                df['provincia'] = prov_default
                tiene_provincia = True
                self.stdout.write(f"[*] Usando provincia por defecto: {prov_default}")
            else:
                self.stdout.write(self.style.WARNING(
                    "[!] Sin columna 'provincia'. Se usara 'Arequipa' por defecto. "
                    "Usa --provincia=Nombre para cambiarlo."
                ))
                df['provincia'] = 'Arequipa'
                tiene_provincia = True

        total_filas = len(df)
        self.stdout.write(f"[*] Filas encontradas: {total_filas}")
        if dry_run:
            self.stdout.write("[!] Modo DRY RUN - no se guardaran cambios\n")

        # ============================================================
        # ESTRATEGIA OPTIMIZADA: Agrupar datos unicos y crear en lote
        # ============================================================

        # 1. Extraer datos unicos por nivel
        departamentos_unicos = df['departamento'].dropna().str.strip().unique()
        provincias_unicas = df['provincia'].dropna().str.strip().unique()
        distritos_unicos = df[['distrito', 'departamento', 'provincia']].dropna(subset=['distrito']).copy()
        distritos_unicos['distrito'] = distritos_unicos['distrito'].str.strip()
        distritos_unicos['departamento'] = distritos_unicos['departamento'].str.strip()
        distritos_unicos['provincia'] = distritos_unicos['provincia'].str.strip()
        distritos_unicos = distritos_unicos.drop_duplicates(subset=['distrito', 'departamento', 'provincia'])

        # Zonas: agrupar por distrito
        zonas_data = []
        if tiene_zona:
            col_zona = col_map['zona_urbanizacion']
            for _, row in df.iterrows():
                zona_val = row.get(col_zona, '')
                if pd.notna(zona_val) and str(zona_val).strip():
                    zonas_data.append({
                        'zona': str(zona_val).strip(),
                        'distrito': str(row['distrito']).strip(),
                        'departamento': str(row['departamento']).strip(),
                        'provincia': str(row['provincia']).strip(),
                        'fuente': str(row.get('fuente', '')).strip() if pd.notna(row.get('fuente')) else '',
                    })

        self.stdout.write(f"[*] Datos unicos: {len(departamentos_unicos)} deptos, "
                          f"{len(provincias_unicas)} provs, "
                          f"{len(distritos_unicos)} distritos, "
                          f"{len(zonas_data)} zonas")

        if dry_run:
            self.stdout.write("\n[!] DRY RUN - No se guardara nada. Ejecuta sin --dry-run para importar.")
            self.stdout.write("\n[#] Vista previa de lo que se importaria:")
            self.stdout.write(f"  Departamentos: {', '.join(departamentos_unicos)}")
            self.stdout.write(f"  Provincias: {', '.join(provincias_unicas)}")
            self.stdout.write(f"  Distritos ({len(distritos_unicos)}):")
            for _, d in distritos_unicos.iterrows():
                self.stdout.write(f"    - {d['distrito']} ({d['provincia']}, {d['departamento']})")
            if zonas_data:
                # Agrupar zonas por distrito para preview
                zonas_por_distrito = {}
                for z in zonas_data:
                    zonas_por_distrito.setdefault(z['distrito'], []).append(z['zona'])
                self.stdout.write(f"  Zonas/Urbanizaciones por distrito:")
                for dist, zonas in sorted(zonas_por_distrito.items()):
                    self.stdout.write(f"    {dist}: {len(zonas)} zonas")
            return

        # ============================================================
        # IMPORTACION REAL con transaccion
        # ============================================================
        stats = {'departamentos': 0, 'provincias': 0, 'distritos': 0, 'zonas': 0, 'errores': 0}

        try:
            with transaction.atomic():
                # --- DEPARTAMENTOS ---
                deptos_existentes = {
                    u.nombre: u for u in
                    UbicacionGeografica.objects.filter(nivel='departamento', nombre__in=departamentos_unicos)
                }
                deptos_a_crear = []
                for dep_nombre in departamentos_unicos:
                    if dep_nombre not in deptos_existentes:
                        deptos_a_crear.append(UbicacionGeografica(
                            nombre=dep_nombre, nivel='departamento', activo=True
                        ))

                if deptos_a_crear:
                    UbicacionGeografica.objects.bulk_create(deptos_a_crear)
                    stats['departamentos'] = len(deptos_a_crear)
                    # Recargar cache
                    for d in deptos_a_crear:
                        deptos_existentes[d.nombre] = d
                    self.stdout.write(f"  [+] {len(deptos_a_crear)} departamento(s) creado(s)")

                # Refrescar todos los deptos (incluyendo los recien creados)
                deptos_map = {u.nombre: u for u in
                              UbicacionGeografica.objects.filter(nivel='departamento')}

                # --- PROVINCIAS ---
                provs_existentes = {
                    (u.nombre, u.parent_id): u for u in
                    UbicacionGeografica.objects.filter(nivel='provincia')
                }
                provs_a_crear = []
                for prov_nombre in provincias_unicas:
                    # La provincia pertenece al unico departamento (Arequipa)
                    dep = deptos_map.get('Arequipa')
                    if not dep:
                        self.stdout.write(self.style.ERROR(
                            f"  [X] Departamento 'Arequipa' no encontrado para provincia {prov_nombre}"
                        ))
                        stats['errores'] += 1
                        continue
                    key = (prov_nombre, dep.id)
                    if key not in provs_existentes:
                        provs_a_crear.append(UbicacionGeografica(
                            nombre=prov_nombre, nivel='provincia', parent=dep, activo=True
                        ))

                if provs_a_crear:
                    UbicacionGeografica.objects.bulk_create(provs_a_crear)
                    stats['provincias'] = len(provs_a_crear)
                    self.stdout.write(f"  [+] {len(provs_a_crear)} provincia(s) creada(s)")

                # Refrescar provincias
                provs_map = {}
                for u in UbicacionGeografica.objects.filter(nivel='provincia'):
                    provs_map[(u.nombre, u.parent_id)] = u

                # --- DISTRITOS ---
                dists_existentes = {
                    (u.nombre, u.parent_id): u for u in
                    UbicacionGeografica.objects.filter(nivel='distrito')
                }
                dists_a_crear = []
                for _, row in distritos_unicos.iterrows():
                    dep = deptos_map.get(row['departamento'])
                    if not dep:
                        stats['errores'] += 1
                        continue
                    prov_key = (row['provincia'], dep.id)
                    prov = provs_map.get(prov_key)
                    if not prov:
                        stats['errores'] += 1
                        continue
                    dist_key = (row['distrito'], prov.id)
                    if dist_key not in dists_existentes:
                        dists_a_crear.append(UbicacionGeografica(
                            nombre=row['distrito'], nivel='distrito',
                            parent=prov, activo=True
                        ))

                if dists_a_crear:
                    UbicacionGeografica.objects.bulk_create(dists_a_crear)
                    stats['distritos'] = len(dists_a_crear)
                    self.stdout.write(f"  [+] {len(dists_a_crear)} distrito(s) creado(s)")

                # Refrescar distritos
                dists_map = {}
                for u in UbicacionGeografica.objects.filter(nivel='distrito'):
                    dists_map[(u.nombre, u.parent_id)] = u

                # --- ZONAS / URBANIZACIONES ---
                if zonas_data:
                    # Obtener zonas existentes
                    zonas_existentes = set()
                    for u in UbicacionGeografica.objects.filter(nivel='zona_urbanizacion'):
                        zonas_existentes.add((u.nombre, u.parent_id))

                    zonas_a_crear = []
                    for z in zonas_data:
                        dep = deptos_map.get(z['departamento'])
                        if not dep:
                            continue
                        prov_key = (z['provincia'], dep.id)
                        prov = provs_map.get(prov_key)
                        if not prov:
                            continue
                        dist_key = (z['distrito'], prov.id)
                        dist = dists_map.get(dist_key)
                        if not dist:
                            continue
                        zona_key = (z['zona'], dist.id)
                        if zona_key not in zonas_existentes:
                            zonas_a_crear.append(UbicacionGeografica(
                                nombre=z['zona'], nivel='zona_urbanizacion',
                                parent=dist, codigo=z['fuente'], activo=True
                            ))
                            zonas_existentes.add(zona_key)

                    if zonas_a_crear:
                        # Crear en lotes de 100 para no saturar
                        batch_size = 100
                        for i in range(0, len(zonas_a_crear), batch_size):
                            batch = zonas_a_crear[i:i + batch_size]
                            UbicacionGeografica.objects.bulk_create(batch)
                        stats['zonas'] = len(zonas_a_crear)
                        self.stdout.write(f"  [+] {len(zonas_a_crear)} zona(s)/urbanizacion(es) creada(s)")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n[X] Error durante la importacion: {e}"))
            raise

        # Resumen final
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS("[#] RESUMEN DE IMPORTACION"))
        self.stdout.write("=" * 50)
        self.stdout.write(f"  Total filas en Excel: {total_filas}")
        self.stdout.write(f"  Departamentos creados: {stats['departamentos']}")
        self.stdout.write(f"  Provincias creadas: {stats['provincias']}")
        self.stdout.write(f"  Distritos creados: {stats['distritos']}")
        self.stdout.write(f"  Zonas/Urbanizaciones creadas: {stats['zonas']}")
        self.stdout.write(f"  Errores/saltados: {stats['errores']}")
        self.stdout.write("=" * 50)
