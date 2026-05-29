const VIEW_MODE = 'week';
const CURRENT_YEAR = 2026;
const CURRENT_MONTH = 5;
const CURRENT_DAY = 18;
const TODAY = '2026-05-29';




// ===== WEEK VIEW: Render from JSON =====
const diasSemana = [{"date_iso": "2026-05-18", "date_display": "18", "day_name": "Mon", "is_today": false, "requerimientos": [{"id": 20223, "hora": "08:41:00", "hora_display": "08:41", "tipo_propiedad": "OFICINA", "tipo_propiedad_key": "oficina", "presupuesto_display": "", "presupuesto_monto": null, "presupuesto_moneda": "USD", "agente": "Ximena Heredia", "distritos": "Cerro Colorado", "distritos_list": ["Cerro Colorado"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": true}, {"id": 20217, "hora": "08:41:00", "hora_display": "08:41", "tipo_propiedad": "CASA", "tipo_propiedad_key": "casa", "presupuesto_display": "$300,000", "presupuesto_monto": 300000.0, "presupuesto_moneda": "USD", "agente": "Ximena Heredia", "distritos": "Cayma Cerro Colorado", "distritos_list": ["Cayma Cerro Colorado"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": true}, {"id": 20221, "hora": "09:19:00", "hora_display": "09:19", "tipo_propiedad": "NO ESPECIFICADO", "tipo_propiedad_key": "no_especificado", "presupuesto_display": "", "presupuesto_monto": null, "presupuesto_moneda": "no_especificado", "agente": "andreita", "distritos": "Cayma", "distritos_list": ["Cayma"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": true}, {"id": 20226, "hora": "09:33:00", "hora_display": "09:33", "tipo_propiedad": "CASA", "tipo_propiedad_key": "casa", "presupuesto_display": "$250,000", "presupuesto_monto": 250000.0, "presupuesto_moneda": "USD", "agente": "Belen Aguilar Ar\u00e9valo", "distritos": "Jose Luis Bustamante y Rivero, Cercado", "distritos_list": ["Jose Luis Bustamante y Rivero", "Cercado"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20227, "hora": "09:37:00", "hora_display": "09:37", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$180,000", "presupuesto_monto": 180000.0, "presupuesto_moneda": "USD", "agente": "Melanie Delgado", "distritos": "Piedra Santa, Chullo, Tahuaycani", "distritos_list": ["Piedra Santa", "Chullo", "Tahuaycani"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20228, "hora": "09:50:00", "hora_display": "09:50", "tipo_propiedad": "CASA", "tipo_propiedad_key": "casa", "presupuesto_display": "$210,000", "presupuesto_monto": 210000.0, "presupuesto_moneda": "USD", "agente": "Melanie Delgado", "distritos": "Jos\u00e9 Luis Bustamante y Rivero", "distritos_list": ["Jos\u00e9 Luis Bustamante y Rivero"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20229, "hora": "10:28:00", "hora_display": "10:28", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$105,000", "presupuesto_monto": 105000.0, "presupuesto_moneda": "USD", "agente": "Propify Valery Gonzales", "distritos": "Cerro Colorado, Sachaca", "distritos_list": ["Cerro Colorado", "Sachaca"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20230, "hora": "11:14:00", "hora_display": "11:14", "tipo_propiedad": "CASA", "tipo_propiedad_key": "casa", "presupuesto_display": "", "presupuesto_monto": null, "presupuesto_moneda": "no_especificado", "agente": "Juan Carlos Lezama Rivera", "distritos": "Yanahuara, Umacollo, Sachaca, Cayma", "distritos_list": ["Yanahuara", "Umacollo", "Sachaca", "Cayma"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20231, "hora": "11:20:00", "hora_display": "11:20", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$85,000", "presupuesto_monto": 85000.0, "presupuesto_moneda": "USD", "agente": "+51 952 540 717", "distritos": "", "distritos_list": [], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20457, "hora": "11:22:11", "hora_display": "11:22", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$105,000", "presupuesto_monto": 105000.0, "presupuesto_moneda": "USD", "agente": "Ximena Garc\u00eda Agente Inmobiliario", "distritos": "", "distritos_list": [], "porcentaje_match": 71.0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20373, "hora": "11:36:43", "hora_display": "11:36", "tipo_propiedad": "CASA", "tipo_propiedad_key": "casa", "presupuesto_display": "$240,000", "presupuesto_monto": 240000.0, "presupuesto_moneda": "USD", "agente": "Oswaldo Eguia Agente Inmobiliario", "distritos": "Jos\u00e9 Luis Bustamante", "distritos_list": ["Jos\u00e9 Luis Bustamante"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20233, "hora": "12:17:00", "hora_display": "12:17", "tipo_propiedad": "CASA", "tipo_propiedad_key": "casa", "presupuesto_display": "$200,000", "presupuesto_monto": 200000.0, "presupuesto_moneda": "USD", "agente": "Smart House Gestion Inmobiliaria", "distritos": "Cayma, Cerro Colorado", "distritos_list": ["Cayma", "Cerro Colorado"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20374, "hora": "12:27:17", "hora_display": "12:27", "tipo_propiedad": "CASA", "tipo_propiedad_key": "casa", "presupuesto_display": "$158,000", "presupuesto_monto": 158000.0, "presupuesto_moneda": "USD", "agente": "~\u202fMonica", "distritos": "Cerro Colorado", "distritos_list": ["Cerro Colorado"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20234, "hora": "12:29:00", "hora_display": "12:29", "tipo_propiedad": "LOCAL COMERCIAL", "tipo_propiedad_key": "local_comercial", "presupuesto_display": "S/1,500", "presupuesto_monto": 1500.0, "presupuesto_moneda": "PEN", "agente": "Marita Quispe", "distritos": "Cercado de Arequipa", "distritos_list": ["Cercado de Arequipa"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20235, "hora": "13:16:00", "hora_display": "13:16", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "S/350,000", "presupuesto_monto": 350000.0, "presupuesto_moneda": "PEN", "agente": "Marco Hidalgo Cabana", "distritos": "Jos\u00e9 Luis Bustamante y Rivero", "distritos_list": ["Jos\u00e9 Luis Bustamante y Rivero"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20236, "hora": "13:40:00", "hora_display": "13:40", "tipo_propiedad": "NO ESPECIFICADO", "tipo_propiedad_key": "no_especificado", "presupuesto_display": "", "presupuesto_monto": null, "presupuesto_moneda": "no_especificado", "agente": "Belen Aguilar Ar\u00e9valo", "distritos": "Jos\u00e9 Luis Bustamante y Rivero", "distritos_list": ["Jos\u00e9 Luis Bustamante y Rivero"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20237, "hora": "14:10:00", "hora_display": "14:10", "tipo_propiedad": "CASA", "tipo_propiedad_key": "casa", "presupuesto_display": "$400,000", "presupuesto_monto": 400000.0, "presupuesto_moneda": "USD", "agente": "+51 918 090 769", "distritos": "Cayma, Vallecito, Cerro Colorado, Yanahuara, Sacha", "distritos_list": ["Cayma", "Vallecito", "Cerro Colorado", "Yanahuara", "Sachaca", "JLBR"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20239, "hora": "14:13:00", "hora_display": "14:13", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$200,000", "presupuesto_monto": 200000.0, "presupuesto_moneda": "USD", "agente": "+51 987 326 992", "distritos": "Jos\u00e9 Luis Bustamante y Rivero", "distritos_list": ["Jos\u00e9 Luis Bustamante y Rivero"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20375, "hora": "14:52:23", "hora_display": "14:52", "tipo_propiedad": "TERRENO", "tipo_propiedad_key": "terreno", "presupuesto_display": "", "presupuesto_monto": null, "presupuesto_moneda": "no_especificado", "agente": "Verito Olmos Agente Inmobiario", "distritos": "Cerro Colorado, Vallecito, Yanahuara", "distritos_list": ["Cerro Colorado", "Vallecito", "Yanahuara"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20377, "hora": "15:17:58", "hora_display": "15:17", "tipo_propiedad": "CASA", "tipo_propiedad_key": "casa", "presupuesto_display": "S/5,000", "presupuesto_monto": 5000.0, "presupuesto_moneda": "PEN", "agente": "Lucia Arredondo Agente", "distritos": "Cerro Colorado, Mariano Melgar, Jos\u00e9 Luis Bustaman", "distritos_list": ["Cerro Colorado", "Mariano Melgar", "Jos\u00e9 Luis Bustamante y Rivero"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20240, "hora": "15:51:00", "hora_display": "15:51", "tipo_propiedad": "CASA", "tipo_propiedad_key": "casa", "presupuesto_display": "$300,000", "presupuesto_monto": 300000.0, "presupuesto_moneda": "USD", "agente": "Marco Hidalgo Cabana", "distritos": "Yanahuara, Cayma Baja", "distritos_list": ["Yanahuara", "Cayma Baja"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20241, "hora": "16:57:00", "hora_display": "16:57", "tipo_propiedad": "CASA", "tipo_propiedad_key": "casa", "presupuesto_display": "S/3,000", "presupuesto_monto": 3000.0, "presupuesto_moneda": "PEN", "agente": "Omar Valdivia", "distritos": "Miraflores, Mariano Melgar, Alto Selva Alegre", "distritos_list": ["Miraflores", "Mariano Melgar", "Alto Selva Alegre"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20459, "hora": "18:30:58", "hora_display": "18:30", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "S/1,500", "presupuesto_monto": 1500.0, "presupuesto_moneda": "PEN", "agente": "~\u202fsonia310779", "distritos": "Cayma", "distritos_list": ["Cayma"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20245, "hora": "20:14:00", "hora_display": "20:14", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$150,000", "presupuesto_monto": 150000.0, "presupuesto_moneda": "USD", "agente": "Cecilia", "distritos": "Cayma, Yanahuara, Cerro Colorado", "distritos_list": ["Cayma", "Yanahuara", "Cerro Colorado"], "porcentaje_match": 75.0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20246, "hora": "23:15:00", "hora_display": "23:15", "tipo_propiedad": "LOCAL COMERCIAL", "tipo_propiedad_key": "local_comercial", "presupuesto_display": "", "presupuesto_monto": null, "presupuesto_moneda": "no_especificado", "agente": "Tomas Fernandez", "distritos": "no_especificado", "distritos_list": ["no_especificado"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}], "total": 25, "con_match_alto": 0}, {"date_iso": "2026-05-19", "date_display": "19", "day_name": "Tue", "is_today": false, "requerimientos": [{"id": 20382, "hora": "07:07:53", "hora_display": "07:07", "tipo_propiedad": "LOCAL COMERCIAL", "tipo_propiedad_key": "local_comercial", "presupuesto_display": "", "presupuesto_monto": null, "presupuesto_moneda": "no_especificado", "agente": "Tommy KW", "distritos": "no_especificado", "distritos_list": ["no_especificado"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20247, "hora": "07:59:00", "hora_display": "07:59", "tipo_propiedad": "CASA", "tipo_propiedad_key": "casa", "presupuesto_display": "$500,000", "presupuesto_monto": 500000.0, "presupuesto_moneda": "USD", "agente": "D\u00e1rely Paredes", "distritos": "asa", "distritos_list": ["asa"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20248, "hora": "08:00:00", "hora_display": "08:00", "tipo_propiedad": "CASA", "tipo_propiedad_key": "casa", "presupuesto_display": "$500,000", "presupuesto_monto": 500000.0, "presupuesto_moneda": "USD", "agente": "D\u00e1rely Paredes", "distritos": "", "distritos_list": [], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20249, "hora": "08:00:00", "hora_display": "08:00", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$115,000", "presupuesto_monto": 115000.0, "presupuesto_moneda": "USD", "agente": "Ysrael Rivas", "distritos": "Jos\u00e9 Luis Bustamante y Rivero", "distritos_list": ["Jos\u00e9 Luis Bustamante y Rivero"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20250, "hora": "08:01:00", "hora_display": "08:01", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$120,000", "presupuesto_monto": 120000.0, "presupuesto_moneda": "USD", "agente": "D\u00e1rely Paredes", "distritos": "Cayma, Yanahuara", "distritos_list": ["Cayma", "Yanahuara"], "porcentaje_match": 71.0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20383, "hora": "08:49:04", "hora_display": "08:49", "tipo_propiedad": "TERRENO", "tipo_propiedad_key": "terreno", "presupuesto_display": "", "presupuesto_monto": null, "presupuesto_moneda": "no_especificado", "agente": "Dayana Arista Agente", "distritos": "Sachaca", "distritos_list": ["Sachaca"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20384, "hora": "09:50:23", "hora_display": "09:50", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$170,000", "presupuesto_monto": 170000.0, "presupuesto_moneda": "USD", "agente": "Deisy Marroquin Agente Inmobiliario", "distritos": "Cayma, Yanahuara", "distritos_list": ["Cayma", "Yanahuara"], "porcentaje_match": 77.0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20461, "hora": "11:46:33", "hora_display": "11:46", "tipo_propiedad": "CASA", "tipo_propiedad_key": "casa", "presupuesto_display": "$210,000", "presupuesto_monto": 210000.0, "presupuesto_moneda": "USD", "agente": "~\u202fGZSANTAMARIA", "distritos": "Miraflores", "distritos_list": ["Miraflores"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20385, "hora": "11:46:55", "hora_display": "11:46", "tipo_propiedad": "CASA", "tipo_propiedad_key": "casa", "presupuesto_display": "$210,000", "presupuesto_monto": 210000.0, "presupuesto_moneda": "USD", "agente": "~\u202fGZSANTAMARIA", "distritos": "Miraflores", "distritos_list": ["Miraflores"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20386, "hora": "12:18:53", "hora_display": "12:18", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "S/3,500", "presupuesto_monto": 3500.0, "presupuesto_moneda": "PEN", "agente": "~\u202fClaudia Bejar", "distritos": "Jos\u00e9 Luis Bustamante y Rivero", "distritos_list": ["Jos\u00e9 Luis Bustamante y Rivero"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20398, "hora": "12:57:00", "hora_display": "12:57", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "", "presupuesto_monto": null, "presupuesto_moneda": "no_especificado", "agente": "Rosa Angela Raa", "distritos": "Mirasol", "distritos_list": ["Mirasol"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20399, "hora": "12:57:00", "hora_display": "12:57", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "S/1,500", "presupuesto_monto": 1500.0, "presupuesto_moneda": "PEN", "agente": "Rosa Angela Raa", "distritos": "Cayma", "distritos_list": ["Cayma"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20254, "hora": "12:57:00", "hora_display": "12:57", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "S/1,500", "presupuesto_monto": 1500.0, "presupuesto_moneda": "PEN", "agente": "Rosa Angela Raa", "distritos": "Cayma", "distritos_list": ["Cayma"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": true}, {"id": 20255, "hora": "12:57:00", "hora_display": "12:57", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$150,000", "presupuesto_monto": 150000.0, "presupuesto_moneda": "USD", "agente": "Rosa Angela Raa", "distritos": "Cayma, Yanahuara", "distritos_list": ["Cayma", "Yanahuara"], "porcentaje_match": 86.5, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 24204, "hora": "12:57:00", "hora_display": "12:57", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "", "presupuesto_monto": null, "presupuesto_moneda": "no_especificado", "agente": "Rosa Angela Raa", "distritos": "Mirasol", "distritos_list": ["Mirasol"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 24206, "hora": "12:57:00", "hora_display": "12:57", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "S/1,500", "presupuesto_monto": 1500.0, "presupuesto_moneda": "PEN", "agente": "Rosa Angela Raa", "distritos": "Cayma", "distritos_list": ["Cayma"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20388, "hora": "17:37:50", "hora_display": "17:37", "tipo_propiedad": "CASA", "tipo_propiedad_key": "casa", "presupuesto_display": "$500,000", "presupuesto_monto": 500000.0, "presupuesto_moneda": "USD", "agente": "~\u202fGiovana", "distritos": "Sachaca, Cayma, Yanahuara, Cerro Colorado", "distritos_list": ["Sachaca", "Cayma", "Yanahuara", "Cerro Colorado"], "porcentaje_match": 76.0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20260, "hora": "17:40:00", "hora_display": "17:40", "tipo_propiedad": "CASA", "tipo_propiedad_key": "casa", "presupuesto_display": "$350,000", "presupuesto_monto": 350000.0, "presupuesto_moneda": "USD", "agente": "Erika Palacios", "distritos": "Cayma, Yanahuara", "distritos_list": ["Cayma", "Yanahuara"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": true}, {"id": 20261, "hora": "18:00:00", "hora_display": "18:00", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$120,000", "presupuesto_monto": 120000.0, "presupuesto_moneda": "USD", "agente": "Vanessa Pinto Miranda", "distritos": "Cayma, Yanahuara, Cerro Colorado", "distritos_list": ["Cayma", "Yanahuara", "Cerro Colorado"], "porcentaje_match": 75.5, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": true}, {"id": 20463, "hora": "18:39:42", "hora_display": "18:39", "tipo_propiedad": "CASA", "tipo_propiedad_key": "casa", "presupuesto_display": "$300,000", "presupuesto_monto": 300000.0, "presupuesto_moneda": "USD", "agente": "~\u202fAngela De La Cuba", "distritos": "no_especificado", "distritos_list": ["no_especificado"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20390, "hora": "18:59:52", "hora_display": "18:59", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "", "presupuesto_monto": null, "presupuesto_moneda": "no_especificado", "agente": "~\u202fGiuliana Perochena", "distritos": "Cayma, Yanahuara", "distritos_list": ["Cayma", "Yanahuara"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20262, "hora": "19:24:00", "hora_display": "19:24", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$120,000", "presupuesto_monto": 120000.0, "presupuesto_moneda": "USD", "agente": "+51 952 540 717", "distritos": "", "distritos_list": [], "porcentaje_match": 71.0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": true}, {"id": 20391, "hora": "19:24:47", "hora_display": "19:24", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$120,000", "presupuesto_monto": 120000.0, "presupuesto_moneda": "USD", "agente": "Mildreth Delgado Agente", "distritos": "", "distritos_list": [], "porcentaje_match": 71.0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}], "total": 23, "con_match_alto": 0}, {"date_iso": "2026-05-20", "date_display": "20", "day_name": "Wed", "is_today": false, "requerimientos": [{"id": 20264, "hora": "07:56:00", "hora_display": "07:56", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$150,000", "presupuesto_monto": 150000.0, "presupuesto_moneda": "USD", "agente": "Rossiela Gomez", "distritos": "Cayma", "distritos_list": ["Cayma"], "porcentaje_match": 88.5, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 24212, "hora": "07:56:00", "hora_display": "07:56", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$150,000", "presupuesto_monto": 150000.0, "presupuesto_moneda": "USD", "agente": "Jessica Casta\u00f1eda", "distritos": "Cayma", "distritos_list": ["Cayma"], "porcentaje_match": 86.5, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20266, "hora": "10:03:00", "hora_display": "10:03", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$120,000", "presupuesto_monto": 120000.0, "presupuesto_moneda": "USD", "agente": "Darely Paredes", "distritos": "JBYR, Cayma, Yanahuara", "distritos_list": ["JBYR", "Cayma", "Yanahuara"], "porcentaje_match": 73.0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20267, "hora": "11:05:00", "hora_display": "11:05", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$150,000", "presupuesto_monto": 150000.0, "presupuesto_moneda": "USD", "agente": "Rodrigo Prieto Torres", "distritos": "Jos\u00e9 Luis Bustamante y Rivero", "distritos_list": ["Jos\u00e9 Luis Bustamante y Rivero"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20268, "hora": "11:19:00", "hora_display": "11:19", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$180,000", "presupuesto_monto": 180000.0, "presupuesto_moneda": "USD", "agente": "Darely Paredes", "distritos": "Cayma, Yanahuara, Umacollo", "distritos_list": ["Cayma", "Yanahuara", "Umacollo"], "porcentaje_match": 72.0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20394, "hora": "11:49:54", "hora_display": "11:49", "tipo_propiedad": "CASA", "tipo_propiedad_key": "casa", "presupuesto_display": "$200,000", "presupuesto_monto": 200000.0, "presupuesto_moneda": "USD", "agente": "Fiorella Diaz Agente", "distritos": "Jose Luis Bustamante y Rivero, Cercado, Mariano Me", "distritos_list": ["Jose Luis Bustamante y Rivero", "Cercado", "Mariano Melgar", "Paucarpata"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20269, "hora": "12:15:00", "hora_display": "12:15", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "S/1,700", "presupuesto_monto": 1700.0, "presupuesto_moneda": "PEN", "agente": "Marco Hidalgo Cabana", "distritos": "Yanahuara", "distritos_list": ["Yanahuara"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20464, "hora": "12:17:54", "hora_display": "12:17", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$150,000", "presupuesto_monto": 150000.0, "presupuesto_moneda": "USD", "agente": "~\u202fEsperanza Damiani", "distritos": "Cayma, Yanahuara, Umacollo, Sachaca", "distritos_list": ["Cayma", "Yanahuara", "Umacollo", "Sachaca"], "porcentaje_match": 81.0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20406, "hora": "12:49:00", "hora_display": "12:49", "tipo_propiedad": "CASA", "tipo_propiedad_key": "casa", "presupuesto_display": "$140,000", "presupuesto_monto": 140000.0, "presupuesto_moneda": "USD", "agente": "Marilyn Benavente Z.", "distritos": "Alto Selva Alegre, Miraflores, Mariano Melgar, Pau", "distritos_list": ["Alto Selva Alegre", "Miraflores", "Mariano Melgar", "Paucarpata"], "porcentaje_match": 73.67, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20270, "hora": "12:49:00", "hora_display": "12:49", "tipo_propiedad": "CASA", "tipo_propiedad_key": "casa", "presupuesto_display": "$140,000", "presupuesto_monto": 140000.0, "presupuesto_moneda": "USD", "agente": "Marilyn Benavente Z.", "distritos": "Alto Selva Alegre, Miraflores, Mariano Melgar, Pau", "distritos_list": ["Alto Selva Alegre", "Miraflores", "Mariano Melgar", "Paucarpata"], "porcentaje_match": 73.67, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": true}, {"id": 24214, "hora": "12:49:00", "hora_display": "12:49", "tipo_propiedad": "CASA", "tipo_propiedad_key": "casa", "presupuesto_display": "$140,000", "presupuesto_monto": 140000.0, "presupuesto_moneda": "USD", "agente": "Marilyn Benavente Z.", "distritos": "Alto Selva Alegre, Miraflores, Mariano Melgar, Pau", "distritos_list": ["Alto Selva Alegre", "Miraflores", "Mariano Melgar", "Paucarpata"], "porcentaje_match": 73.67, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 24215, "hora": "13:07:00", "hora_display": "13:07", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$175,000", "presupuesto_monto": 175000.0, "presupuesto_moneda": "USD", "agente": "Yin Nataly", "distritos": "Yanahuara", "distritos_list": ["Yanahuara"], "porcentaje_match": 82.0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20271, "hora": "13:07:00", "hora_display": "13:07", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$175,000", "presupuesto_monto": 175000.0, "presupuesto_moneda": "USD", "agente": "Yin Nataly", "distritos": "Yanahuara", "distritos_list": ["Yanahuara"], "porcentaje_match": 82.0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20408, "hora": "16:09:00", "hora_display": "16:09", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$100,000", "presupuesto_monto": 100000.0, "presupuesto_moneda": "USD", "agente": "Martha Morales", "distritos": "Umacollo", "distritos_list": ["Umacollo"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20409, "hora": "16:33:00", "hora_display": "16:33", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "S/1,500", "presupuesto_monto": 1500.0, "presupuesto_moneda": "PEN", "agente": "Zarela Garc\u00eda", "distritos": "Jos\u00e9 Luis Bustamante y Rivero, Guardia Civil", "distritos_list": ["Jos\u00e9 Luis Bustamante y Rivero", "Guardia Civil"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 24216, "hora": "16:33:00", "hora_display": "16:33", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "S/1,500", "presupuesto_monto": 1500.0, "presupuesto_moneda": "PEN", "agente": "Zarela Garc\u00eda", "distritos": "Jos\u00e9 Luis Bustamante y Rivero", "distritos_list": ["Jos\u00e9 Luis Bustamante y Rivero"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20410, "hora": "17:36:00", "hora_display": "17:36", "tipo_propiedad": "CASA", "tipo_propiedad_key": "casa", "presupuesto_display": "$250,000", "presupuesto_monto": 250000.0, "presupuesto_moneda": "USD", "agente": "Propify Valery Gonzales", "distritos": "Cayma", "distritos_list": ["Cayma"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20411, "hora": "18:13:00", "hora_display": "18:13", "tipo_propiedad": "NO ESPECIFICADO", "tipo_propiedad_key": "no_especificado", "presupuesto_display": "$400,000", "presupuesto_monto": 400000.0, "presupuesto_moneda": "USD", "agente": "Belen Aguilar Ar\u00e9valo", "distritos": "", "distritos_list": [], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20412, "hora": "18:16:00", "hora_display": "18:16", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$170,000", "presupuesto_monto": 170000.0, "presupuesto_moneda": "USD", "agente": "Belen Aguilar Ar\u00e9valo", "distritos": "Yanahuara, Cayma, Sachaca", "distritos_list": ["Yanahuara", "Cayma", "Sachaca"], "porcentaje_match": 79.5, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20413, "hora": "18:17:00", "hora_display": "18:17", "tipo_propiedad": "CASA", "tipo_propiedad_key": "casa", "presupuesto_display": "$200,000", "presupuesto_monto": 200000.0, "presupuesto_moneda": "USD", "agente": "Belen Aguilar Ar\u00e9valo", "distritos": "no_especificado", "distritos_list": ["no_especificado"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20414, "hora": "18:17:00", "hora_display": "18:17", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$120,000", "presupuesto_monto": 120000.0, "presupuesto_moneda": "USD", "agente": "Belen Aguilar Ar\u00e9valo", "distritos": "Cerro Colorado, Yanahuara, Cayma", "distritos_list": ["Cerro Colorado", "Yanahuara", "Cayma"], "porcentaje_match": 78.5, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20415, "hora": "18:18:00", "hora_display": "18:18", "tipo_propiedad": "CASA", "tipo_propiedad_key": "casa", "presupuesto_display": "$250,000", "presupuesto_monto": 250000.0, "presupuesto_moneda": "USD", "agente": "Belen Aguilar Ar\u00e9valo", "distritos": "Sachaca, Yanahuara", "distritos_list": ["Sachaca", "Yanahuara"], "porcentaje_match": 72.0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20416, "hora": "18:19:00", "hora_display": "18:19", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$60,000", "presupuesto_monto": 60000.0, "presupuesto_moneda": "USD", "agente": "Belen Aguilar Ar\u00e9valo", "distritos": "Miraflores, Cerro Colorado, Mariano Melgar, Albora", "distritos_list": ["Miraflores", "Cerro Colorado", "Mariano Melgar", "Alborada"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": true}, {"id": 20418, "hora": "18:42:00", "hora_display": "18:42", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$150,000", "presupuesto_monto": 150000.0, "presupuesto_moneda": "USD", "agente": "Propify Valery Gonzales", "distritos": "Jos\u00e9 Luis Bustamante", "distritos_list": ["Jos\u00e9 Luis Bustamante"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20419, "hora": "18:42:00", "hora_display": "18:42", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "S/1,500", "presupuesto_monto": 1500.0, "presupuesto_moneda": "PEN", "agente": "Jessica Casta\u00f1eda", "distritos": "Cayma", "distritos_list": ["Cayma"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20420, "hora": "21:25:00", "hora_display": "21:25", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$120,000", "presupuesto_monto": 120000.0, "presupuesto_moneda": "USD", "agente": "Ximena Heredia", "distritos": "Cayma, Yanahuara", "distritos_list": ["Cayma", "Yanahuara"], "porcentaje_match": 77.0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": true}], "total": 26, "con_match_alto": 0}, {"date_iso": "2026-05-21", "date_display": "21", "day_name": "Thu", "is_today": false, "requerimientos": [{"id": 20421, "hora": "05:56:00", "hora_display": "05:56", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$150,000", "presupuesto_monto": 150000.0, "presupuesto_moneda": "USD", "agente": "Rosa Angela Raa", "distritos": "Cayma", "distritos_list": ["Cayma"], "porcentaje_match": 86.5, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20424, "hora": "07:52:00", "hora_display": "07:52", "tipo_propiedad": "CASA", "tipo_propiedad_key": "casa", "presupuesto_display": "$120,000", "presupuesto_monto": 120000.0, "presupuesto_moneda": "USD", "agente": "+51 959 178 084", "distritos": "", "distritos_list": [], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 20426, "hora": "08:25:00", "hora_display": "08:25", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$150,000", "presupuesto_monto": 150000.0, "presupuesto_moneda": "USD", "agente": "Jessica Casta\u00f1eda", "distritos": "Cayma", "distritos_list": ["Cayma"], "porcentaje_match": 88.5, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 24221, "hora": "11:15:00", "hora_display": "11:15", "tipo_propiedad": "NO ESPECIFICADO", "tipo_propiedad_key": "no_especificado", "presupuesto_display": "$300,000", "presupuesto_monto": 300000.0, "presupuesto_moneda": "USD", "agente": "Propify Valery Gonzales", "distritos": "Adepa", "distritos_list": ["Adepa"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 24222, "hora": "11:20:00", "hora_display": "11:20", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "", "presupuesto_monto": null, "presupuesto_moneda": "no_especificado", "agente": "Yin Nataly", "distritos": "Cerro Colorado", "distritos_list": ["Cerro Colorado"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 24223, "hora": "11:59:00", "hora_display": "11:59", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$165,000", "presupuesto_monto": 165000.0, "presupuesto_moneda": "USD", "agente": "Propify Valery Gonzales", "distritos": "Yanahuara, Cayma, Cerro Colorado, Sachaca", "distritos_list": ["Yanahuara", "Cayma", "Cerro Colorado", "Sachaca"], "porcentaje_match": 71.0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 24224, "hora": "12:17:00", "hora_display": "12:17", "tipo_propiedad": "CASA", "tipo_propiedad_key": "casa", "presupuesto_display": "$300,000", "presupuesto_monto": 300000.0, "presupuesto_moneda": "USD", "agente": "Marita Quispe", "distritos": "Cercado, Jos\u00e9 Luis Bustamante y Rivero", "distritos_list": ["Cercado", "Jos\u00e9 Luis Bustamante y Rivero"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 24225, "hora": "12:25:00", "hora_display": "12:25", "tipo_propiedad": "CASA", "tipo_propiedad_key": "casa", "presupuesto_display": "$210,000", "presupuesto_monto": 210000.0, "presupuesto_moneda": "USD", "agente": "Propify Valery Gonzales", "distritos": "Paucarpata", "distritos_list": ["Paucarpata"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 24226, "hora": "15:29:00", "hora_display": "15:29", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$160,000", "presupuesto_monto": 160000.0, "presupuesto_moneda": "USD", "agente": "Valeria Calder\u00f3n", "distritos": "Vallecito", "distritos_list": ["Vallecito"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 24227, "hora": "22:40:00", "hora_display": "22:40", "tipo_propiedad": "CASA", "tipo_propiedad_key": "casa", "presupuesto_display": "$50,000", "presupuesto_monto": 50000.0, "presupuesto_moneda": "USD", "agente": "+51 989 655 285", "distritos": "", "distritos_list": [], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}], "total": 10, "con_match_alto": 0}, {"date_iso": "2026-05-22", "date_display": "22", "day_name": "Fri", "is_today": false, "requerimientos": [{"id": 24228, "hora": "08:05:00", "hora_display": "08:05", "tipo_propiedad": "LOCAL COMERCIAL", "tipo_propiedad_key": "local_comercial", "presupuesto_display": "", "presupuesto_monto": null, "presupuesto_moneda": "no_especificado", "agente": "+51 959 178 084", "distritos": "", "distritos_list": [], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 24229, "hora": "10:17:00", "hora_display": "10:17", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$120,000", "presupuesto_monto": 120000.0, "presupuesto_moneda": "USD", "agente": "ilserozuzu", "distritos": "Miraflores, Mariano Melgar, Jos\u00e9 Luis Bustamante y", "distritos_list": ["Miraflores", "Mariano Melgar", "Jos\u00e9 Luis Bustamante y Rivero"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 24230, "hora": "10:26:00", "hora_display": "10:26", "tipo_propiedad": "CASA", "tipo_propiedad_key": "casa", "presupuesto_display": "S/500,000", "presupuesto_monto": 500000.0, "presupuesto_moneda": "PEN", "agente": "+51 993 804 905", "distritos": "Umacollo", "distritos_list": ["Umacollo"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 24232, "hora": "13:16:00", "hora_display": "13:16", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$160,000", "presupuesto_monto": 160000.0, "presupuesto_moneda": "USD", "agente": "+51 957 631 049", "distritos": "Cayma, Yanahuara, Tahuaycani", "distritos_list": ["Cayma", "Yanahuara", "Tahuaycani"], "porcentaje_match": 81.0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 24233, "hora": "14:57:00", "hora_display": "14:57", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$200,000", "presupuesto_monto": 200000.0, "presupuesto_moneda": "USD", "agente": "Kike Guevara Espinoza", "distritos": "Cayma, Yanahuara", "distritos_list": ["Cayma", "Yanahuara"], "porcentaje_match": 78.0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 24234, "hora": "15:33:00", "hora_display": "15:33", "tipo_propiedad": "TERRENO", "tipo_propiedad_key": "terreno", "presupuesto_display": "", "presupuesto_monto": null, "presupuesto_moneda": "PEN", "agente": "Karmen Cotacallapa", "distritos": "Jos\u00e9 Luis Bustamante y Rivero, Paucarpata", "distritos_list": ["Jos\u00e9 Luis Bustamante y Rivero", "Paucarpata"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}], "total": 6, "con_match_alto": 0}, {"date_iso": "2026-05-23", "date_display": "23", "day_name": "Sat", "is_today": false, "requerimientos": [{"id": 24235, "hora": "11:03:00", "hora_display": "11:03", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$200,000", "presupuesto_monto": 200000.0, "presupuesto_moneda": "USD", "agente": "+51 979 379 198", "distritos": "Cayma", "distritos_list": ["Cayma"], "porcentaje_match": 78.0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 24240, "hora": "12:11:00", "hora_display": "12:11", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "S/4,000", "presupuesto_monto": 4000.0, "presupuesto_moneda": "PEN", "agente": "+51 979 379 198", "distritos": "Cayma", "distritos_list": ["Cayma"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 24242, "hora": "14:08:00", "hora_display": "14:08", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$210,000", "presupuesto_monto": 210000.0, "presupuesto_moneda": "USD", "agente": "+51 981 108 430", "distritos": "Se\u00f1orial", "distritos_list": ["Se\u00f1orial"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 24248, "hora": "18:18:00", "hora_display": "18:18", "tipo_propiedad": "TERRENO", "tipo_propiedad_key": "terreno", "presupuesto_display": "", "presupuesto_monto": null, "presupuesto_moneda": "no_especificado", "agente": "Jessica Casta\u00f1eda", "distritos": "Cayma, Yanahuara, Jos\u00e9 Luis Bustamante y Rivero", "distritos_list": ["Cayma", "Yanahuara", "Jos\u00e9 Luis Bustamante y Rivero"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 24249, "hora": "18:47:00", "hora_display": "18:47", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "$160,000", "presupuesto_monto": 160000.0, "presupuesto_moneda": "USD", "agente": "D\u00e1rely Paredes", "distritos": "Jos\u00e9 Luis Bustamante y Rivero", "distritos_list": ["Jos\u00e9 Luis Bustamante y Rivero"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 24250, "hora": "19:39:00", "hora_display": "19:39", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "", "presupuesto_monto": null, "presupuesto_moneda": "no_especificado", "agente": "+51 957 631 049", "distritos": "Cayma, Yanahuara", "distritos_list": ["Cayma", "Yanahuara"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}], "total": 6, "con_match_alto": 0}, {"date_iso": "2026-05-24", "date_display": "24", "day_name": "Sun", "is_today": false, "requerimientos": [{"id": 24251, "hora": "00:57:00", "hora_display": "00:57", "tipo_propiedad": "CASA", "tipo_propiedad_key": "casa", "presupuesto_display": "$400,000", "presupuesto_monto": 400000.0, "presupuesto_moneda": "USD", "agente": "Mery Lu", "distritos": "Miraflores", "distritos_list": ["Miraflores"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 24252, "hora": "16:08:00", "hora_display": "16:08", "tipo_propiedad": "DEPARTAMENTO", "tipo_propiedad_key": "departamento", "presupuesto_display": "", "presupuesto_monto": null, "presupuesto_moneda": "no_especificado", "agente": "Yin Nataly", "distritos": "Cerro Colorado", "distritos_list": ["Cerro Colorado"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 24253, "hora": "16:18:00", "hora_display": "16:18", "tipo_propiedad": "CASA", "tipo_propiedad_key": "casa", "presupuesto_display": "", "presupuesto_monto": null, "presupuesto_moneda": "no_especificado", "agente": "+51 950 970 958", "distritos": "", "distritos_list": [], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 24254, "hora": "16:24:00", "hora_display": "16:24", "tipo_propiedad": "TERRENO", "tipo_propiedad_key": "terreno", "presupuesto_display": "$350", "presupuesto_monto": 350.0, "presupuesto_moneda": "USD", "agente": "+51 950 970 958", "distritos": "", "distritos_list": [], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 24255, "hora": "16:31:00", "hora_display": "16:31", "tipo_propiedad": "TERRENO", "tipo_propiedad_key": "terreno", "presupuesto_display": "$120", "presupuesto_monto": 120.0, "presupuesto_moneda": "USD", "agente": "+51 950 970 958", "distritos": "Matarani", "distritos_list": ["Matarani"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 24257, "hora": "17:10:00", "hora_display": "17:10", "tipo_propiedad": "TERRENO", "tipo_propiedad_key": "terreno", "presupuesto_display": "$330,000", "presupuesto_monto": 330000.0, "presupuesto_moneda": "USD", "agente": "+51 950 970 958", "distritos": "Cayma", "distritos_list": ["Cayma"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 24259, "hora": "23:16:00", "hora_display": "23:16", "tipo_propiedad": "TERRENO", "tipo_propiedad_key": "terreno", "presupuesto_display": "", "presupuesto_monto": null, "presupuesto_moneda": "no_especificado", "agente": "Mery Lu", "distritos": "Porongoche", "distritos_list": ["Porongoche"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}, {"id": 24260, "hora": "23:51:00", "hora_display": "23:51", "tipo_propiedad": "TERRENO", "tipo_propiedad_key": "terreno", "presupuesto_display": "$200,000", "presupuesto_monto": 200000.0, "presupuesto_moneda": "USD", "agente": "Mery Lu Community Tops", "distritos": "Jos\u00e9 Luis Bustamante y Rivero, Yanahuara, Sachaca,", "distritos_list": ["Jos\u00e9 Luis Bustamante y Rivero", "Yanahuara", "Sachaca", "Umacollo", "Cayma", "Hunter", "Miraflores", "Tiabaya"], "porcentaje_match": 0, "mejor_propiedad_codigo": null, "mejor_propiedad_precio": null, "mejor_propiedad_moneda_id": null, "verificado": false}], "total": 8, "con_match_alto": 0}];
const DAY_NAMES = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];

function getMatchBadgeClass(pct) {
    if (pct >= 90) return 'high';
    if (pct >= 50) return 'medium';
    if (pct > 0) return 'low';
    return 'none';
}

function getMatchBadgeText(pct) {
    if (pct >= 90) return Math.round(pct) + '%';
    if (pct >= 50) return Math.round(pct) + '%';
    if (pct > 0) return Math.round(pct) + '%';
    return '—';
}

document.addEventListener('DOMContentLoaded', function() {
    // Render header
    const header = document.getElementById('weekHeader');
    let headerHtml = '<div class="week-header-cell"></div>';
    diasSemana.forEach(function(dia) {
        const todayClass = dia.is_today ? 'today' : '';
        headerHtml += `<div class="week-header-cell ${todayClass}">
            <span class="day-name">${dia.day_name}</span>
            <span class="day-num">${dia.date_display}</span>
        </div>`;
    });
    header.innerHTML = headerHtml;

    // Render body - hours 7 to 22
    const body = document.getElementById('weekBody');
    let bodyHtml = '';
    for (let h = 7; h <= 22; h++) {
        const timeStr = String(h).padStart(2, '0') + ':00';
        bodyHtml += `<div class="week-hour-row">
            <div class="week-time-label">${timeStr}</div>`;
        diasSemana.forEach(function(dia) {
            const todayClass = dia.is_today ? 'today' : '';
            bodyHtml += `<div class="week-day-col ${todayClass}">`;
            // Find requerimientos at this hour
            dia.requerimientos.forEach(function(req) {
                if (req.hora && req.hora.startsWith(String(h).padStart(2, '0'))) {
                    const badgeClass = getMatchBadgeClass(req.porcentaje_match);
                    const badgeText = getMatchBadgeText(req.porcentaje_match);
                    const presupuestoHtml = req.presupuesto_display ? `<span style="color:#3fb950;font-weight:600;margin-left:2px;">${req.presupuesto_display}</span>` : '';
                    const agenteHtml = req.agente ? `<span style="color:#ff6d00;font-weight:600;margin-left:2px;">${req.agente}</span>` : '';
                    const distritosHtml = req.distritos ? `<span style="color:var(--text-secondary);margin-left:2px;">· ${req.distritos.substring(0,20)}</span>` : '';
                    const precioPropHtml = (req.mejor_propiedad_precio && req.mejor_propiedad_moneda_id)
                        ? `<span style="color:var(--accent-green);font-weight:600;margin-left:2px;font-size:10px;">· ${getCurrencySymbol(req.mejor_propiedad_moneda_id)}${Number(req.mejor_propiedad_precio).toLocaleString('en-US')}</span>`
                        : '';
                    const verifiedStarHtml = req.verificado
                        ? `<div class="verified-star" style="position:absolute;bottom:2px;right:2px;width:16px;height:16px;z-index:5;pointer-events:none;">
                            <svg viewBox="0 0 24 24" fill="#00ff88" style="width:14px;height:14px;filter:drop-shadow(0 0 6px #00ff88) drop-shadow(0 0 12px #00ff88);animation:verifiedPulse 2s ease-in-out infinite;">
                                <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
                                <path d="M10 13l-2-2-1.5 1.5L10 16l6-6-1.5-1.5z" fill="#0d1117"/>
                            </svg>
                        </div>`
                        : '';
                    const distritosStr = req.distritos_list ? req.distritos_list.join(',') : '';
                    bodyHtml += `<div class="week-req-item" onclick="openMatchModal(${req.id})" style="position:relative;" data-tipo-key="${req.tipo_propiedad_key}" data-distritos="${distritosStr}" data-porcentaje-match="${req.porcentaje_match}">
                        ${verifiedStarHtml}
                        <span class="req-hour">${req.hora_display}</span>
                        <span class="req-title">
                            <span style="color:#58a6ff;font-weight:700;">BUSCO</span>
                            <span style="margin-left:2px;">${req.tipo_propiedad}</span>
                            ${presupuestoHtml}
                            ${distritosHtml}
                            ${agenteHtml}
                            ${precioPropHtml}
                        </span>
                        <span class="match-badge ${badgeClass}">${badgeText}</span>
                    </div>`;
                }
            });
            bodyHtml += '</div>';
        });
        bodyHtml += '</div>';
    }
    body.innerHTML = bodyHtml;
});


// ===== FILTROS DE TIPO DE PROPIEDAD =====
let activeFilters = new Set();

// ===== SWITCH: SOLO CON MATCH =====
let showOnlyWithMatch = false;

// Inicializar: todos los tipos activos por defecto
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.filter-chip[data-tipo]').forEach(function(chip) {
        activeFilters.add(chip.dataset.tipo);
    });
    // Si hay datos cargados, aplicar filtro inicial
    if (typeof diasSemana !== 'undefined') {
        applyFilters();
    }
});

function toggleFilter(el) {
    const tipo = el.dataset.tipo;
    if (activeFilters.has(tipo)) {
        if (activeFilters.size <= 1) return;
        activeFilters.delete(tipo);
        el.classList.remove('active');
    } else {
        activeFilters.add(tipo);
        el.classList.add('active');
    }
    applyFilters();
}

function resetFilters() {
    document.querySelectorAll('.filter-chip[data-tipo]').forEach(function(chip) {
        activeFilters.add(chip.dataset.tipo);
        chip.classList.add('active');
    });
    applyFilters();
}

function toggleSinMatch(checkbox) {
    showOnlyWithMatch = checkbox.checked;
    applyFilters();
}

function applyFilters() {
    // Aplicar a vista week (renderizada con JS)
    if (VIEW_MODE === 'week' && typeof diasSemana !== 'undefined') {
        document.querySelectorAll('.week-req-item').forEach(function(item) {
            const reqTipoKey = item.dataset.tipoKey;
            var visible = true;
            // Filtro por tipo
            if (reqTipoKey && !activeFilters.has(reqTipoKey)) {
                visible = false;
            }
            // Filtro: solo con match
            if (visible && showOnlyWithMatch) {
                const pct = parseFloat(item.dataset.porcentajeMatch);
                if (!pct || pct <= 0) {
                    visible = false;
                }
            }
            item.style.display = visible ? '' : 'none';
        });
    }

    // Aplicar a vista day (renderizada con Django template)
    if (VIEW_MODE === 'day') {
        document.querySelectorAll('.day-event-card').forEach(function(card) {
            const reqTipoKey = card.dataset.tipoKey;
            var visible = true;
            // Filtro por tipo
            if (reqTipoKey && !activeFilters.has(reqTipoKey)) {
                visible = false;
            }
            // Filtro: solo con match
            if (visible && showOnlyWithMatch) {
                const pct = parseFloat(card.dataset.porcentajeMatch);
                if (!pct || pct <= 0) {
                    visible = false;
                }
            }
            card.style.display = visible ? '' : 'none';
        });
        // Ocultar filas de hora sin eventos visibles
        document.querySelectorAll('.day-hour-row').forEach(function(row) {
            const hourContent = row.querySelector('.day-hour-content');
            if (hourContent) {
                const hasVisible = Array.from(hourContent.querySelectorAll('.day-event-card')).some(function(card) {
                    return card.style.display !== 'none';
                });
                if (!hasVisible) {
                    row.style.display = 'none';
                } else {
                    row.style.display = '';
                }
            }
        });
    }
}

// ===== MODAL MATCH DETALLE =====
const API_BASE = '/matching/api/matching';

function closeMatchModal() {
    document.getElementById('modalMatchOverlay').classList.remove('active');
}

function openMatchModal(requerimientoId) {
    const overlay = document.getElementById('modalMatchOverlay');
    const body = document.getElementById('modalMatchBody');
    const title = document.getElementById('modalMatchTitle');
    const btnDashboard = document.getElementById('modalBtnDashboard');

    // Show loading
    overlay.classList.add('active');
    body.innerHTML = `<div class="modal-loading">
        <div class="spinner"></div>
        <p>Cargando matching para requerimiento #${requerimientoId}...</p>
    </div>`;
    title.textContent = `📊 Matching #${requerimientoId}`;
    btnDashboard.href = `/matching/dashboard/?requerimiento_id=${requerimientoId}`;

    // Fetch matching data - traer todos los resultados sin filtro de score mínimo
    fetch(`${API_BASE}/${requerimientoId}/ejecutar/?score_minimo=0`)
        .then(function(res) {
            if (!res.ok) throw new Error('Error al ejecutar matching');
            return res.json();
        })
        .then(function(data) {
            renderMatchModal(data, body, title);
        })
        .catch(function(err) {
            body.innerHTML = `<div class="modal-match-error">
                <div class="error-icon">⚠️</div>
                <p>Error: ${err.message}</p>
            </div>`;
        });
}

// ===== MAPA DE DISTRITOS (de mapeo_ubicaciones.py) =====
var DISTRITOS_MAP = {
    "1":"Arequipa","2":"Alto Selva Alegre","3":"Cayma","4":"Cerro Colorado",
    "5":"Characato","6":"Chiguata","7":"Jacobo Hunter","8":"Jose Luis Bustamante y Rivero",
    "9":"La Joya","10":"Mariano Melgar","11":"Miraflores","12":"Mollebaya",
    "13":"Paucarpata","14":"Pocsi","15":"Polobaya","16":"Quequeña",
    "17":"Sabandia","18":"Sachaca","19":"San Juan de Siguas","20":"San Juan de Tarucani",
    "21":"Santa Isabel de Siguas","22":"Santa Rita de Siguas","23":"Socabaya",
    "24":"Tiabaya","25":"Uchumayo","26":"Vitor","27":"Yanahuara","28":"Yarabamba",
    "29":"Yura","30":"Camana","31":"Jose Maria Quimper","32":"Mariano Nicolas Quimper",
    "33":"Mariscal Caceres","34":"Nicolas de Perierola","35":"Ocoña","36":"Quilca",
    "37":"Samuel Pastor","38":"Umacollo"
};

function getDistritoName(val) {
    if (!val && val !== 0) return '—';
    var key = String(val).trim();
    return DISTRITOS_MAP[key] || key;
}

function getCurrencySymbol(currencyId) {
    if (currencyId == 1) return '$';
    if (currencyId == 2) return 'S/';
    return '';
}

function formatPrice(price, currencyId) {
    if (!price && price !== 0) return '—';
    var sym = getCurrencySymbol(currencyId);
    var num = parseFloat(price).toLocaleString('en-US', {minimumFractionDigits:0, maximumFractionDigits:0});
    return sym ? sym + ' ' + num : num;
}

// ===== WHATSAPP: Enviar propuesta =====
var ultimoRequerimientoData = null;
var ultimaPropiedadTop = null;

function enviarPropuestaWhatsApp() {
    var req = ultimoRequerimientoData;
    var prop = ultimaPropiedadTop;
    
    if (!req) {
        alert('No hay datos de requerimiento disponibles.');
        return;
    }
    
    // 1. Saludo
    var nombreAgente = (req.agente && req.agente.trim()) ? req.agente.trim() : '';
    var saludo = nombreAgente
        ? 'Hola ' + nombreAgente + ' \uD83D\uDC4B'
        : 'Hola \uD83D\uDC4B';
    
    // 2. Cuerpo del mensaje
    var codigo = req.id || '\u2014';
    var fechaStr = '';
    if (req.fecha) {
        try {
            var partes = req.fecha.split('-');
            fechaStr = partes[2] + '/' + partes[1] + '/' + partes[0];
        } catch(e) {
            fechaStr = req.fecha;
        }
    }
    
    var lineas = [];
    lineas.push(saludo);
    lineas.push('');
    lineas.push('Soy *Belen Aguilar De Propify*.');
    lineas.push('');
    lineas.push('Tengo una propiedad para tu requerimiento *' + codigo + '* del ' + fechaStr + '.');
    lineas.push('');
    lineas.push('\uD83D\uDCCB *Tu requerimiento:*');
    lineas.push(req.requerimiento || '\u2014');
    lineas.push('');
    
    // 3. Datos de la propiedad (si hay)
    if (prop) {
        lineas.push('\uD83C\uDFE0 *Mi propiedad es:*');
        lineas.push('');
        if (prop.title) lineas.push('\uD83D\uDCCC ' + prop.title);
        if (prop.district) lineas.push('\uD83D\uDCCD Distrito: ' + getDistritoName(prop.district));
        if (prop.price) lineas.push('\uD83D\uDCB0 Precio: ' + formatPrice(prop.price, prop.currency_id));
        if (prop.bedrooms) lineas.push('\uD83D\uDECF\uFE0F Habitaciones: ' + prop.bedrooms);
        if (prop.bathrooms) lineas.push('\uD83D\uDEBF Ba\u00F1os: ' + prop.bathrooms);
        if (prop.built_area) lineas.push('\uD83D\uDCD0 \u00C1rea: ' + prop.built_area + ' m\u00B2');
        if (prop.code) lineas.push('\uD83D\uDCDD C\u00F3digo: ' + prop.code);
        lineas.push('');
        if (prop.imagen_url) {
            lineas.push('\uD83D\uDDBC\uFE0F ' + prop.imagen_url);
            lineas.push('');
        }
    }
    
    // 4. Links de ejemplo
    lineas.push('\uD83D\uDD17 Ver propiedad: https://propifai.com/propiedad/' + (prop ? prop.id : '\u2014'));
    lineas.push('\uD83D\uDCC5 Agendar visita: https://propifai.com/agendar?ref=wa_' + codigo);
    lineas.push('');
    lineas.push('\u00BFTe interesa? Responde:');
    
    // 5. Botones visuales con Unicode box drawing
    lineas.push('\u250C\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2510');
    lineas.push('\u2502 \u2705 S\u00ED, me interesa           \u2502');
    lineas.push('\u251C\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2524');
    lineas.push('\u2502 \u274C No, gracias               \u2502');
    lineas.push('\u251C\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2524');
    lineas.push('\u2502 \uD83D\uDCC5 Agendar una visita        \u2502');
    lineas.push('\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2518');
    
    var mensaje = lineas.join('\n');
    
    // 6. Guardar propuesta en BD via API
    var bodyData = {
        requerimiento_id: req.id,
        propiedad_id: prop ? prop.id : null,
        propiedad_code: prop ? prop.code : '',
        propiedad_title: prop ? prop.title : '',
        propiedad_price: prop ? prop.price : null,
        propiedad_currency_id: prop ? prop.currency_id : null,
        propiedad_district_id: prop ? (prop.district ? parseInt(prop.district) : null) : null,
        agente_nombre: req.agente || '',
        agente_telefono: req.agente_telefono || '',
        mensaje: mensaje,
    };

    fetch('/matching/api/propuesta/guardar/', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(bodyData),
    }).catch(function(err) {
        console.warn('Error guardando propuesta:', err);
    });

    // 7. Abrir WhatsApp con número si está disponible
    var telefono = (req.agente_telefono || '').replace(/[^0-9]/g, '');
    var url;
    if (telefono) {
        url = 'https://api.whatsapp.com/send?phone=' + telefono + '&text=' + encodeURIComponent(mensaje);
    } else {
        url = 'https://api.whatsapp.com/send?text=' + encodeURIComponent(mensaje);
    }
    window.open(url, '_blank');
}

function renderMatchModal(data, body, title) {
    const req = data.requerimiento || {};
    const resultados = data.resultados || [];
    const estadisticas = data.estadisticas || {};
    
    // Guardar datos para WhatsApp
    ultimoRequerimientoData = req;
    ultimaPropiedadTop = resultados.length > 0 ? (resultados[0].propiedad || null) : null;

    // Consultar si ya hay propuesta enviada para este requerimiento
    var propuestaEnviada = false;
    var propuestaId = null;
    var xhr = new XMLHttpRequest();
    xhr.open('GET', '/matching/api/propuesta/listar/?requerimiento_id=' + (req.id || ''), false);
    xhr.send();
    if (xhr.status === 200) {
        var props = JSON.parse(xhr.responseText);
        if (props && props.length > 0) {
            propuestaEnviada = true;
            propuestaId = props[0].id;
        }
    }
    
    // Mostrar/ocultar boton WhatsApp (solo si hay match >= 70%)
    var btnWA = document.getElementById('btnWhatsAppPropuesta');
    if (btnWA) {
        var scoreTotalWA = resultados.length > 0 ? parseFloat(resultados[0].score_total || 0) : 0;
        btnWA.style.display = (scoreTotalWA >= 70) ? 'inline-flex' : 'none';
    }

    if (resultados.length === 0) {
        body.innerHTML = `<div class="modal-no-match">
            <div class="no-match-icon">🔍</div>
            <p>No se encontraron propiedades con coincidencia para este requerimiento.</p>
            ${propuestaEnviada ? '<div style="margin-top:12px;padding:8px 12px;border-radius:6px;background:rgba(0,255,136,0.12);border:1px solid rgba(0,255,136,0.4);text-align:center;font-size:13px;font-weight:600;color:#00ff88;">✅ WhatsApp enviado a ' + (req.agente || 'agente') + '</div>' : ''}
        </div>`;
        return;
    }

    const topResult = resultados[0];
    const prop = topResult.propiedad || {};
    const scoreDetalle = topResult.score_detalle || {};
    const scoreTotal = parseFloat(topResult.score_total || 0);

    // Determine score class
    var scoreClass = 'low';
    if (scoreTotal >= 90) scoreClass = 'high';
    else if (scoreTotal >= 50) scoreClass = 'medium';

    // Resolver distrito de propiedad (ID → nombre)
    var propDistrito = getDistritoName(prop.district);

    // Resolver moneda de propiedad
    var propCurrencySym = getCurrencySymbol(prop.currency_id);
    var propPriceFormatted = formatPrice(prop.price, prop.currency_id);

    // Helper: get row class based on score_detalle
    function getRowClass(key) {
        if (!key || scoreDetalle[key] === undefined) return '';
        var val = parseFloat(scoreDetalle[key]);
        if (val >= 0.8) return 'row-match';
        if (val >= 0.3) return 'row-partial';
        return 'row-no-match';
    }

    // Helper: format value for display
    function fmt(val, fallback) {
        return (val !== null && val !== undefined && val !== '') ? val : (fallback || '—');
    }

    // Property image
    var propImgHtml = '';
    if (prop.imagen_url) {
        propImgHtml = '<img src="' + prop.imagen_url + '" alt="' + (prop.title || 'Propiedad') + '" style="width:120px;height:90px;object-fit:cover;border-radius:6px;background:var(--bg-tertiary);border:1px solid var(--border-color);" onerror="this.style.display=\'none\'">';
    } else {
        propImgHtml = '<div style="width:120px;height:90px;border-radius:6px;background:var(--bg-tertiary);border:1px solid var(--border-color);display:flex;align-items:center;justify-content:center;color:var(--text-muted);font-size:11px;margin:0 auto;">🏠 Sin imagen</div>';
    }

    body.innerHTML = `
        <div class="modal-compare-panel">
            <table class="compare-table">
                <thead>
                    <tr>
                        <th>Campo</th>
                        <th>📋 Req</th>
                        <th>🏠 Prop</th>
                    </tr>
                </thead>
                <tbody>
                    <tr class="${getRowClass('tipo_propiedad')}">
                        <td class="col-label">Tipo</td>
                        <td class="col-req">${fmt(req.tipo_propiedad)}</td>
                        <td class="col-prop">${fmt(prop.tipo_propiedad)}</td>
                    </tr>
                    <tr class="${getRowClass('condicion')}">
                        <td class="col-label">Condición</td>
                        <td class="col-req">${fmt(req.condicion)}</td>
                        <td class="col-prop">${fmt(prop.operation_type_name || (prop.operation_type_id == 2 ? 'compra' : prop.operation_type_id == 3 ? 'alquiler' : '—'))}</td>
                    </tr>
                    <tr class="${getRowClass('distrito')}">
                        <td class="col-label">Distrito</td>
                        <td class="col-req">${fmt(req.distritos)}</td>
                        <td class="col-prop">${propDistrito}</td>
                    </tr>
                    <tr class="${getRowClass('precio')}">
                        <td class="col-label">Precio</td>
                        <td class="col-req">${fmt(req.presupuesto_display)}</td>
                        <td class="col-prop">${propPriceFormatted}</td>
                    </tr>
                    <tr class="${getRowClass('habitaciones')}">
                        <td class="col-label">Habitaciones</td>
                        <td class="col-req">${fmt(req.habitaciones)}</td>
                        <td class="col-prop">${fmt(prop.bedrooms)}</td>
                    </tr>
                    <tr class="${getRowClass('banos')}">
                        <td class="col-label">Baños</td>
                        <td class="col-req">${fmt(req.banos)}</td>
                        <td class="col-prop">${fmt(prop.bathrooms)}</td>
                    </tr>
                    <tr class="${getRowClass('area')}">
                        <td class="col-label">Área m²</td>
                        <td class="col-req">${fmt(req.area_m2)}</td>
                        <td class="col-prop">${fmt(prop.built_area)}</td>
                    </tr>
                    <tr class="${getRowClass('estacionamiento')}">
                        <td class="col-label">Cochera</td>
                        <td class="col-req">${req.cochera ? 'Sí' : 'No'}</td>
                        <td class="col-prop">${prop.garage_spaces ? prop.garage_spaces + ' auto(s)' : 'No'}</td>
                    </tr>
                    <tr class="${getRowClass('ascensor')}">
                        <td class="col-label">Ascensor</td>
                        <td class="col-req">${req.ascensor ? 'Sí' : 'No'}</td>
                        <td class="col-prop">${prop.ascensor ? 'Sí' : 'No'}</td>
                    </tr>
                    <tr class="${getRowClass('amenities')}">
                        <td class="col-label">Amueblado</td>
                        <td class="col-req">${req.amueblado ? 'Sí' : 'No'}</td>
                        <td class="col-prop">${prop.amenities ? 'Sí' : 'No'}</td>
                    </tr>
                </tbody>
            </table>
        </div>

        <div class="modal-req-panel">
            <div style="font-size:12px;font-weight:600;color:var(--accent-blue);">📝 Requerimiento original</div>
            <div class="modal-req-text">${fmt(req.requerimiento || '—')}</div>
        </div>

        <div class="modal-side-panel">
            <div class="modal-score-box" style="padding:10px;text-align:center;">
                <div class="score-num ${scoreClass}" style="font-size:32px;">${Math.round(scoreTotal)}%</div>
                <div class="score-label" style="font-size:10px;">Coincidencia</div>
            </div>

            <div style="text-align:center;">
                ${propImgHtml}
                <div class="modal-side-code" style="font-size:10px;margin-top:4px;">${fmt(prop.code)}</div>
                <div class="modal-side-title" style="font-size:12px;font-weight:600;color:var(--text-primary);">${fmt(prop.title)}</div>
                ${prop.real_address ? '<div style="font-size:10px;color:var(--text-muted);">' + prop.real_address + '</div>' : ''}
            </div>

            <div style="font-size:11px;margin-top:4px;">
                <div style="display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid rgba(48,54,61,0.3);"><span style="color:var(--text-secondary);">Precio</span><span style="color:var(--accent-green);font-weight:600;">${propPriceFormatted}</span></div>
                <div style="display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid rgba(48,54,61,0.3);"><span style="color:var(--text-secondary);">Distrito</span><span style="color:var(--text-primary);">${propDistrito}</span></div>
                <div style="display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid rgba(48,54,61,0.3);"><span style="color:var(--text-secondary);">Tipo</span><span style="color:var(--text-primary);">${fmt(prop.tipo_propiedad)}</span></div>
                <div style="display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid rgba(48,54,61,0.3);"><span style="color:var(--text-secondary);">Condición</span><span style="color:var(--text-primary);">${fmt(prop.operation_type_name || (prop.operation_type_id == 2 ? 'Venta' : prop.operation_type_id == 3 ? 'Alquiler' : '—'))}</span></div>
                <div style="display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid rgba(48,54,61,0.3);"><span style="color:var(--text-secondary);">Habitaciones</span><span style="color:var(--text-primary);">${fmt(prop.bedrooms)}</span></div>
                <div style="display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid rgba(48,54,61,0.3);"><span style="color:var(--text-secondary);">Baños</span><span style="color:var(--text-primary);">${fmt(prop.bathrooms)}</span></div>
                <div style="display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid rgba(48,54,61,0.3);"><span style="color:var(--text-secondary);">Área m²</span><span style="color:var(--text-primary);">${fmt(prop.built_area)}</span></div>
                <div style="display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid rgba(48,54,61,0.3);"><span style="color:var(--text-secondary);">Cochera</span><span style="color:var(--text-primary);">${prop.garage_spaces ? prop.garage_spaces + ' auto(s)' : 'No'}</span></div>
                <div style="display:flex;justify-content:space-between;padding:3px 0;"><span style="color:var(--text-secondary);">Ascensor</span><span style="color:var(--text-primary);">${prop.ascensor ? 'Sí' : 'No'}</span></div>
            </div>

            ${propuestaEnviada ? '<div style="margin-top:6px;padding:6px 10px;border-radius:6px;background:rgba(0,255,136,0.12);border:1px solid rgba(0,255,136,0.4);text-align:center;font-size:11px;font-weight:600;color:#00ff88;text-shadow:0 0 8px rgba(0,255,136,0.3);animation:waPulse 2s ease-in-out infinite;">✅ WhatsApp enviado</div>' : ''}
        </div>
    `;

    // Estilo para la animacion del badge
    var style = document.createElement('style');
    style.textContent = '@keyframes waPulse { 0%,100% { box-shadow: 0 0 4px rgba(0,255,136,0.2); } 50% { box-shadow: 0 0 12px rgba(0,255,136,0.5); } }';
    document.head.appendChild(style);
    `;

    title.textContent = `📊 Match #${req.id || ''} — ${Math.round(scoreTotal)}%`;
}

// Close modal on Escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') closeMatchModal();
});
