# Árbol completo del proyecto Prometeo

```
./
    ├── elgranextractor/
    │   ├── mcp-deepseek-requerimientos/
    │   │   ├── src/
    │   │   │   ├── index-simple.ts
    │   │   │   └── index.ts
    │   │   ├── README.md
    │   │   ├── mcp_settings_example.json
    │   │   ├── package-lock.json
    │   │   ├── package.json
    │   │   ├── test-import.js
    │   │   ├── test-server.js
    │   │   ├── test-tool.js
    │   │   └── tsconfig.json
    │   ├── webapp/
    │   │   ├── acm/
    │   │   │   ├── static/
    │   │   │   │   └── acm/
    │   │   │   │       ├── css/
    │   │   │   │       │   └── acm.css
    │   │   │   │       ├── img/
    │   │   │   │       │   └── no-image.svg
    │   │   │   │       └── js/
    │   │   │   │           └── acm.js
    │   │   │   ├── templates/
    │   │   │   │   └── acm/
    │   │   │   │       ├── acm_analisis.html
    │   │   │   │       ├── acm_analisis_compacto.html
    │   │   │   │       └── acm_base.html
    │   │   │   ├── __init__.py
    │   │   │   ├── apps.py
    │   │   │   ├── urls.py
    │   │   │   ├── utils.py
    │   │   │   └── views.py
    │   │   ├── api/
    │   │   │   ├── __init__.py
    │   │   │   ├── serializers.py
    │   │   │   ├── urls.py
    │   │   │   ├── urls_mejoradas.py
    │   │   │   ├── views.py
    │   │   │   └── views_mejoradas.py
    │   │   ├── captura/
    │   │   │   ├── migrations/
    │   │   │   │   ├── 0001_initial.py
    │   │   │   │   ├── 0002_initial_consolidada.py
    │   │   │   │   ├── 0003_eventodeteccion_captura_eve_fuente__e6ec8b_idx.py
    │   │   │   │   └── __init__.py
    │   │   │   ├── README_SCREENSHOT_OCR.md
    │   │   │   ├── __init__.py
    │   │   │   ├── admin.py
    │   │   │   ├── azure_storage.py
    │   │   │   ├── captura_screenshot.py
    │   │   │   ├── detector_tipos.py
    │   │   │   ├── diff_engine.py
    │   │   │   ├── extractor_pdf.py
    │   │   │   ├── mejorador_captura.py
    │   │   │   ├── models.py
    │   │   │   ├── tareas_mejoradas.py
    │   │   │   └── test_captura_screenshot.py
    │   │   ├── colas/
    │   │   │   ├── __init__.py
    │   │   │   ├── celery.py
    │   │   │   ├── tareas_captura.py
    │   │   │   ├── tareas_descubrimiento.py
    │   │   │   └── tasks.py
    │   │   ├── cuadrantizacion/
    │   │   │   ├── management/
    │   │   │   │   ├── commands/
    │   │   │   │   │   ├── __init__.py
    │   │   │   │   │   ├── calcular_precios_zonas.py
    │   │   │   │   │   ├── crear_datos_prueba.py
    │   │   │   │   │   └── migrar_propiedades_valoracion.py
    │   │   │   │   └── __init__.py
    │   │   │   ├── migrations/
    │   │   │   │   ├── 0001_initial.py
    │   │   │   │   ├── 0002_alter_zonavalor_options_and_more.py
    │   │   │   │   ├── 0003_alter_zonavalor_coordenadas.py
    │   │   │   │   └── __init__.py
    │   │   │   ├── __init__.py
    │   │   │   ├── apps.py
    │   │   │   ├── models.py
    │   │   │   ├── serializers.py
    │   │   │   ├── services.py
    │   │   │   ├── urls.py
    │   │   │   ├── utils.py
    │   │   │   └── views.py
    │   │   ├── ingestas/
    │   │   │   ├── management/
    │   │   │   │   ├── commands/
    │   │   │   │   │   ├── __init__.py
    │   │   │   │   │   ├── borrar_propiedadraw.py
    │   │   │   │   │   ├── importar_excel_propiedadraw.py
    │   │   │   │   │   └── migrar_atributos_a_campos.py
    │   │   │   │   └── __init__.py
    │   │   │   ├── migrations/
    │   │   │   │   ├── 0001_initial.py
    │   │   │   │   ├── 0002_alter_campodinamico_id_alter_mapeofuente_id_and_more.py
    │   │   │   │   ├── 0003_propiedadraw_agente_inmobiliario_and_more.py
    │   │   │   │   ├── 0004_change_fecha_publicacion_to_date.py
    │   │   │   │   ├── 0005_remove_old_fields.py
    │   │   │   │   ├── 0006_fix_atributos_extras_nullable.py
    │   │   │   │   ├── 0007_propiedadraw_estado_propiedad_and_more.py
    │   │   │   │   ├── 0008_estandarizar_tipo_propiedad.py
    │   │   │   │   ├── 0009_propiedadraw_identificador_externo.py
    │   │   │   │   ├── 0010_add_subtipo_propiedad.py
    │   │   │   │   └── __init__.py
    │   │   │   ├── templatetags/
    │   │   │   │   ├── __init__.py
    │   │   │   │   └── ingestas_extras.py
    │   │   │   ├── README_PROCESAMIENTO_IA.md
    │   │   │   ├── __init__.py
    │   │   │   ├── admin.py
    │   │   │   ├── forms.py
    │   │   │   ├── models.py
    │   │   │   ├── procesamiento_ia.py
    │   │   │   ├── services.py
    │   │   │   ├── services_api.py
    │   │   │   ├── urls.py
    │   │   │   └── views.py
    │   │   ├── market_analysis/
    │   │   │   ├── migrations/
    │   │   │   │   └── __init__.py
    │   │   │   ├── static/
    │   │   │   │   └── market_analysis/
    │   │   │   │       └── js/
    │   │   │   │           ├── dashboard.js
    │   │   │   │           ├── heatmap-init.js
    │   │   │   │           └── heatmap.js
    │   │   │   ├── templates/
    │   │   │   │   └── market_analysis/
    │   │   │   │       ├── dashboard.html
    │   │   │   │       ├── heatmap.html
    │   │   │   │       ├── heatmap_fixed.html
    │   │   │   │       ├── heatmap_minimal.html
    │   │   │   │       ├── heatmap_simple.html
    │   │   │   │       └── heatmap_test.html
    │   │   │   ├── __init__.py
    │   │   │   ├── admin.py
    │   │   │   ├── apps.py
    │   │   │   ├── diagnostic.py
    │   │   │   ├── models.py
    │   │   │   ├── tests.py
    │   │   │   ├── urls.py
    │   │   │   └── views.py
    │   │   ├── matching/
    │   │   │   ├── migrations/
    │   │   │   │   ├── 0001_initial.py
    │   │   │   │   └── __init__.py
    │   │   │   ├── static/
    │   │   │   │   └── matching/
    │   │   │   │       └── matching.js
    │   │   │   ├── templates/
    │   │   │   │   └── matching/
    │   │   │   │       ├── partials/
    │   │   │   │       │   └── resumen_requerimiento.html
    │   │   │   │       ├── dashboard.html
    │   │   │   │       └── masivo.html
    │   │   │   ├── README_MATCHING.md
    │   │   │   ├── __init__.py
    │   │   │   ├── admin.py
    │   │   │   ├── apps.py
    │   │   │   ├── engine.py
    │   │   │   ├── models.py
    │   │   │   ├── serializers.py
    │   │   │   ├── tests.py
    │   │   │   ├── urls.py
    │   │   │   └── views.py
    │   │   ├── propifai/
    │   │   │   ├── migrations/
    │   │   │   │   ├── 0001_initial.py
    │   │   │   │   └── __init__.py
    │   │   │   ├── __init__.py
    │   │   │   ├── admin.py
    │   │   │   ├── apps.py
    │   │   │   ├── mapeo_ubicaciones.py
    │   │   │   ├── models.py
    │   │   │   ├── tests.py
    │   │   │   ├── urls.py
    │   │   │   └── views.py
    │   │   ├── requerimientos/
    │   │   │   ├── data/
    │   │   │   │   ├── PROCEDIMIENTO_IMPORTACION_INMOBILIARIOS.md
    │   │   │   │   ├── inmobiliaria-remax-10-febrero-2026.xlsx
    │   │   │   │   ├── propiedadesraw2_tipificado.xlsx
    │   │   │   │   ├── requerimientos_completo.xlsx
    │   │   │   │   └── requerimientos_inmobiliarios.xlsx
    │   │   │   ├── management/
    │   │   │   │   ├── commands/
    │   │   │   │   │   ├── __init__.py
    │   │   │   │   │   ├── importar_requerimientos_excel.py
    │   │   │   │   │   └── importar_requerimientos_inmobiliarios.py
    │   │   │   │   └── __init__.py
    │   │   │   ├── migrations/
    │   │   │   │   ├── 0001_initial.py
    │   │   │   │   ├── 0002_remove_requerimientoraw_requerimien_tipo_re_68263b_idx_and_more.py
    │   │   │   │   ├── 0003_requerimiento_and_more.py
    │   │   │   │   ├── 0004_add_fuente_red_inmobiliaria.py
    │   │   │   │   └── __init__.py
    │   │   │   ├── README_ANALISIS_TEMPORAL.md
    │   │   │   ├── README_MEJORAS_PROGRESO.md
    │   │   │   ├── __init__.py
    │   │   │   ├── admin.py
    │   │   │   ├── analytics.py
    │   │   │   ├── apps.py
    │   │   │   ├── check_excel_structure.py
    │   │   │   ├── check_rows.py
    │   │   │   ├── diagnostico_fuente.py
    │   │   │   ├── diagnostico_simple.py
    │   │   │   ├── forms.py
    │   │   │   ├── importar_nuevo_excel.py
    │   │   │   ├── inspeccionar_nuevo_excel.py
    │   │   │   ├── inspeccionar_simple.py
    │   │   │   ├── inspect_excel.py
    │   │   │   ├── models.py
    │   │   │   ├── services.py
    │   │   │   ├── tasks.py
    │   │   │   ├── test_import.py
    │   │   │   ├── test_import_full.py
    │   │   │   ├── test_import_simple.py
    │   │   │   ├── tests.py
    │   │   │   ├── urls.py
    │   │   │   └── views.py
    │   │   ├── semillas/
    │   │   │   ├── migrations/
    │   │   │   │   ├── 0001_initial.py
    │   │   │   │   ├── 0002_fuenteweb_categoria.py
    │   │   │   │   ├── 0003_fuenteweb_es_semilla_activa_and_more.py
    │   │   │   │   ├── 0004_alter_fuenteweb_id.py
    │   │   │   │   └── __init__.py
    │   │   │   ├── __init__.py
    │   │   │   ├── admin.py
    │   │   │   ├── descubrimiento.py
    │   │   │   └── models.py
    │   │   ├── static/
    │   │   │   ├── requerimientos/
    │   │   │   │   ├── data/
    │   │   │   │   │   ├── Pin-propify.svg
    │   │   │   │   │   ├── test-pin.svg
    │   │   │   │   │   └── test.txt
    │   │   │   │   └── js/
    │   │   │   │       └── dashboard_analytics.js
    │   │   │   └── test_image.html
    │   │   ├── staticfiles/
    │   │   │   └── admin/
    │   │   │       ├── css/
    │   │   │       │   ├── vendor/
    │   │   │       │   │   └── select2/
    │   │   │       │   │       ├── LICENSE-SELECT2.md
    │   │   │       │   │       ├── select2.css
    │   │   │       │   │       └── select2.min.css
    │   │   │       │   ├── autocomplete.css
    │   │   │       │   ├── base.css
    │   │   │       │   ├── changelists.css
    │   │   │       │   ├── dark_mode.css
    │   │   │       │   ├── dashboard.css
    │   │   │       │   ├── forms.css
    │   │   │       │   ├── login.css
    │   │   │       │   ├── nav_sidebar.css
    │   │   │       │   ├── responsive.css
    │   │   │       │   ├── responsive_rtl.css
    │   │   │       │   ├── rtl.css
    │   │   │       │   ├── unusable_password_field.css
    │   │   │       │   └── widgets.css
    │   │   │       ├── img/
    │   │   │       │   ├── gis/
    │   │   │       │   │   ├── move_vertex_off.svg
    │   │   │       │   │   └── move_vertex_on.svg
    │   │   │       │   ├── LICENSE
    │   │   │       │   ├── README.txt
    │   │   │       │   ├── calendar-icons.svg
    │   │   │       │   ├── icon-addlink.svg
    │   │   │       │   ├── icon-alert.svg
    │   │   │       │   ├── icon-calendar.svg
    │   │   │       │   ├── icon-changelink.svg
    │   │   │       │   ├── icon-clock.svg
    │   │   │       │   ├── icon-deletelink.svg
    │   │   │       │   ├── icon-hidelink.svg
    │   │   │       │   ├── icon-no.svg
    │   │   │       │   ├── icon-unknown-alt.svg
    │   │   │       │   ├── icon-unknown.svg
    │   │   │       │   ├── icon-viewlink.svg
    │   │   │       │   ├── icon-yes.svg
    │   │   │       │   ├── inline-delete.svg
    │   │   │       │   ├── search.svg
    │   │   │       │   ├── selector-icons.svg
    │   │   │       │   ├── sorting-icons.svg
    │   │   │       │   ├── tooltag-add.svg
    │   │   │       │   └── tooltag-arrowright.svg
    │   │   │       └── js/
    │   │   │           ├── admin/
    │   │   │           │   ├── DateTimeShortcuts.js
    │   │   │           │   └── RelatedObjectLookups.js
    │   │   │           ├── vendor/
    │   │   │           │   ├── jquery/
    │   │   │           │   │   ├── LICENSE.txt
    │   │   │           │   │   ├── jquery.js
    │   │   │           │   │   └── jquery.min.js
    │   │   │           │   ├── select2/
    │   │   │           │   │   ├── i18n/
    │   │   │           │   │   │   ├── af.js
    │   │   │           │   │   │   ├── ar.js
    │   │   │           │   │   │   ├── az.js
    │   │   │           │   │   │   ├── bg.js
    │   │   │           │   │   │   ├── bn.js
    │   │   │           │   │   │   ├── bs.js
    │   │   │           │   │   │   ├── ca.js
    │   │   │           │   │   │   ├── cs.js
    │   │   │           │   │   │   ├── da.js
    │   │   │           │   │   │   ├── de.js
    │   │   │           │   │   │   ├── dsb.js
    │   │   │           │   │   │   ├── el.js
    │   │   │           │   │   │   ├── en.js
    │   │   │           │   │   │   ├── es.js
    │   │   │           │   │   │   ├── et.js
    │   │   │           │   │   │   ├── eu.js
    │   │   │           │   │   │   ├── fa.js
    │   │   │           │   │   │   ├── fi.js
    │   │   │           │   │   │   ├── fr.js
    │   │   │           │   │   │   ├── gl.js
    │   │   │           │   │   │   ├── he.js
    │   │   │           │   │   │   ├── hi.js
    │   │   │           │   │   │   ├── hr.js
    │   │   │           │   │   │   ├── hsb.js
    │   │   │           │   │   │   ├── hu.js
    │   │   │           │   │   │   ├── hy.js
    │   │   │           │   │   │   ├── id.js
    │   │   │           │   │   │   ├── is.js
    │   │   │           │   │   │   ├── it.js
    │   │   │           │   │   │   ├── ja.js
    │   │   │           │   │   │   ├── ka.js
    │   │   │           │   │   │   ├── km.js
    │   │   │           │   │   │   ├── ko.js
    │   │   │           │   │   │   ├── lt.js
    │   │   │           │   │   │   ├── lv.js
    │   │   │           │   │   │   ├── mk.js
    │   │   │           │   │   │   ├── ms.js
    │   │   │           │   │   │   ├── nb.js
    │   │   │           │   │   │   ├── ne.js
    │   │   │           │   │   │   ├── nl.js
    │   │   │           │   │   │   ├── pl.js
    │   │   │           │   │   │   ├── ps.js
    │   │   │           │   │   │   ├── pt-BR.js
    │   │   │           │   │   │   ├── pt.js
    │   │   │           │   │   │   ├── ro.js
    │   │   │           │   │   │   ├── ru.js
    │   │   │           │   │   │   ├── sk.js
    │   │   │           │   │   │   ├── sl.js
    │   │   │           │   │   │   ├── sq.js
    │   │   │           │   │   │   ├── sr-Cyrl.js
    │   │   │           │   │   │   ├── sr.js
    │   │   │           │   │   │   ├── sv.js
    │   │   │           │   │   │   ├── th.js
    │   │   │           │   │   │   ├── tk.js
    │   │   │           │   │   │   ├── tr.js
    │   │   │           │   │   │   ├── uk.js
    │   │   │           │   │   │   ├── vi.js
    │   │   │           │   │   │   ├── zh-CN.js
    │   │   │           │   │   │   └── zh-TW.js
    │   │   │           │   │   ├── LICENSE.md
    │   │   │           │   │   ├── select2.full.js
    │   │   │           │   │   └── select2.full.min.js
    │   │   │           │   └── xregexp/
    │   │   │           │       ├── LICENSE.txt
    │   │   │           │       ├── xregexp.js
    │   │   │           │       └── xregexp.min.js
    │   │   │           ├── SelectBox.js
    │   │   │           ├── SelectFilter2.js
    │   │   │           ├── actions.js
    │   │   │           ├── autocomplete.js
    │   │   │           ├── calendar.js
    │   │   │           ├── cancel.js
    │   │   │           ├── change_form.js
    │   │   │           ├── core.js
    │   │   │           ├── filters.js
    │   │   │           ├── inlines.js
    │   │   │           ├── jquery.init.js
    │   │   │           ├── nav_sidebar.js
    │   │   │           ├── popup_response.js
    │   │   │           ├── prepopulate.js
    │   │   │           ├── prepopulate_init.js
    │   │   │           ├── theme.js
    │   │   │           ├── unusable_password_field.js
    │   │   │           └── urlify.js
    │   │   ├── templates/
    │   │   │   ├── admin/
    │   │   │   │   ├── ingestas/
    │   │   │   │   │   ├── borrar_todo_confirm.html
    │   │   │   │   │   └── importar_excel.html
    │   │   │   │   └── requerimientos/
    │   │   │   │       ├── importar_excel.html
    │   │   │   │       └── requerimiento_change_list.html
    │   │   │   ├── cuadrantizacion/
    │   │   │   │   ├── _tree_node.html
    │   │   │   │   ├── configurar_jerarquia.html
    │   │   │   │   ├── heatmap.html
    │   │   │   │   └── mapa_zonas.html
    │   │   │   ├── ingestas/
    │   │   │   │   ├── detalle_propiedad.html
    │   │   │   │   ├── editar_propiedad.html
    │   │   │   │   ├── index.html
    │   │   │   │   ├── lista_propiedades_rediseno.html
    │   │   │   │   ├── lista_propiedades_rediseno.html.backup2
    │   │   │   │   ├── lista_propiedades_rediseno_backup.html
    │   │   │   │   ├── lista_propiedades_rediseno_debug.html
    │   │   │   │   ├── procesar_ia.html
    │   │   │   │   ├── resultado.html
    │   │   │   │   ├── resultado_ia.html
    │   │   │   │   ├── subir.html
    │   │   │   │   └── validar.html
    │   │   │   ├── propifai/
    │   │   │   │   ├── lista_propiedades_propify.html
    │   │   │   │   ├── lista_propiedades_propify_clonado.html
    │   │   │   │   ├── lista_propiedades_propify_rediseno.html
    │   │   │   │   └── propiedades_simple.html
    │   │   │   ├── requerimientos/
    │   │   │   │   ├── dashboard_analisis.html
    │   │   │   │   └── lista.html
    │   │   │   ├── base.html
    │   │   │   ├── capturas.html
    │   │   │   ├── capturas_mejoradas.html
    │   │   │   ├── fuentes_web.html
    │   │   │   └── index.html
    │   │   ├── .env.example
    │   │   ├── .gitignore
    │   │   ├── BORRAR_PROPIEDADRAW.md
    │   │   ├── COMO_USAR_CAPTURAS.md
    │   │   ├── CORRECCION_CAMPOS_DINAMICOS.md
    │   │   ├── CUADRANTIZACION_IMPLEMENTADA.md
    │   │   ├── DEPLOYMENT_CHECKLIST.md
    │   │   ├── FIX_BASE_DATOS.md
    │   │   ├── GUIA_USO_CAPTURAS.md
    │   │   ├── INICIO_RAPIDO_CAPTURA.md
    │   │   ├── PASOS_SIMPLES.md
    │   │   ├── Procfile
    │   │   ├── REQUERIMIENTOS_IMPLEMENTACION.md
    │   │   ├── SISTEMA_CAPTURA_CRUDO.md
    │   │   ├── SOLUCION_SQL_DIRECTA.sql
    │   │   ├── SOLUTION_SUMMARY.md
    │   │   ├── SQL_AGREGAR_SOLO_FALTANTES.sql
    │   │   ├── __init__.py
    │   │   ├── actualizar_fuentes.py
    │   │   ├── actualizar_fuentes_recientes.py
    │   │   ├── actualizar_tipo_propiedad.py
    │   │   ├── alter_column.sql
    │   │   ├── alter_column_max.py
    │   │   ├── alter_columns.py
    │   │   ├── asgi.py
    │   │   ├── borrar_requerimientos.py
    │   │   ├── borrar_requerimientos_sin_confirmacion.py
    │   │   ├── check.py
    │   │   ├── check2.py
    │   │   ├── check3.py
    │   │   ├── check_api.py
    │   │   ├── check_api2.py
    │   │   ├── check_atributos.py
    │   │   ├── check_campos.py
    │   │   ├── check_column_lengths.py
    │   │   ├── check_columns.py
    │   │   ├── check_columns2.py
    │   │   ├── check_constraint.py
    │   │   ├── check_excel_columns.py
    │   │   ├── check_fuentes.py
    │   │   ├── check_icons.py
    │   │   ├── check_import.py
    │   │   ├── check_imported.py
    │   │   ├── check_json.py
    │   │   ├── check_json2.py
    │   │   ├── check_last.py
    │   │   ├── check_mapping.py
    │   │   ├── check_mapping2.py
    │   │   ├── check_property_images_table.py
    │   │   ├── check_propifai_image_tables.py
    │   │   ├── check_propifai_images.py
    │   │   ├── check_relation.py
    │   │   ├── check_schema.py
    │   │   ├── check_schema_fixed.py
    │   │   ├── check_tipo_propiedad.py
    │   │   ├── check_urls.py
    │   │   ├── check_zonas.py
    │   │   ├── clear_cache_simple.py
    │   │   ├── clear_cache_windows.py
    │   │   ├── clear_template_cache.py
    │   │   ├── crear_mapeo_ubicaciones.py
    │   │   ├── debug_excel.py
    │   │   ├── debug_logs.txt
    │   │   ├── diagnosticar_acm_propifai.py
    │   │   ├── diagnosticar_acm_propifai_fixed.py
    │   │   ├── diagnosticar_acm_simple.py
    │   │   ├── explore_all_tables.py
    │   │   ├── explore_district_mapping.py
    │   │   ├── explore_location_tables.py
    │   │   ├── explore_properties_table.py
    │   │   ├── explore_propifai_table.py
    │   │   ├── explore_propifai_tables.py
    │   │   ├── final_test.py
    │   │   ├── fix_constraint.py
    │   │   ├── heatmap_current.html
    │   │   ├── heatmap_final.html
    │   │   ├── heatmap_new.html
    │   │   ├── heatmap_output.html
    │   │   ├── heatmap_simple_output.html
    │   │   ├── last_req.py
    │   │   ├── manage.py
    │   │   ├── mapeo_tipo_propiedad.py
    │   │   ├── mapeo_ubicaciones_propifai.json
    │   │   ├── quick_check.py
    │   │   ├── quick_test.py
    │   │   ├── routers.py
    │   │   ├── settings.py
    │   │   ├── show_fields.py
    │   │   ├── startup.sh
    │   │   ├── temp_check.py
    │   │   ├── test_acm_markers.py
    │   │   ├── test_acm_markers_fixed.py
    │   │   ├── test_acm_propifai.py
    │   │   ├── test_acm_propifai_coords.py
    │   │   ├── test_admin.py
    │   │   ├── test_all_ports.py
    │   │   ├── test_api_crear_propiedad.py
    │   │   ├── test_api_directo.py
    │   │   ├── test_api_externa.py
    │   │   ├── test_api_externa_actual.py
    │   │   ├── test_azure_storage.py
    │   │   ├── test_celery_simple.py
    │   │   ├── test_celery_task.py
    │   │   ├── test_client_lista.py
    │   │   ├── test_configurar_jerarquia.py
    │   │   ├── test_correccion_imagenes.py
    │   │   ├── test_crear_pais.py
    │   │   ├── test_crear_pais_final.py
    │   │   ├── test_cuadrantizacion_jerarquia.py
    │   │   ├── test_db_connection.py
    │   │   ├── test_deepseek.py
    │   │   ├── test_distritos_error.py
    │   │   ├── test_filtro_distrito.py
    │   │   ├── test_filtros_presupuesto.py
    │   │   ├── test_final_verification.py
    │   │   ├── test_fix_imagenes.py
    │   │   ├── test_heatmap_page.py
    │   │   ├── test_heatmap_simple.py
    │   │   ├── test_ia.py
    │   │   ├── test_ia2.py
    │   │   ├── test_ia3.py
    │   │   ├── test_ia_requerimientos.py
    │   │   ├── test_image_urls.py
    │   │   ├── test_imagen_url.py
    │   │   ├── test_imagenes.py
    │   │   ├── test_imagenes_completo.py
    │   │   ├── test_imagenes_final.py
    │   │   ├── test_import_debug.py
    │   │   ├── test_jerarquia_simple.py
    │   │   ├── test_lista_client.py
    │   │   ├── test_lista_final.py
    │   │   ├── test_margenes.py
    │   │   ├── test_masivo_limitado.py
    │   │   ├── test_matching_analysis.py
    │   │   ├── test_matching_analysis2.py
    │   │   ├── test_matching_analysis3.py
    │   │   ├── test_matching_corregido.py
    │   │   ├── test_mcp.py
    │   │   ├── test_mcp2.py
    │   │   ├── test_no_cache.py
    │   │   ├── test_nueva_grilla.py
    │   │   ├── test_pais_simple.py
    │   │   ├── test_procesamiento_ia.py
    │   │   ├── test_rapido_imagenes.py
    │   │   ├── test_render_lista.py
    │   │   ├── test_requerimientos.csv
    │   │   ├── test_simple_final.py
    │   │   ├── test_sql_syntax.py
    │   │   ├── test_tarea_completa.py
    │   │   ├── test_template_render.py
    │   │   ├── test_template_simple.py
    │   │   ├── test_unnamed_fix.py
    │   │   ├── test_url_encoding.py
    │   │   ├── test_url_simple.py
    │   │   ├── test_urls_completas.py
    │   │   ├── test_view.py
    │   │   ├── test_visualizacion_propifai.py
    │   │   ├── urls.py
    │   │   ├── verificar_atributos.py
    │   │   ├── verificar_cambios_final.py
    │   │   ├── verificar_columnas_propifai.py
    │   │   ├── verificar_distritos.py
    │   │   ├── verificar_estandarizacion.py
    │   │   ├── verificar_fuente_red.py
    │   │   ├── verificar_fuentes_excel.py
    │   │   ├── verificar_fuentes_excel2.py
    │   │   ├── verificar_fuentes_importadas.py
    │   │   ├── verificar_importacion.py
    │   │   ├── verificar_importacion_final.py
    │   │   ├── verificar_solucion_propifai.py
    │   │   ├── views.py
    │   │   └── wsgi.py
    │   ├── .deployment
    │   ├── .gitignore
    │   ├── AZURE_DEPLOYMENT_FIX.md
    │   ├── DEPLOY_INSTRUCTIONS.md
    │   ├── FASE0_ANALISIS_RESUMEN.md
    │   ├── FASE1_IMPLEMENTACION.md
    │   ├── MARKET_ANALYSIS_IMPLEMENTACION.md
    │   ├── README.md
    │   ├── RESUMEN_MARKET_ANALYSIS.md
    │   ├── SOLUCION_PROPIEDADES_PROPIFY.md
    │   ├── acceso_directo.py
    │   ├── analizar_html_real.py
    │   ├── analizar_html_simple.py
    │   ├── analizar_requerimientos_sin_match.py
    │   ├── analyze_template.py
    │   ├── application.py
    │   ├── borrar_propiedades_raw.py
    │   ├── borrar_propiedades_raw_auto.py
    │   ├── campos_propiedadraw_simple.py
    │   ├── campos_propiedadraw_tabla.txt
    │   ├── check_api.py
    │   ├── check_api_detail.py
    │   ├── check_blocks.py
    │   ├── check_css.py
    │   ├── check_css_simple.py
    │   ├── check_heatmap_html.py
    │   ├── check_heatmap_live.py
    │   ├── check_heatmap_properties.py
    │   ├── check_html.py
    │   ├── check_html_balance.py
    │   ├── check_propifai_fields.py
    │   ├── check_scripts.py
    │   ├── check_server_version.py
    │   ├── check_template_error.py
    │   ├── check_terrenos.py
    │   ├── convert_svg_to_png.py
    │   ├── convert_svg_to_png_cairo.py
    │   ├── count_blocks.py
    │   ├── create_png_data_url.py
    │   ├── create_svg_data_url.py
    │   ├── debug_checkboxes.py
    │   ├── debug_detallado.py
    │   ├── debug_propifai_terrenos.py
    │   ├── debug_propify_issue.py
    │   ├── debug_simple.py
    │   ├── diagnostic_error.py
    │   ├── diagnostic_error2.py
    │   ├── diagnostico_contexto_real.py
    │   ├── diagnostico_final.py
    │   ├── diagnostico_propifai.py
    │   ├── diagnostico_rapido.py
    │   ├── error_full.html
    │   ├── fix_template.py
    │   ├── fix_template_simple.py
    │   ├── generar_excel_campos.py
    │   ├── generate_data_url.py
    │   ├── get_propifai_coords.py
    │   ├── heatmap_debug.html
    │   ├── html_fragmento.txt
    │   ├── importar_propiedades_raw.py
    │   ├── listar_campos_propiedadraw.py
    │   ├── masivo_output.html
    │   ├── oryx-manifest.toml
    │   ├── pin_propify_data_url.txt
    │   ├── png_data_url.txt
    │   ├── propiedades_propify.html
    │   ├── requirements.txt
    │   ├── runtime.txt
    │   ├── svg_data_url.txt
    │   ├── test_acm.py
    │   ├── test_checkbox_logic.py
    │   ├── test_completo_terrenos.py
    │   ├── test_conexion_propifai.py
    │   ├── test_contexto_simple.py
    │   ├── test_conversion.py
    │   ├── test_correccion_terrenos.py
    │   ├── test_depuracion.py
    │   ├── test_depuracion_simple.py
    │   ├── test_despues_cambio.py
    │   ├── test_directo_simple.py
    │   ├── test_filtro_usuario.py
    │   ├── test_filtros_checkbox.py
    │   ├── test_final.ps1
    │   ├── test_final.py
    │   ├── test_final_completo.py
    │   ├── test_final_matching.py
    │   ├── test_final_simple.py
    │   ├── test_final_terrenos.py
    │   ├── test_frontend_logic.py
    │   ├── test_google_maps_key.py
    │   ├── test_google_maps_key_simple.py
    │   ├── test_heatmap_api.py
    │   ├── test_heatmap_html.py
    │   ├── test_heatmap_page.py
    │   ├── test_heatmap_page_simple.py
    │   ├── test_heatmap_ps.ps1
    │   ├── test_heatmap_real.py
    │   ├── test_http.py
    │   ├── test_http_acm.py
    │   ├── test_http_acm_arequipa.py
    │   ├── test_http_checkboxes.py
    │   ├── test_http_filtros.py
    │   ├── test_import.py
    │   ├── test_intercalado_simple.py
    │   ├── test_js_loaded.py
    │   ├── test_logica_mejorada.py
    │   ├── test_logs.py
    │   ├── test_markers.ps1
    │   ├── test_market_analysis_heatmap.py
    │   ├── test_matching_debug.py
    │   ├── test_matching_final.py
    │   ├── test_matching_final_v2.py
    │   ├── test_matching_resumen.py
    │   ├── test_pagina_web.py
    │   ├── test_paginacion.py
    │   ├── test_paginacion_propify.py
    │   ├── test_performance.ps1
    │   ├── test_performance_simple.ps1
    │   ├── test_png_access.html
    │   ├── test_precio_m2_propifai.py
    │   ├── test_propifai_db.py
    │   ├── test_propifai_directo.py
    │   ├── test_propify_directo.py
    │   ├── test_propify_directo_final.py
    │   ├── test_propify_filtros.py
    │   ├── test_rapido_propify.py
    │   ├── test_real_data.py
    │   ├── test_simple.ps1
    │   ├── test_simple.py
    │   ├── test_url_final.py
    │   ├── test_url_propify.py
    │   ├── test_vista.py
    │   ├── test_vista_completa.py
    │   ├── test_vista_directa.py
    │   ├── test_vista_directo.py
    │   ├── test_vista_final.py
    │   ├── test_vista_masivo.py
    │   ├── test_vista_optimizada.py
    │   ├── test_vista_propiedades.py
    │   ├── test_vista_propify.py
    │   ├── test_web_page.py
    │   ├── verificacion_final_imagenes.py
    │   ├── verificacion_final_servidor.py
    │   ├── verificacion_simple.py
    │   ├── verificar_campo_es_propify.py
    │   ├── verificar_campo_identificador_externo.py
    │   ├── verificar_contexto_directo.py
    │   ├── verificar_datos.py
    │   ├── verificar_html_directo.py
    │   ├── verificar_html_final.py
    │   ├── verificar_html_propify.py
    │   ├── verificar_html_real.py
    │   ├── verificar_html_simple_win.py
    │   ├── verificar_implementacion.py
    │   ├── verificar_problema_usuario.py
    │   ├── verificar_propify_directo.py
    │   ├── verificar_rapido.py
    │   ├── verificar_servidor_real.py
    │   ├── verificar_simple.py
    │   ├── verificar_template_propify.py
    │   ├── verificar_vista_completa.py
    │   └── verify_heatmap.py
    ├── mcp-deepseek-requerimientos/
    │   ├── build/
    │   │   ├── index-simple.d.ts
    │   │   ├── index-simple.d.ts.map
    │   │   ├── index-simple.js
    │   │   ├── index-simple.js.map
    │   │   ├── index.d.ts
    │   │   ├── index.d.ts.map
    │   │   ├── index.js
    │   │   └── index.js.map
    │   ├── src/
    │   │   ├── index-simple.ts
    │   │   └── index.ts
    │   ├── README.md
    │   ├── mcp_settings_example.json
    │   ├── package-lock.json
    │   ├── package.json
    │   ├── test-import.js
    │   ├── test-server.js
    │   ├── test-tool.js
    │   └── tsconfig.json
    ├── test_capturas/
    ├── webapp/
    │   ├── acm/
    │   │   ├── static/
    │   │   │   └── acm/
    │   │   │       ├── css/
    │   │   │       │   └── acm.css
    │   │   │       ├── img/
    │   │   │       │   └── no-image.svg
    │   │   │       └── js/
    │   │   │           └── acm.js
    │   │   ├── templates/
    │   │   │   └── acm/
    │   │   │       ├── acm_analisis.html
    │   │   │       ├── acm_analisis_compacto.html
    │   │   │       └── acm_base.html
    │   │   ├── __init__.py
    │   │   ├── apps.py
    │   │   ├── urls.py
    │   │   ├── utils.py
    │   │   └── views.py
    │   ├── analisis_crm/
    │   │   ├── migrations/
    │   │   │   └── __init__.py
    │   │   ├── templates/
    │   │   │   └── analisis_crm/
    │   │   │       ├── analytics.html
    │   │   │       ├── dashboard.html
    │   │   │       ├── lead_detail.html
    │   │   │       └── lead_list.html
    │   │   ├── __init__.py
    │   │   ├── admin.py
    │   │   ├── apps.py
    │   │   ├── dashboard_debug.log
    │   │   ├── models.py
    │   │   ├── tests.py
    │   │   ├── urls.py
    │   │   └── views.py
    │   ├── api/
    │   │   ├── ANDROID_IMPLEMENTATION_GUIDE.md
    │   │   ├── API_DOCUMENTATION.md
    │   │   ├── __init__.py
    │   │   ├── serializers.py
    │   │   ├── urls.py
    │   │   ├── urls_mejoradas.py
    │   │   ├── views.py
    │   │   └── views_mejoradas.py
    │   ├── captura/
    │   │   ├── migrations/
    │   │   │   ├── 0001_initial.py
    │   │   │   ├── 0002_initial_consolidada.py
    │   │   │   ├── 0003_eventodeteccion_captura_eve_fuente__e6ec8b_idx.py
    │   │   │   └── __init__.py
    │   │   ├── README_SCREENSHOT_OCR.md
    │   │   ├── __init__.py
    │   │   ├── admin.py
    │   │   ├── azure_storage.py
    │   │   ├── captura_screenshot.py
    │   │   ├── detector_tipos.py
    │   │   ├── diff_engine.py
    │   │   ├── extractor_pdf.py
    │   │   ├── mejorador_captura.py
    │   │   ├── models.py
    │   │   ├── tareas_mejoradas.py
    │   │   └── test_captura_screenshot.py
    │   ├── colas/
    │   │   ├── __init__.py
    │   │   ├── celery.py
    │   │   ├── tareas_captura.py
    │   │   ├── tareas_descubrimiento.py
    │   │   └── tasks.py
    │   ├── cuadrantizacion/
    │   │   ├── management/
    │   │   │   ├── commands/
    │   │   │   │   ├── __init__.py
    │   │   │   │   ├── calcular_precios_zonas.py
    │   │   │   │   ├── crear_datos_prueba.py
    │   │   │   │   └── migrar_propiedades_valoracion.py
    │   │   │   └── __init__.py
    │   │   ├── migrations/
    │   │   │   ├── 0001_initial.py
    │   │   │   ├── 0002_alter_zonavalor_options_and_more.py
    │   │   │   ├── 0003_alter_zonavalor_coordenadas.py
    │   │   │   └── __init__.py
    │   │   ├── __init__.py
    │   │   ├── apps.py
    │   │   ├── models.py
    │   │   ├── serializers.py
    │   │   ├── services.py
    │   │   ├── urls.py
    │   │   ├── utils.py
    │   │   └── views.py
    │   ├── eventos/
    │   │   ├── migrations/
    │   │   │   └── __init__.py
    │   │   ├── templates/
    │   │   │   └── eventos/
    │   │   │       ├── dashboard.html
    │   │   │       └── detalle.html
    │   │   ├── __init__.py
    │   │   ├── admin.py
    │   │   ├── apps.py
    │   │   ├── models.py
    │   │   ├── tests.py
    │   │   ├── urls.py
    │   │   └── views.py
    │   ├── ingestas/
    │   │   ├── management/
    │   │   │   ├── commands/
    │   │   │   │   ├── __init__.py
    │   │   │   │   ├── borrar_propiedadraw.py
    │   │   │   │   ├── importar_excel_propiedadraw.py
    │   │   │   │   └── migrar_atributos_a_campos.py
    │   │   │   └── __init__.py
    │   │   ├── migrations/
    │   │   │   ├── 0001_initial.py
    │   │   │   ├── 0002_alter_campodinamico_id_alter_mapeofuente_id_and_more.py
    │   │   │   ├── 0003_propiedadraw_agente_inmobiliario_and_more.py
    │   │   │   ├── 0004_change_fecha_publicacion_to_date.py
    │   │   │   ├── 0005_remove_old_fields.py
    │   │   │   ├── 0006_fix_atributos_extras_nullable.py
    │   │   │   ├── 0007_propiedadraw_estado_propiedad_and_more.py
    │   │   │   ├── 0008_estandarizar_tipo_propiedad.py
    │   │   │   ├── 0009_propiedadraw_identificador_externo.py
    │   │   │   ├── 0010_add_subtipo_propiedad.py
    │   │   │   ├── 0011_add_condicion_propiedad_verificada.py
    │   │   │   ├── 0012_alter_propiedadraw_condicion.py
    │   │   │   └── __init__.py
    │   │   ├── templatetags/
    │   │   │   ├── __init__.py
    │   │   │   └── ingestas_extras.py
    │   │   ├── README_PROCESAMIENTO_IA.md
    │   │   ├── __init__.py
    │   │   ├── admin.py
    │   │   ├── forms.py
    │   │   ├── models.py
    │   │   ├── procesamiento_ia.py
    │   │   ├── services.py
    │   │   ├── services_api.py
    │   │   ├── urls.py
    │   │   └── views.py
    │   ├── market_analysis/
    │   │   ├── migrations/
    │   │   │   └── __init__.py
    │   │   ├── static/
    │   │   │   └── market_analysis/
    │   │   │       └── js/
    │   │   │           ├── dashboard.js
    │   │   │           ├── heatmap-init.js
    │   │   │           └── heatmap.js
    │   │   ├── templates/
    │   │   │   └── market_analysis/
    │   │   │       ├── dashboard.html
    │   │   │       └── heatmap.html
    │   │   ├── __init__.py
    │   │   ├── admin.py
    │   │   ├── apps.py
    │   │   ├── charts.py
    │   │   ├── diagnostic.py
    │   │   ├── models.py
    │   │   ├── tests.py
    │   │   ├── urls.py
    │   │   └── views.py
    │   ├── matching/
    │   │   ├── migrations/
    │   │   │   ├── 0001_initial.py
    │   │   │   └── __init__.py
    │   │   ├── static/
    │   │   │   └── matching/
    │   │   │       └── matching.js
    │   │   ├── templates/
    │   │   │   └── matching/
    │   │   │       ├── partials/
    │   │   │       │   └── resumen_requerimiento.html
    │   │   │       ├── dashboard.html
    │   │   │       └── masivo.html
    │   │   ├── README_MATCHING.md
    │   │   ├── __init__.py
    │   │   ├── admin.py
    │   │   ├── apps.py
    │   │   ├── engine.py
    │   │   ├── models.py
    │   │   ├── serializers.py
    │   │   ├── tests.py
    │   │   ├── urls.py
    │   │   └── views.py
    │   ├── meta_ads/
    │   │   ├── management/
    │   │   │   ├── commands/
    │   │   │   │   ├── __init__.py
    │   │   │   │   └── sync_meta_ads.py
    │   │   │   └── __init__.py
    │   │   ├── migrations/
    │   │   │   ├── 0001_initial.py
    │   │   │   └── __init__.py
    │   │   ├── templates/
    │   │   │   └── meta_ads/
    │   │   │       ├── campaign_list.html
    │   │   │       ├── dashboard.html
    │   │   │       ├── historical_analysis.html
    │   │   │       └── sync.html
    │   │   ├── __init__.py
    │   │   ├── admin.py
    │   │   ├── apps.py
    │   │   ├── models.py
    │   │   ├── services.py
    │   │   ├── tests.py
    │   │   ├── urls.py
    │   │   └── views.py
    │   ├── propifai/
    │   │   ├── migrations/
    │   │   │   ├── 0001_initial.py
    │   │   │   └── __init__.py
    │   │   ├── __init__.py
    │   │   ├── admin.py
    │   │   ├── apps.py
    │   │   ├── mapeo_ubicaciones.py
    │   │   ├── models.py
    │   │   ├── tests.py
    │   │   ├── urls.py
    │   │   └── views.py
    │   ├── requerimientos/
    │   │   ├── data/
    │   │   │   ├── PROCEDIMIENTO_IMPORTACION_INMOBILIARIOS.md
    │   │   │   ├── Pin-propify.png
    │   │   │   ├── inmobiliaria-remax-10-febrero-2026.xlsx
    │   │   │   ├── pin-remax.png
    │   │   │   ├── propiedadesraw2_tipificado.xlsx
    │   │   │   ├── propiedadesraw_corregido (2).xlsx
    │   │   │   ├── propiedadesraw_para_azure.xlsx
    │   │   │   ├── requerimientos_completo.xlsx
    │   │   │   ├── requerimientos_inmobiliarios.xlsx
    │   │   │   └── ~$propiedadesraw_para_azure.xlsx
    │   │   ├── management/
    │   │   │   ├── commands/
    │   │   │   │   ├── __init__.py
    │   │   │   │   ├── importar_requerimientos_excel.py
    │   │   │   │   └── importar_requerimientos_inmobiliarios.py
    │   │   │   └── __init__.py
    │   │   ├── migrations/
    │   │   │   ├── 0001_initial.py
    │   │   │   ├── 0002_remove_requerimientoraw_requerimien_tipo_re_68263b_idx_and_more.py
    │   │   │   ├── 0003_requerimiento_and_more.py
    │   │   │   ├── 0004_add_fuente_red_inmobiliaria.py
    │   │   │   └── __init__.py
    │   │   ├── README_ANALISIS_TEMPORAL.md
    │   │   ├── README_MEJORAS_PROGRESO.md
    │   │   ├── __init__.py
    │   │   ├── admin.py
    │   │   ├── analytics.py
    │   │   ├── apps.py
    │   │   ├── check_excel_structure.py
    │   │   ├── check_rows.py
    │   │   ├── diagnostico_fuente.py
    │   │   ├── diagnostico_simple.py
    │   │   ├── forms.py
    │   │   ├── importar_nuevo_excel.py
    │   │   ├── inspeccionar_nuevo_excel.py
    │   │   ├── inspeccionar_simple.py
    │   │   ├── inspect_excel.py
    │   │   ├── models.py
    │   │   ├── services.py
    │   │   ├── tasks.py
    │   │   ├── test_import.py
    │   │   ├── test_import_full.py
    │   │   ├── test_import_simple.py
    │   │   ├── tests.py
    │   │   ├── urls.py
    │   │   └── views.py
    │   ├── semillas/
    │   │   ├── migrations/
    │   │   │   ├── 0001_initial.py
    │   │   │   ├── 0002_fuenteweb_categoria.py
    │   │   │   ├── 0003_fuenteweb_es_semilla_activa_and_more.py
    │   │   │   ├── 0004_alter_fuenteweb_id.py
    │   │   │   └── __init__.py
    │   │   ├── __init__.py
    │   │   ├── admin.py
    │   │   ├── descubrimiento.py
    │   │   └── models.py
    │   ├── static/
    │   │   ├── eventos/
    │   │   │   └── css/
    │   │   │       └── grafico_fijo.css
    │   │   ├── requerimientos/
    │   │   │   ├── data/
    │   │   │   │   ├── Pin-propify.png
    │   │   │   │   ├── Pin-propify.svg
    │   │   │   │   ├── pin-remax.png
    │   │   │   │   ├── test-pin.svg
    │   │   │   │   └── test.txt
    │   │   │   └── js/
    │   │   │       └── dashboard_analytics.js
    │   │   └── test_image.html
    │   ├── staticfiles/
    │   │   └── admin/
    │   │       ├── css/
    │   │       │   ├── vendor/
    │   │       │   │   └── select2/
    │   │       │   │       ├── LICENSE-SELECT2.md
    │   │       │   │       ├── select2.css
    │   │       │   │       └── select2.min.css
    │   │       │   ├── autocomplete.css
    │   │       │   ├── base.css
    │   │       │   ├── changelists.css
    │   │       │   ├── dark_mode.css
    │   │       │   ├── dashboard.css
    │   │       │   ├── forms.css
    │   │       │   ├── login.css
    │   │       │   ├── nav_sidebar.css
    │   │       │   ├── responsive.css
    │   │       │   ├── responsive_rtl.css
    │   │       │   ├── rtl.css
    │   │       │   ├── unusable_password_field.css
    │   │       │   └── widgets.css
    │   │       ├── img/
    │   │       │   ├── gis/
    │   │       │   │   ├── move_vertex_off.svg
    │   │       │   │   └── move_vertex_on.svg
    │   │       │   ├── LICENSE
    │   │       │   ├── README.txt
    │   │       │   ├── calendar-icons.svg
    │   │       │   ├── icon-addlink.svg
    │   │       │   ├── icon-alert.svg
    │   │       │   ├── icon-calendar.svg
    │   │       │   ├── icon-changelink.svg
    │   │       │   ├── icon-clock.svg
    │   │       │   ├── icon-deletelink.svg
    │   │       │   ├── icon-hidelink.svg
    │   │       │   ├── icon-no.svg
    │   │       │   ├── icon-unknown-alt.svg
    │   │       │   ├── icon-unknown.svg
    │   │       │   ├── icon-viewlink.svg
    │   │       │   ├── icon-yes.svg
    │   │       │   ├── inline-delete.svg
    │   │       │   ├── search.svg
    │   │       │   ├── selector-icons.svg
    │   │       │   ├── sorting-icons.svg
    │   │       │   ├── tooltag-add.svg
    │   │       │   └── tooltag-arrowright.svg
    │   │       └── js/
    │   │           ├── admin/
    │   │           │   ├── DateTimeShortcuts.js
    │   │           │   └── RelatedObjectLookups.js
    │   │           ├── vendor/
    │   │           │   ├── jquery/
    │   │           │   │   ├── LICENSE.txt
    │   │           │   │   ├── jquery.js
    │   │           │   │   └── jquery.min.js
    │   │           │   ├── select2/
    │   │           │   │   ├── i18n/
    │   │           │   │   │   ├── af.js
    │   │           │   │   │   ├── ar.js
    │   │           │   │   │   ├── az.js
    │   │           │   │   │   ├── bg.js
    │   │           │   │   │   ├── bn.js
    │   │           │   │   │   ├── bs.js
    │   │           │   │   │   ├── ca.js
    │   │           │   │   │   ├── cs.js
    │   │           │   │   │   ├── da.js
    │   │           │   │   │   ├── de.js
    │   │           │   │   │   ├── dsb.js
    │   │           │   │   │   ├── el.js
    │   │           │   │   │   ├── en.js
    │   │           │   │   │   ├── es.js
    │   │           │   │   │   ├── et.js
    │   │           │   │   │   ├── eu.js
    │   │           │   │   │   ├── fa.js
    │   │           │   │   │   ├── fi.js
    │   │           │   │   │   ├── fr.js
    │   │           │   │   │   ├── gl.js
    │   │           │   │   │   ├── he.js
    │   │           │   │   │   ├── hi.js
    │   │           │   │   │   ├── hr.js
    │   │           │   │   │   ├── hsb.js
    │   │           │   │   │   ├── hu.js
    │   │           │   │   │   ├── hy.js
    │   │           │   │   │   ├── id.js
    │   │           │   │   │   ├── is.js
    │   │           │   │   │   ├── it.js
    │   │           │   │   │   ├── ja.js
    │   │           │   │   │   ├── ka.js
    │   │           │   │   │   ├── km.js
    │   │           │   │   │   ├── ko.js
    │   │           │   │   │   ├── lt.js
    │   │           │   │   │   ├── lv.js
    │   │           │   │   │   ├── mk.js
    │   │           │   │   │   ├── ms.js
    │   │           │   │   │   ├── nb.js
    │   │           │   │   │   ├── ne.js
    │   │           │   │   │   ├── nl.js
    │   │           │   │   │   ├── pl.js
    │   │           │   │   │   ├── ps.js
    │   │           │   │   │   ├── pt-BR.js
    │   │           │   │   │   ├── pt.js
    │   │           │   │   │   ├── ro.js
    │   │           │   │   │   ├── ru.js
    │   │           │   │   │   ├── sk.js
    │   │           │   │   │   ├── sl.js
    │   │           │   │   │   ├── sq.js
    │   │           │   │   │   ├── sr-Cyrl.js
    │   │           │   │   │   ├── sr.js
    │   │           │   │   │   ├── sv.js
    │   │           │   │   │   ├── th.js
    │   │           │   │   │   ├── tk.js
    │   │           │   │   │   ├── tr.js
    │   │           │   │   │   ├── uk.js
    │   │           │   │   │   ├── vi.js
    │   │           │   │   │   ├── zh-CN.js
    │   │           │   │   │   └── zh-TW.js
    │   │           │   │   ├── LICENSE.md
    │   │           │   │   ├── select2.full.js
    │   │           │   │   └── select2.full.min.js
    │   │           │   └── xregexp/
    │   │           │       ├── LICENSE.txt
    │   │           │       ├── xregexp.js
    │   │           │       └── xregexp.min.js
    │   │           ├── SelectBox.js
    │   │           ├── SelectFilter2.js
    │   │           ├── actions.js
    │   │           ├── autocomplete.js
    │   │           ├── calendar.js
    │   │           ├── cancel.js
    │   │           ├── change_form.js
    │   │           ├── core.js
    │   │           ├── filters.js
    │   │           ├── inlines.js
    │   │           ├── jquery.init.js
    │   │           ├── nav_sidebar.js
    │   │           ├── popup_response.js
    │   │           ├── prepopulate.js
    │   │           ├── prepopulate_init.js
    │   │           ├── theme.js
    │   │           ├── unusable_password_field.js
    │   │           └── urlify.js
    │   ├── templates/
    │   │   ├── admin/
    │   │   │   ├── ingestas/
    │   │   │   │   ├── borrar_todo_confirm.html
    │   │   │   │   └── importar_excel.html
    │   │   │   └── requerimientos/
    │   │   │       ├── importar_excel.html
    │   │   │       └── requerimiento_change_list.html
    │   │   ├── cuadrantizacion/
    │   │   │   ├── _tree_node.html
    │   │   │   ├── configurar_jerarquia.html
    │   │   │   ├── heatmap.html
    │   │   │   └── mapa_zonas.html
    │   │   ├── ingestas/
    │   │   │   ├── detalle_propiedad.html
    │   │   │   ├── editar_propiedad.html
    │   │   │   ├── index.html
    │   │   │   ├── lista_propiedades_rediseno.html
    │   │   │   ├── lista_propiedades_rediseno.html.backup2
    │   │   │   ├── lista_propiedades_rediseno_backup.html
    │   │   │   ├── lista_propiedades_rediseno_debug.html
    │   │   │   ├── procesar_ia.html
    │   │   │   ├── resultado.html
    │   │   │   ├── resultado_ia.html
    │   │   │   ├── subir.html
    │   │   │   ├── tabla_propiedades_completa.html
    │   │   │   └── validar.html
    │   │   ├── market_analysis/
    │   │   │   ├── dashboard.html
    │   │   │   ├── data_quality_dashboard.html
    │   │   │   ├── data_quality_dashboard_fixed.html
    │   │   │   ├── property_list_dashboard.html
    │   │   │   └── property_quick_detail.html
    │   │   ├── propifai/
    │   │   │   ├── dashboard_calidad_cartera.html
    │   │   │   ├── lista_propiedades_propify.html
    │   │   │   ├── lista_propiedades_propify_clonado.html
    │   │   │   ├── lista_propiedades_propify_rediseno.html
    │   │   │   ├── property_visits_dashboard.html
    │   │   │   ├── property_visits_dashboard.html.backup
    │   │   │   └── propiedades_simple.html
    │   │   ├── requerimientos/
    │   │   │   ├── dashboard_analisis.html
    │   │   │   └── lista.html
    │   │   ├── base.html
    │   │   ├── capturas.html
    │   │   ├── capturas_mejoradas.html
    │   │   ├── fuentes_web.html
    │   │   └── index.html
    │   ├── .env
    │   ├── .env.example
    │   ├── .gitignore
    │   ├── BORRAR_PROPIEDADRAW.md
    │   ├── COMO_USAR_CAPTURAS.md
    │   ├── CORRECCION_CAMPOS_DINAMICOS.md
    │   ├── CUADRANTIZACION_IMPLEMENTADA.md
    │   ├── DEPLOYMENT_CHECKLIST.md
    │   ├── EJECUTAR_BORRADO_AHORA.txt
    │   ├── FIX_BASE_DATOS.md
    │   ├── GUIA_USO_CAPTURAS.md
    │   ├── INICIO_RAPIDO_CAPTURA.md
    │   ├── INSTRUCCIONES_EJECUCION.txt
    │   ├── PASOS_SIMPLES.md
    │   ├── Procfile
    │   ├── REQUERIMIENTOS_IMPLEMENTACION.md
    │   ├── RESUMEN_REIMPORTACION.txt
    │   ├── SISTEMA_CAPTURA_CRUDO.md
    │   ├── SOLUCION_DEFINITIVA.md
    │   ├── SOLUCION_SQL_DIRECTA.sql
    │   ├── SOLUTION_SUMMARY.md
    │   ├── SQL_AGREGAR_SOLO_FALTANTES.sql
    │   ├── __init__.py.backup
    │   ├── actualizar_fuentes.py
    │   ├── actualizar_fuentes_recientes.py
    │   ├── actualizar_tipo_propiedad.py
    │   ├── agregar_columnas_manual.py
    │   ├── alter_column.sql
    │   ├── alter_column_max.py
    │   ├── alter_columns.py
    │   ├── aplicar_migraciones.py
    │   ├── aplicar_migraciones_forzado.py
    │   ├── asgi.py
    │   ├── borrar_directo.ps1
    │   ├── borrar_final.py
    │   ├── borrar_propiedadraw.bat
    │   ├── borrar_propiedadraw.py
    │   ├── borrar_propiedadraw_auto.py
    │   ├── borrar_propiedadraw_si.py
    │   ├── borrar_requerimientos.py
    │   ├── borrar_requerimientos_sin_confirmacion.py
    │   ├── borrar_simple_final.py
    │   ├── borrar_ultimo.py
    │   ├── check.py
    │   ├── check2.py
    │   ├── check3.py
    │   ├── check_agents.py
    │   ├── check_api.py
    │   ├── check_api2.py
    │   ├── check_atributos.py
    │   ├── check_campos.py
    │   ├── check_chart_script.py
    │   ├── check_column_lengths.py
    │   ├── check_columns.py
    │   ├── check_columns2.py
    │   ├── check_constraint.py
    │   ├── check_event_counts.py
    │   ├── check_events_schema.py
    │   ├── check_excel_columns.py
    │   ├── check_filters.py
    │   ├── check_fuentes.py
    │   ├── check_historical_data.py
    │   ├── check_html_order.py
    │   ├── check_html_order_with_dates.py
    │   ├── check_icons.py
    │   ├── check_import.py
    │   ├── check_imported.py
    │   ├── check_json.py
    │   ├── check_json2.py
    │   ├── check_last.py
    │   ├── check_mapping.py
    │   ├── check_mapping2.py
    │   ├── check_new_template.py
    │   ├── check_order.py
    │   ├── check_order_view.py
    │   ├── check_panel.py
    │   ├── check_properties_json.py
    │   ├── check_property_images_table.py
    │   ├── check_propifai_image_tables.py
    │   ├── check_propifai_images.py
    │   ├── check_relation.py
    │   ├── check_schema.py
    │   ├── check_schema_fixed.py
    │   ├── check_table_rows.py
    │   ├── check_template_data.py
    │   ├── check_tipo_propiedad.py
    │   ├── check_urls.py
    │   ├── check_view_data.py
    │   ├── check_zonas.py
    │   ├── clear_cache_simple.py
    │   ├── clear_cache_windows.py
    │   ├── clear_template_cache.py
    │   ├── comparar_importacion.py
    │   ├── corregir_anticresis_final.py
    │   ├── corregir_condicion_choices.py
    │   ├── corregir_condicion_simple.py
    │   ├── corregir_id_auto.py
    │   ├── corregir_id_directo.py
    │   ├── corregir_id_final.py
    │   ├── corregir_id_instrucciones.sql
    │   ├── corregir_id_propiedad.py
    │   ├── corregir_id_sqlcmd.bat
    │   ├── crear_mapeo_ubicaciones.py
    │   ├── crear_migracion_faltante.py
    │   ├── dashboard_fragment.html
    │   ├── dashboard_new.html
    │   ├── dashboard_output.html
    │   ├── debug_error.py
    │   ├── debug_error2.py
    │   ├── debug_error3.py
    │   ├── debug_excel.py
    │   ├── debug_json.py
    │   ├── debug_leads.py
    │   ├── debug_logs.txt
    │   ├── debug_meta_token.py
    │   ├── debug_real_data.py
    │   ├── debug_view.py
    │   ├── diagnostic_local.py
    │   ├── diagnostic_propifai.py
    │   ├── diagnosticar_acm_propifai.py
    │   ├── diagnosticar_acm_propifai_fixed.py
    │   ├── diagnosticar_acm_simple.py
    │   ├── diagnostico_campo_id.py
    │   ├── diagnostico_detallado.py
    │   ├── diagnostico_grafico_leads.py
    │   ├── ejecutar_sql_fix.py
    │   ├── estado_actual.py
    │   ├── explore_all_tables.py
    │   ├── explore_assigned_tables.py
    │   ├── explore_district_mapping.py
    │   ├── explore_lead_statuses.py
    │   ├── explore_location_tables.py
    │   ├── explore_properties_table.py
    │   ├── explore_propifai_table.py
    │   ├── explore_propifai_tables.py
    │   ├── extract_error.py
    │   ├── extract_kpi.py
    │   ├── fake_migrate.py
    │   ├── fetch_and_analyze.py
    │   ├── fetch_and_check.py
    │   ├── final_dashboard_test.py
    │   ├── final_test.py
    │   ├── find_js_errors.py
    │   ├── fix_admin_error.py
    │   ├── fix_constraint.py
    │   ├── full_dashboard.html
    │   ├── get_crm_leads_schema.py
    │   ├── get_full_html.py
    │   ├── get_rendered_html.py
    │   ├── heatmap_current.html
    │   ├── heatmap_final.html
    │   ├── heatmap_new.html
    │   ├── heatmap_output.html
    │   ├── heatmap_simple_output.html
    │   ├── identificar_anticresis.py
    │   ├── importar_corregido_final.py
    │   ├── importar_definitivo.py
    │   ├── importar_excel_corregido.py
    │   ├── importar_final_robusto.py
    │   ├── importar_simple.py
    │   ├── inspeccionar_excel.py
    │   ├── last_req.py
    │   ├── manage.py
    │   ├── mapeo_tipo_propiedad.py
    │   ├── mapeo_ubicaciones_propifai.json
    │   ├── modify_template.py
    │   ├── nuclear_fix.py
    │   ├── poblar_ejemplo.py
    │   ├── probar_admin.py
    │   ├── quick_check.py
    │   ├── quick_dashboard_test.py
    │   ├── quick_test.py
    │   ├── reimportar_completo.bat
    │   ├── reimportar_excel_completo.py
    │   ├── rendered_dashboard.html
    │   ├── reparar_esquema_final.py
    │   ├── revertir_cambios_condicion.py
    │   ├── routers.py
    │   ├── settings.py
    │   ├── show_fields.py
    │   ├── simple_data_check.py
    │   ├── simplified_test.html
    │   ├── sql_fix_columns.sql
    │   ├── startup.sh
    │   ├── sync_historical_meta_ads.py
    │   ├── temp.html
    │   ├── temp_check.py
    │   ├── temp_count.py
    │   ├── test.html
    │   ├── test_acm_markers.py
    │   ├── test_acm_markers_fixed.py
    │   ├── test_acm_propifai.py
    │   ├── test_acm_propifai_coords.py
    │   ├── test_admin.py
    │   ├── test_all_ports.py
    │   ├── test_analisis_crm.py
    │   ├── test_api_crear_propiedad.py
    │   ├── test_api_directo.py
    │   ├── test_api_externa.py
    │   ├── test_api_externa_actual.py
    │   ├── test_azure_storage.py
    │   ├── test_celery_simple.py
    │   ├── test_celery_task.py
    │   ├── test_client_lista.py
    │   ├── test_conexion_simple.py
    │   ├── test_configurar_jerarquia.py
    │   ├── test_correccion_imagenes.py
    │   ├── test_correcciones.py
    │   ├── test_crear_pais.py
    │   ├── test_crear_pais_final.py
    │   ├── test_cuadrantizacion_jerarquia.py
    │   ├── test_dashboard.py
    │   ├── test_dashboard_data.py
    │   ├── test_dashboard_load.py
    │   ├── test_dashboard_page.py
    │   ├── test_db_connection.py
    │   ├── test_deepseek.py
    │   ├── test_distritos_error.py
    │   ├── test_eventos_connection.py
    │   ├── test_eventos_dashboard.py
    │   ├── test_eventos_mejoras.py
    │   ├── test_eventos_real.py
    │   ├── test_eventos_simple.py
    │   ├── test_eventos_web.py
    │   ├── test_filtro_distrito.py
    │   ├── test_filtros_presupuesto.py
    │   ├── test_final.py
    │   ├── test_final_dashboard.py
    │   ├── test_final_graph.py
    │   ├── test_final_verification.py
    │   ├── test_fix_imagenes.py
    │   ├── test_heatmap_page.py
    │   ├── test_heatmap_simple.py
    │   ├── test_historical_fix.py
    │   ├── test_ia.py
    │   ├── test_ia2.py
    │   ├── test_ia3.py
    │   ├── test_ia_requerimientos.py
    │   ├── test_image_urls.py
    │   ├── test_imagen_url.py
    │   ├── test_imagenes.py
    │   ├── test_imagenes_completo.py
    │   ├── test_imagenes_final.py
    │   ├── test_import_debug.py
    │   ├── test_javascript.html
    │   ├── test_javascript_execution.py
    │   ├── test_jerarquia_simple.py
    │   ├── test_json_output.py
    │   ├── test_lista_client.py
    │   ├── test_lista_final.py
    │   ├── test_margenes.py
    │   ├── test_masivo_limitado.py
    │   ├── test_matching_analysis.py
    │   ├── test_matching_analysis2.py
    │   ├── test_matching_analysis3.py
    │   ├── test_matching_corregido.py
    │   ├── test_mcp.py
    │   ├── test_mcp2.py
    │   ├── test_meta_token.py
    │   ├── test_no_cache.py
    │   ├── test_nueva_grilla.py
    │   ├── test_output.html
    │   ├── test_page_load.py
    │   ├── test_pais_simple.py
    │   ├── test_procesamiento_ia.py
    │   ├── test_rapido_imagenes.py
    │   ├── test_render_lista.py
    │   ├── test_render_view.py
    │   ├── test_requerimientos.csv
    │   ├── test_simple_final.py
    │   ├── test_simple_request.py
    │   ├── test_simplified_init.py
    │   ├── test_sql_syntax.py
    │   ├── test_tarea_completa.py
    │   ├── test_template_render.py
    │   ├── test_template_simple.py
    │   ├── test_unnamed_fix.py
    │   ├── test_url_encoding.py
    │   ├── test_url_simple.py
    │   ├── test_urls_completas.py
    │   ├── test_view.py
    │   ├── test_view_direct.py
    │   ├── test_view_json.py
    │   ├── test_view_logic.py
    │   ├── test_vista_eventos.py
    │   ├── test_visualizacion_propifai.py
    │   ├── ultimo_intento.py
    │   ├── urls.py
    │   ├── verificacion_completa_final.py
    │   ├── verificacion_final_admin.py
    │   ├── verificacion_final_completa.py
    │   ├── verificar_admin.py
    │   ├── verificar_admin_config.py
    │   ├── verificar_atributos.py
    │   ├── verificar_borrado.py
    │   ├── verificar_cambios_completos.py
    │   ├── verificar_cambios_final.py
    │   ├── verificar_campo_valoraciones.py
    │   ├── verificar_campos.bat
    │   ├── verificar_campos_modelo.py
    │   ├── verificar_campos_nuevos.py
    │   ├── verificar_columnas_propifai.py
    │   ├── verificar_columnas_simple.py
    │   ├── verificar_condicion_excel.py
    │   ├── verificar_distritos.py
    │   ├── verificar_esquema.py
    │   ├── verificar_esquema_completo.py
    │   ├── verificar_estado_final.py
    │   ├── verificar_estandarizacion.py
    │   ├── verificar_fuente_red.py
    │   ├── verificar_fuentes_excel.py
    │   ├── verificar_fuentes_excel2.py
    │   ├── verificar_fuentes_importadas.py
    │   ├── verificar_html_grafico.py
    │   ├── verificar_importacion.py
    │   ├── verificar_importacion_final.py
    │   ├── verificar_propiedades_acm.py
    │   ├── verificar_script_elements.py
    │   ├── verificar_solucion_propifai.py
    │   ├── verificar_todos_campos_admin.py
    │   ├── verificar_vista_grafico.py
    │   ├── views.py
    │   └── wsgi.py
    ├── ')
    ├── .deployment
    ├── .gitignore
    ├── AZURE_DEPLOYMENT_FIX.md
    ├── CHECKPOINT_FACEBOOK_SOLUCION.md
    ├── DEPLOY_INSTRUCTIONS.md
    ├── FASE0_ANALISIS_RESUMEN.md
    ├── FASE1_IMPLEMENTACION.md
    ├── MARKET_ANALYSIS_IMPLEMENTACION.md
    ├── README.md
    ├── RESUMEN_MARKET_ANALYSIS.md
    ├── SOLUCION_PROPIEDADES_PROPIFY.md
    ├── SOLUCION_TOKEN_META_VENCIDO.md
    ├── acceso_directo.py
    ├── analizar_fechas_reales.py
    ├── analizar_fechas_sql.py
    ├── analizar_html_real.py
    ├── analizar_html_simple.py
    ├── analizar_requerimientos_sin_match.py
    ├── analyze_template.py
    ├── application.py
    ├── borrar_propiedades_raw.py
    ├── borrar_propiedades_raw_auto.py
    ├── borrar_propiedadesraw.py
    ├── campos_propiedadraw_simple.py
    ├── campos_propiedadraw_tabla.txt
    ├── check_api.py
    ├── check_api_detail.py
    ├── check_blocks.py
    ├── check_css.py
    ├── check_css_simple.py
    ├── check_dashboard_html.py
    ├── check_data.py
    ├── check_heatmap_html.py
    ├── check_heatmap_live.py
    ├── check_heatmap_properties.py
    ├── check_html.py
    ├── check_html_balance.py
    ├── check_matplotlib.py
    ├── check_model_fields.py
    ├── check_property_type_field.py
    ├── check_property_type_field_v2.py
    ├── check_property_type_orm.py
    ├── check_propiedadraw_fields.py
    ├── check_propifai_fields.py
    ├── check_scripts.py
    ├── check_server_version.py
    ├── check_tables_structure.py
    ├── check_template_error.py
    ├── check_terrenos.py
    ├── cleanup_chart.py
    ├── convert_svg_to_png.py
    ├── convert_svg_to_png_cairo.py
    ├── count_blocks.py
    ├── create_png_data_url.py
    ├── create_svg_data_url.py
    ├── debug_checkboxes.py
    ├── debug_colores.py
    ├── debug_detallado.py
    ├── debug_propifai_terrenos.py
    ├── debug_propify_issue.py
    ├── debug_simple.py
    ├── diagnostic_error.py
    ├── diagnostic_error2.py
    ├── diagnostic_propifai.py
    ├── diagnosticar_api.py
    ├── diagnosticar_dias.py
    ├── diagnosticar_formato_dias.py
    ├── diagnostico_barras_duplicadas.py
    ├── diagnostico_contexto_real.py
    ├── diagnostico_dashboard_completo.py
    ├── diagnostico_fechas_grafica.py
    ├── diagnostico_final.py
    ├── diagnostico_propifai.py
    ├── diagnostico_rapido.py
    ├── diagnostico_simple.py
    ├── error_full.html
    ├── estructura_proyecto.md
    ├── estructura_tabla_remax.md
    ├── eventos.html
    ├── eventos_corregido.html
    ├── explore_district_table.py
    ├── fetch_debug.py
    ├── filtered_page2.html
    ├── find_exact_table.py
    ├── fix_chart_height.py
    ├── fix_chart_height2.py
    ├── fix_template.py
    ├── fix_template_simple.py
    ├── generar_arbol.py
    ├── generar_excel_campos.py
    ├── generate_data_url.py
    ├── get_propifai_coords.py
    ├── get_real_data.py
    ├── heatmap_debug.html
    ├── html_fragmento.txt
    ├── importar_propiedades_raw.py
    ├── importar_propiedadesraw.py
    ├── importar_propiedadesraw_auto.py
    ├── importar_simple.py
    ├── inspeccionar_datos_grafica.py
    ├── inspeccionar_datos_simple.py
    ├── inspeccionar_excel.py
    ├── investigar_offset.py
    ├── listar_campos_propiedadraw.py
    ├── masivo_output.html
    ├── oryx-manifest.toml
    ├── page.html
    ├── page2.html
    ├── page3.html
    ├── page4.html
    ├── pin_propify_data_url.txt
    ├── png_data_url.txt
    ├── propiedades_propify.html
    ├── requirements.txt
    ├── response.txt
    ├── runtime.txt
    ├── screenshot_current.png
    ├── screenshot_current_colors.png
    ├── screenshot_green_test.png
    ├── screenshot_teal_design.png
    ├── server.log
    ├── sidebar_visible.png
    ├── simular_fecha_frontend.py
    ├── startup.sh
    ├── svg_data_url.txt
    ├── temp.html
    ├── temp2.html
    ├── test_acm.py
    ├── test_agentes.py
    ├── test_agentes_eventos.py
    ├── test_api_dashboard.py
    ├── test_charts.py
    ├── test_checkbox_logic.py
    ├── test_columnas.py
    ├── test_completo_terrenos.py
    ├── test_conexion_propifai.py
    ├── test_conteo_props.py
    ├── test_contexto_simple.py
    ├── test_conversion.py
    ├── test_correccion_dias.py
    ├── test_correccion_grafica.py
    ├── test_correccion_terrenos.py
    ├── test_correcciones_final.py
    ├── test_crm_mejora.py
    ├── test_dashboard_agentes.py
    ├── test_dashboard_data.py
    ├── test_dashboard_district.py
    ├── test_dashboard_district_simple.py
    ├── test_dashboard_final.py
    ├── test_depuracion.py
    ├── test_depuracion_simple.py
    ├── test_despues_cambio.py
    ├── test_dias_corregidos.py
    ├── test_directo_simple.py
    ├── test_duplicacion_tipos.py
    ├── test_edit_functionality.py
    ├── test_fecha_creacion.py
    ├── test_fechas_api.py
    ├── test_fechas_final.py
    ├── test_fechas_peru.py
    ├── test_filtro_usuario.py
    ├── test_filtros_checkbox.py
    ├── test_final.ps1
    ├── test_final.py
    ├── test_final_completo.py
    ├── test_final_correccion.py
    ├── test_final_dashboard.py
    ├── test_final_grafico.py
    ├── test_final_heatmap.py
    ├── test_final_matching.py
    ├── test_final_simple.py
    ├── test_final_terrenos.py
    ├── test_frontend_logic.py
    ├── test_funcion_real.py
    ├── test_google_maps_key.py
    ├── test_google_maps_key_simple.py
    ├── test_grafico_eventos.py
    ├── test_grafico_final.py
    ├── test_grafico_final_simple.py
    ├── test_grafico_simple.py
    ├── test_heatmap_api.py
    ├── test_heatmap_coordinates.py
    ├── test_heatmap_html.py
    ├── test_heatmap_page.py
    ├── test_heatmap_page_simple.py
    ├── test_heatmap_ps.ps1
    ├── test_heatmap_real.py
    ├── test_heatmap_view.py
    ├── test_http.py
    ├── test_http_acm.py
    ├── test_http_acm_arequipa.py
    ├── test_http_checkboxes.py
    ├── test_http_filtros.py
    ├── test_import.py
    ├── test_intercalado_simple.py
    ├── test_js_loaded.py
    ├── test_js_parse.html
    ├── test_lead_status.py
    ├── test_leyenda_interactiva.py
    ├── test_logica_mejorada.py
    ├── test_logs.py
    ├── test_markers.ps1
    ├── test_market_analysis_heatmap.py
    ├── test_matching_debug.py
    ├── test_matching_final.py
    ├── test_matching_final_v2.py
    ├── test_matching_resumen.py
    ├── test_matriz_agente_semana.py
    ├── test_meta_api.py
    ├── test_page.html
    ├── test_pagina_web.py
    ├── test_paginacion.py
    ├── test_paginacion_propify.py
    ├── test_performance.ps1
    ├── test_performance_simple.ps1
    ├── test_png_access.html
    ├── test_precio_m2_propifai.py
    ├── test_problematic_examples.py
    ├── test_propifai_db.py
    ├── test_propifai_directo.py
    ├── test_propify_directo.py
    ├── test_propify_directo_final.py
    ├── test_propify_filtros.py
    ├── test_rapido_propify.py
    ├── test_real_data.py
    ├── test_simple.ps1
    ├── test_simple.py
    ├── test_simple_leyenda.py
    ├── test_simulacion_vista.py
    ├── test_sorting.py
    ├── test_status_counts.py
    ├── test_status_simple.py
    ├── test_timeline_fix.py
    ├── test_timeline_simple.py
    ├── test_tipo_propiedad_dashboard.py
    ├── test_tipo_propiedad_dashboard_v2.py
    ├── test_tipo_propiedad_dashboard_v3.py
    ├── test_url_final.py
    ├── test_url_propify.py
    ├── test_verificar_conteos.py
    ├── test_vista.py
    ├── test_vista_completa.py
    ├── test_vista_directa.py
    ├── test_vista_directo.py
    ├── test_vista_final.py
    ├── test_vista_masivo.py
    ├── test_vista_optimizada.py
    ├── test_vista_propiedades.py
    ├── test_vista_propify.py
    ├── test_web_page.py
    ├── verificacion_final_imagenes.py
    ├── verificacion_final_servidor.py
    ├── verificacion_final_simple.py
    ├── verificacion_simple.py
    ├── verificar_campo_es_propify.py
    ├── verificar_campo_identificador_externo.py
    ├── verificar_coincidencia_datos.py
    ├── verificar_colores_eventos.py
    ├── verificar_contexto_directo.py
    ├── verificar_correcciones_final.py
    ├── verificar_datos.py
    ├── verificar_datos_eventos.py
    ├── verificar_duplicacion_datos.py
    ├── verificar_duplicacion_lista.py
    ├── verificar_html_directo.py
    ├── verificar_html_final.py
    ├── verificar_html_propify.py
    ├── verificar_html_real.py
    ├── verificar_html_simple_win.py
    ├── verificar_implementacion.py
    ├── verificar_importacion.py
    ├── verificar_problema_usuario.py
    ├── verificar_propiedades_heatmap.py
    ├── verificar_propify_directo.py
    ├── verificar_rapido.py
    ├── verificar_servidor_real.py
    ├── verificar_simple.py
    ├── verificar_template_propify.py
    ├── verificar_vista_completa.py
    └── verify_heatmap.py
```
