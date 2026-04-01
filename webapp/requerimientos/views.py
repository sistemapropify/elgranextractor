from django.views.generic import ListView, DetailView, RedirectView, TemplateView
from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone
from datetime import datetime, timedelta
import json
from .models import Requerimiento, FuenteChoices, CondicionChoices, TipoPropiedadChoices
from .analytics import (
    obtener_requerimientos_por_mes,
    calcular_crecimiento_porcentual,
    obtener_distritos_por_mes,
    obtener_tipos_propiedad_por_mes,
    obtener_presupuesto_por_mes,
    obtener_caracteristicas_demandadas,
    detectar_picos_y_valles,
    calcular_tendencia
)
from .tasks import generar_analisis_temporal, obtener_progreso_tarea


class ListaRequerimientosView(ListView):
    model = Requerimiento
    template_name = 'requerimientos/lista.html'
    paginate_by = 20
    context_object_name = 'requerimientos'
    ordering = ['-fecha', '-hora']

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filtros básicos
        fuente = self.request.GET.get('fuente')
        condicion = self.request.GET.get('condicion')
        tipo_propiedad = self.request.GET.get('tipo_propiedad')
        distrito = self.request.GET.get('distrito')
        presupuesto_min = self.request.GET.get('presupuesto_min')
        presupuesto_max = self.request.GET.get('presupuesto_max')
        
        if fuente:
            queryset = queryset.filter(fuente=fuente)
        if condicion:
            queryset = queryset.filter(condicion=condicion)
        if tipo_propiedad:
            queryset = queryset.filter(tipo_propiedad=tipo_propiedad)
        if distrito:
            queryset = queryset.filter(distritos__icontains=distrito)
        
        # Filtro por presupuesto mínimo
        if presupuesto_min:
            try:
                min_val = float(presupuesto_min)
                queryset = queryset.filter(presupuesto_monto__gte=min_val)
            except (ValueError, TypeError):
                pass
        
        # Filtro por presupuesto máximo
        if presupuesto_max:
            try:
                max_val = float(presupuesto_max)
                queryset = queryset.filter(presupuesto_monto__lte=max_val)
            except (ValueError, TypeError):
                pass
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Agregar opciones de filtro como listas de tuplas (value, label)
        context['fuentes'] = FuenteChoices.choices
        context['condiciones'] = CondicionChoices.choices
        context['tipos_propiedad'] = TipoPropiedadChoices.choices
        return context


class DetalleRequerimientoView(DetailView):
    model = Requerimiento
    template_name = 'requerimientos/detalle.html'
    context_object_name = 'requerimiento'


class SubirExcelView(RedirectView):
    """Redirige a la subida de Excel de la app ingestas."""
    pattern_name = 'ingestas:subir_excel'


# ─────────────────────────────────────────────
#  VISTAS DE ANÁLISIS TEMPORAL
# ─────────────────────────────────────────────

class DashboardAnalisisTemporalView(TemplateView):
    """Vista principal del dashboard de análisis temporal."""
    template_name = 'requerimientos/dashboard_analisis.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtener filtros de la URL
        fecha_inicio = self.request.GET.get('fecha_inicio')
        fecha_fin = self.request.GET.get('fecha_fin')
        condicion = self.request.GET.get('condicion')
        tipo_propiedad = self.request.GET.get('tipo_propiedad')
        distrito = self.request.GET.get('distrito')
        fuente = self.request.GET.get('fuente')
        
        # Convertir fechas
        if fecha_inicio:
            fecha_inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
        if fecha_fin:
            fecha_fin = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
        
        filtros = {
            'condicion': condicion,
            'tipo_propiedad': tipo_propiedad,
            'distrito': distrito,
            'fuente': fuente,
        }
        
        # Obtener datos para el dashboard
        context['filtros'] = filtros
        context['fecha_inicio'] = fecha_inicio
        context['fecha_fin'] = fecha_fin
        
        # Opciones para filtros
        context['fuentes'] = FuenteChoices.choices
        context['condiciones'] = CondicionChoices.choices
        context['tipos_propiedad'] = TipoPropiedadChoices.choices
        
        return context


class ApiAnalisisTemporalView(TemplateView):
    """API que retorna datos JSON para el dashboard (modo síncrono o asíncrono)."""
    
    def get(self, request, *args, **kwargs):
        # Verificar si se solicita modo asíncrono
        async_mode = request.GET.get('async', 'false').lower() == 'true'
        
        if async_mode:
            return self._iniciar_analisis_asincrono(request)
        else:
            return self._obtener_analisis_sincrono(request)
    
    def _obtener_analisis_sincrono(self, request):
        """Retorna análisis inmediato (para datasets pequeños)."""
        try:
            # Obtener filtros
            fecha_inicio = request.GET.get('fecha_inicio')
            fecha_fin = request.GET.get('fecha_fin')
            condicion = request.GET.get('condicion')
            tipo_propiedad = request.GET.get('tipo_propiedad')
            distrito = request.GET.get('distrito')
            fuente = request.GET.get('fuente')
            
            # Convertir fechas
            if fecha_inicio:
                fecha_inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
            if fecha_fin:
                fecha_fin = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
            
            filtros = {
                'condicion': condicion,
                'tipo_propiedad': tipo_propiedad,
                'distrito': distrito,
                'fuente': fuente,
            }
            
            # Obtener todos los datos con manejo de errores individual
            try:
                datos_mes = list(obtener_requerimientos_por_mes(fecha_inicio, fecha_fin, filtros))
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error en obtener_requerimientos_por_mes: {e}")
                datos_mes = []
            
            try:
                distritos_mes = obtener_distritos_por_mes(fecha_inicio, fecha_fin)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error en obtener_distritos_por_mes: {e}")
                distritos_mes = {'distritos': [], 'data': {}, 'meses': []}
            
            try:
                tipos_mes = obtener_tipos_propiedad_por_mes(fecha_inicio, fecha_fin)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error en obtener_tipos_propiedad_por_mes: {e}")
                tipos_mes = {'tipos': [], 'data': {}, 'meses': []}
            
            try:
                presupuesto_mes = obtener_presupuesto_por_mes(fecha_inicio, fecha_fin)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error en obtener_presupuesto_por_mes: {e}")
                presupuesto_mes = []
            
            try:
                caracteristicas_mes = obtener_caracteristicas_demandadas(fecha_inicio, fecha_fin)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error en obtener_caracteristicas_demandadas: {e}")
                caracteristicas_mes = {}
            
            # Calcular crecimiento y tendencias
            totales = [item['total'] for item in datos_mes] if datos_mes else []
            try:
                crecimiento = calcular_crecimiento_porcentual(totales)
            except Exception as e:
                crecimiento = []
            
            try:
                picos, valles = detectar_picos_y_valles(totales)
            except Exception as e:
                picos, valles = [], []
            
            try:
                tendencia = calcular_tendencia(totales)
            except Exception as e:
                tendencia = 'estable'
            
            # Generar insights
            try:
                insights = self._generar_insights(
                    datos_mes, distritos_mes, tipos_mes, presupuesto_mes
                )
            except Exception as e:
                insights = []
            
            # Preparar respuesta
            response_data = {
                'success': True,
                'mode': 'sync',
                'datos_mes': datos_mes,
                'distritos_mes': distritos_mes,
                'tipos_mes': tipos_mes,
                'presupuesto_mes': presupuesto_mes,
                'caracteristicas_mes': caracteristicas_mes,
                'metricas': {
                    'totales': totales,
                    'crecimiento': crecimiento,
                    'picos': picos,
                    'valles': valles,
                    'tendencia': tendencia,
                },
                'insights': insights,
            }
            
            return JsonResponse(response_data, safe=False)
            
        except Exception as e:
            # Log del error para diagnóstico
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error en _obtener_analisis_sincrono: {e}", exc_info=True)
            
            # Intentar devolver datos de ejemplo si la base de datos está vacía
            try:
                # Verificar si hay datos en la base de datos
                from .models import Requerimiento
                if Requerimiento.objects.exists():
                    # Hay datos pero hay un error en el procesamiento
                    return JsonResponse({
                        'success': False,
                        'error': str(e),
                        'mode': 'sync',
                        'message': 'Error procesando datos existentes'
                    }, status=500)
                else:
                    # Base de datos vacía, devolver datos de ejemplo para demostración
                    return self._devolver_datos_ejemplo()
            except Exception as inner_e:
                # Si falla la verificación, devolver error genérico
                return JsonResponse({
                    'success': False,
                    'error': f"{str(e)} (adicional: {str(inner_e)})",
                    'mode': 'sync',
                    'message': 'Error crítico en el análisis'
                }, status=500)
    
    def _iniciar_analisis_asincrono(self, request):
        """Inicia análisis asíncrono y retorna ID de tarea."""
        try:
            # Obtener filtros
            fecha_inicio = request.GET.get('fecha_inicio')
            fecha_fin = request.GET.get('fecha_fin')
            condicion = request.GET.get('condicion')
            tipo_propiedad = request.GET.get('tipo_propiedad')
            distrito = request.GET.get('distrito')
            fuente = request.GET.get('fuente')
            
            filtros = {
                'condicion': condicion,
                'tipo_propiedad': tipo_propiedad,
                'distrito': distrito,
                'fuente': fuente,
            }
            
            # Lanzar tarea asíncrona
            task = generar_analisis_temporal.delay(
                filtros=filtros,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin
            )
            
            return JsonResponse({
                'success': True,
                'mode': 'async',
                'task_id': task.id,
                'status_url': f'/requerimientos/api/analisis-progreso/{task.id}/',
                'message': 'Análisis iniciado en segundo plano'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e),
                'mode': 'async'
            }, status=500)
    
    def _generar_insights(self, datos_mes, distritos_mes, tipos_mes, presupuesto_mes):
        """Genera insights automáticos en lenguaje natural."""
        insights = []
        
        if not datos_mes:
            return insights
        
        # Insight 1: Mes con más demanda
        max_mes = max(datos_mes, key=lambda x: x['total'])
        min_mes = min(datos_mes, key=lambda x: x['total'])
        
        insights.append({
            'icono': '🔥',
            'titulo': f'Mes pico: {max_mes["mes"].strftime("%B %Y")}',
            'descripcion': f'{max_mes["total"]} requerimientos (+{max_mes["total"] - min_mes["total"]} vs mes más bajo)',
            'tipo': 'destacado'
        })
        
        # Insight 2: Crecimiento total
        if len(datos_mes) >= 2:
            primer_mes = datos_mes[0]['total']
            ultimo_mes = datos_mes[-1]['total']
            if primer_mes > 0:
                crecimiento_total = ((ultimo_mes - primer_mes) / primer_mes) * 100
                tendencia = '📈' if crecimiento_total > 0 else '📉'
                insights.append({
                    'icono': tendencia,
                    'titulo': f'Crecimiento total: {crecimiento_total:.1f}%',
                    'descripcion': f'De {primer_mes} a {ultimo_mes} requerimientos',
                    'tipo': 'tendencia'
                })
        
        # Insight 3: Distrito líder
        if distritos_mes['distritos']:
            # Calcular total por distrito
            distrito_totales = {}
            for distrito in distritos_mes['distritos']:
                total = sum(distritos_mes['data'][distrito].values())
                distrito_totales[distrito] = total
            
            top_distrito = max(distrito_totales.items(), key=lambda x: x[1])
            insights.append({
                'icono': '🏆',
                'titulo': f'Distrito líder: {top_distrito[0]}',
                'descripcion': f'{top_distrito[1]} requerimientos en el período',
                'tipo': 'liderazgo'
            })
        
        # Insight 4: Tipo de propiedad más buscado
        if tipos_mes['tipos']:
            tipo_totales = {}
            for tipo in tipos_mes['tipos']:
                total = sum(tipos_mes['data'][tipo])
                tipo_totales[tipo] = total
            
            top_tipo = max(tipo_totales.items(), key=lambda x: x[1])
            tipo_display = dict(TipoPropiedadChoices.choices).get(top_tipo[0], top_tipo[0])
            insights.append({
                'icono': '🏠',
                'titulo': f'Tipo más buscado: {tipo_display}',
                'descripcion': f'{top_tipo[1]} requerimientos ({top_tipo[1]/sum(tipo_totales.values())*100:.1f}%)',
                'tipo': 'preferencia'
            })
        
        return insights

    def _devolver_datos_ejemplo(self):
        """Devuelve datos de ejemplo para demostración cuando la base de datos está vacía."""
        from datetime import datetime, timedelta
        import random
        
        # Generar datos de ejemplo para los últimos 6 meses
        meses = []
        fecha_actual = datetime.now().date()
        for i in range(6):
            mes = fecha_actual.replace(day=1) - timedelta(days=i*30)
            meses.append({
                'mes': mes,
                'total': random.randint(10, 50),
                'compra': random.randint(5, 25),
                'alquiler': random.randint(5, 25),
                'departamento': random.randint(3, 20),
                'casa': random.randint(2, 15),
                'terreno': random.randint(1, 10),
                'presupuesto_promedio': random.uniform(50000, 200000),
                'presupuesto_mediano': None,
                'cochera_si': random.randint(0, 10),
                'ascensor_si': random.randint(0, 5),
                'amueblado_si': random.randint(0, 8),
            })
        
        # Datos de ejemplo para distritos
        distritos_ejemplo = ['Cayma', 'Yanahuara', 'Cerro Colorado', 'Sachaca', 'Hunter']
        distritos_data = {}
        for distrito in distritos_ejemplo:
            distritos_data[distrito] = {mes['mes'].strftime('%Y-%m'): random.randint(1, 10) for mes in meses}
        
        # Datos de ejemplo para tipos de propiedad
        tipos_ejemplo = ['departamento', 'casa', 'terreno', 'oficina', 'local_comercial']
        tipos_data = {}
        for tipo in tipos_ejemplo:
            tipos_data[tipo] = [random.randint(1, 15) for _ in range(len(meses))]
        
        # Datos de ejemplo para presupuesto
        presupuesto_data = [{
            'mes': mes['mes'],
            'presupuesto_promedio': mes['presupuesto_promedio'],
            'presupuesto_mediano': None,
            'cantidad': mes['total']
        } for mes in meses]
        
        # Datos de ejemplo para características
        caracteristicas_data = {
            'cochera': random.randint(20, 80),
            'ascensor': random.randint(10, 50),
            'amueblado': random.randint(15, 60),
            'habitaciones_3': random.randint(5, 40),
            'banos_2': random.randint(10, 50),
        }
        
        # Calcular métricas
        totales = [mes['total'] for mes in meses]
        crecimiento = [None] + [random.uniform(-20, 30) for _ in range(len(meses)-1)]
        picos = [i for i, val in enumerate(totales) if val == max(totales)]
        valles = [i for i, val in enumerate(totales) if val == min(totales)]
        tendencia = 'creciente' if totales[-1] > totales[0] else 'decreciente'
        
        # Insights de ejemplo
        insights = [
            {
                'icono': '🔥',
                'titulo': 'Mes pico: ' + meses[picos[0]]['mes'].strftime('%B %Y'),
                'descripcion': f'{totales[picos[0]]} requerimientos',
                'tipo': 'destacado'
            },
            {
                'icono': '📈',
                'titulo': f'Crecimiento total: {((totales[-1] - totales[0]) / totales[0] * 100):.1f}%',
                'descripcion': f'De {totales[0]} a {totales[-1]} requerimientos',
                'tipo': 'tendencia'
            },
            {
                'icono': '🏆',
                'titulo': f'Distrito líder: {distritos_ejemplo[0]}',
                'descripcion': f'{sum(distritos_data[distritos_ejemplo[0]].values())} requerimientos',
                'tipo': 'liderazgo'
            },
            {
                'icono': '🏠',
                'titulo': f'Tipo más buscado: Departamento',
                'descripcion': f'{sum(tipos_data["departamento"])} requerimientos',
                'tipo': 'preferencia'
            },
        ]
        
        response_data = {
            'success': True,
            'mode': 'sync',
            'datos_mes': meses,
            'distritos_mes': {
                'distritos': distritos_ejemplo,
                'data': distritos_data,
                'meses': [mes['mes'].strftime('%Y-%m') for mes in meses]
            },
            'tipos_mes': {
                'tipos': tipos_ejemplo,
                'data': tipos_data,
                'meses': [mes['mes'].strftime('%Y-%m') for mes in meses]
            },
            'presupuesto_mes': presupuesto_data,
            'caracteristicas_mes': caracteristicas_data,
            'metricas': {
                'totales': totales,
                'crecimiento': crecimiento,
                'picos': picos,
                'valles': valles,
                'tendencia': tendencia,
            },
            'insights': insights,
            'is_sample_data': True,
            'message': 'Se están mostrando datos de ejemplo porque la base de datos está vacía.'
        }
        
        from django.http import JsonResponse
        return JsonResponse(response_data, safe=False)


class ApiAnalisisProgresoView(TemplateView):
    """API para consultar progreso de análisis asíncrono."""
    
    def get(self, request, task_id, *args, **kwargs):
        progreso = obtener_progreso_tarea(task_id)
        
        # Mapear estados para compatibilidad con frontend
        status_map = {
            'processing': 'PROGRESS',
            'completed': 'SUCCESS',
            'failed': 'FAILURE',
            'pending': 'PENDING',
            'unknown': 'PENDING'
        }
        
        status = progreso.get('status', 'unknown')
        mapped_status = status_map.get(status, 'PENDING')
        
        response_data = {
            'task_id': task_id,
            'status': mapped_status,
            'progress': progreso.get('progress', 0),
            'message': progreso.get('message', ''),
            'current_step': progreso.get('current_step', 'Procesando'),
            'generated_at': progreso.get('generated_at')
        }
        
        # Si la tarea está completada, incluir los datos en 'result'
        if mapped_status == 'SUCCESS' and 'data' in progreso:
            response_data['result'] = progreso['data']
        
        # Si hay error, incluir detalles
        if mapped_status == 'FAILURE':
            response_data['error'] = progreso.get('error', 'Error desconocido')
        
        return JsonResponse(response_data)


class ExportarAnalisisExcelView(TemplateView):
    """Exporta el análisis a Excel."""
    
    def get(self, request, *args, **kwargs):
        try:
            import openpyxl
            from openpyxl import Workbook
            from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
            from django.http import HttpResponse
            import io
            
            # Crear libro de trabajo
            wb = Workbook()
            ws = wb.active
            ws.title = "Análisis Temporal"
            
            # Estilos
            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
            header_alignment = Alignment(horizontal="center", vertical="center")
            thin_border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )
            
            # Título
            ws.merge_cells('A1:G1')
            title_cell = ws['A1']
            title_cell.value = "ANÁLISIS TEMPORAL DE REQUERIMIENTOS INMOBILIARIOS"
            title_cell.font = Font(bold=True, size=16)
            title_cell.alignment = Alignment(horizontal="center")
            
            # Subtítulo con filtros aplicados
            ws.merge_cells('A2:G2')
            subtitle = f"Generado el {timezone.now().strftime('%d/%m/%Y %H:%M')}"
            ws['A2'].value = subtitle
            ws['A2'].alignment = Alignment(horizontal="center")
            ws['A2'].font = Font(italic=True)
            
            # Encabezados de sección
            headers = ['Mes', 'Total Requerimientos', 'Compra', 'Alquiler',
                      'Departamento', 'Casa', 'Terreno', 'Presupuesto Promedio']
            
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=4, column=col, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_alignment
                cell.border = thin_border
            
            # Obtener datos (similar a la API)
            fecha_inicio = request.GET.get('fecha_inicio')
            fecha_fin = request.GET.get('fecha_fin')
            filtros = {
                'condicion': request.GET.get('condicion'),
                'tipo_propiedad': request.GET.get('tipo_propiedad'),
                'distrito': request.GET.get('distrito'),
                'fuente': request.GET.get('fuente'),
            }
            
            datos_mes = list(obtener_requerimientos_por_mes(fecha_inicio, fecha_fin, filtros))
            
            # Llenar datos
            for row, dato in enumerate(datos_mes, 5):
                ws.cell(row=row, column=1, value=dato['mes'].strftime('%B %Y') if dato['mes'] else '')
                ws.cell(row=row, column=2, value=dato['total'])
                ws.cell(row=row, column=3, value=dato['compra'])
                ws.cell(row=row, column=4, value=dato['alquiler'])
                ws.cell(row=row, column=5, value=dato['departamento'])
                ws.cell(row=row, column=6, value=dato['casa'])
                ws.cell(row=row, column=7, value=dato['terreno'])
                ws.cell(row=row, column=8, value=float(dato['presupuesto_promedio']) if dato['presupuesto_promedio'] else 0)
            
            # Ajustar anchos de columna
            for column in ws.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 30)
                ws.column_dimensions[column_letter].width = adjusted_width
            
            # Preparar respuesta
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            
            response = HttpResponse(
                output.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = 'attachment; filename="analisis_temporal_requerimientos.xlsx"'
            return response
            
        except ImportError:
            from django.http import HttpResponse
            return HttpResponse("Error: openpyxl no está instalado. Ejecute 'pip install openpyxl'", status=500)
        except Exception as e:
            from django.http import HttpResponse
            return HttpResponse(f"Error al generar Excel: {str(e)}", status=500)


class ExportarAnalisisPDFView(TemplateView):
    """Exporta el análisis a PDF."""
    
    def get(self, request, *args, **kwargs):
        try:
            from reportlab.lib.pagesizes import letter, landscape
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
            from reportlab.lib.units import inch
            from django.http import HttpResponse
            import io
            
            # Crear buffer para PDF
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
            elements = []
            styles = getSampleStyleSheet()
            
            # Título
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=18,
                spaceAfter=12,
                alignment=1  # Centrado
            )
            title = Paragraph("ANÁLISIS TEMPORAL DE REQUERIMIENTOS INMOBILIARIOS", title_style)
            elements.append(title)
            
            # Subtítulo
            subtitle_style = ParagraphStyle(
                'CustomSubtitle',
                parent=styles['Normal'],
                fontSize=10,
                spaceAfter=24,
                alignment=1,
                textColor=colors.grey
            )
            subtitle = Paragraph(
                f"Generado el {timezone.now().strftime('%d/%m/%Y %H:%M')} | "
                f"Sistema de Análisis Inmobiliario",
                subtitle_style
            )
            elements.append(subtitle)
            
            # Obtener datos
            fecha_inicio = request.GET.get('fecha_inicio')
            fecha_fin = request.GET.get('fecha_fin')
            filtros = {
                'condicion': request.GET.get('condicion'),
                'tipo_propiedad': request.GET.get('tipo_propiedad'),
                'distrito': request.GET.get('distrito'),
                'fuente': request.GET.get('fuente'),
            }
            
            datos_mes = list(obtener_requerimientos_por_mes(fecha_inicio, fecha_fin, filtros))
            
            # Crear tabla de datos
            if datos_mes:
                table_data = []
                # Encabezados
                headers = ['Mes', 'Total', 'Compra', 'Alquiler', 'Depto.', 'Casa', 'Terreno', 'Presupuesto']
                table_data.append(headers)
                
                # Filas de datos
                for dato in datos_mes:
                    row = [
                        dato['mes'].strftime('%b %Y') if dato['mes'] else '',
                        str(dato['total']),
                        str(dato['compra']),
                        str(dato['alquiler']),
                        str(dato['departamento']),
                        str(dato['casa']),
                        str(dato['terreno']),
                        f"${dato['presupuesto_promedio']:,.0f}" if dato['presupuesto_promedio'] else '$0'
                    ]
                    table_data.append(row)
                
                # Crear tabla
                table = Table(table_data, colWidths=[1.2*inch, 0.7*inch, 0.7*inch, 0.7*inch,
                                                     0.7*inch, 0.7*inch, 0.7*inch, 1*inch])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2C3E50')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                ]))
                
                elements.append(Spacer(1, 0.25*inch))
                elements.append(table)
            
            # Nota al pie
            elements.append(Spacer(1, 0.5*inch))
            note_style = ParagraphStyle(
                'NoteStyle',
                parent=styles['Normal'],
                fontSize=8,
                textColor=colors.grey,
                alignment=1
            )
            note = Paragraph(
                "Este reporte fue generado automáticamente por el Sistema de Análisis Temporal. "
                "Los datos están sujetos a actualizaciones periódicas.",
                note_style
            )
            elements.append(note)
            
            # Construir PDF
            doc.build(elements)
            
            # Preparar respuesta
            buffer.seek(0)
            response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="analisis_temporal_requerimientos.pdf"'
            return response
            
        except ImportError:
            from django.http import HttpResponse
            return HttpResponse("Error: reportlab no está instalado. Ejecute 'pip install reportlab'", status=500)
        except Exception as e:
            from django.http import HttpResponse
            return HttpResponse(f"Error al generar PDF: {str(e)}", status=500)
