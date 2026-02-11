"""
Vistas mejoradas para la API REST con funcionalidades de captura mejorada.
"""

import logging
from django.utils import timezone
from django.http import JsonResponse
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from captura.tareas_mejoradas import (
    capturar_contenido_mejorado_task,
    reprocesar_capturas_incompletas,
    evaluar_calidad_capturas,
    capturar_url_manual_mejorada,
)
from captura.models import CapturaCruda
from semillas.models import FuenteWeb

logger = logging.getLogger(__name__)


class CapturaMejoradaAPIView(APIView):
    """
    Vista para operaciones de captura mejorada.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Ejecuta una captura mejorada para una fuente específica.
        
        Parámetros esperados en el body:
        - fuente_id: ID de la fuente a capturar (opcional si se proporciona url)
        - url: URL a capturar directamente (opcional si se proporciona fuente_id)
        - forzar_selenium: Si es True, fuerza el uso de Selenium (default: False)
        """
        fuente_id = request.data.get('fuente_id')
        url = request.data.get('url')
        forzar_selenium = request.data.get('forzar_selenium', False)
        
        if not fuente_id and not url:
            return Response(
                {'error': 'Se requiere fuente_id o url'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if fuente_id:
            # Capturar fuente existente
            try:
                fuente = FuenteWeb.objects.get(id=fuente_id)
            except FuenteWeb.DoesNotExist:
                return Response(
                    {'error': f'Fuente con ID {fuente_id} no encontrada'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            tarea = capturar_contenido_mejorado_task.delay(
                fuente_id=fuente_id,
                forzar_selenium=forzar_selenium
            )
            
            return Response({
                'estado': 'en_proceso',
                'mensaje': f'Captura mejorada iniciada para {fuente.nombre}',
                'task_id': tarea.id,
                'fuente_id': fuente_id,
                'fuente_nombre': fuente.nombre,
                'url': fuente.url,
            }, status=status.HTTP_202_ACCEPTED)
        
        else:
            # Capturar URL directamente
            tarea = capturar_url_manual_mejorada.delay(
                url=url,
                categoria=request.data.get('categoria', 'manual')
            )
            
            return Response({
                'estado': 'en_proceso',
                'mensaje': f'Captura manual mejorada iniciada para {url}',
                'task_id': tarea.id,
                'url': url,
            }, status=status.HTTP_202_ACCEPTED)
    
    def get(self, request):
        """
        Obtiene información sobre capturas mejoradas recientes.
        
        Parámetros de query:
        - limite: Número máximo de capturas a retornar (default: 10)
        - fuente_id: Filtrar por fuente específica
        - solo_mejoradas: Si es True, solo retorna capturas hechas con métodos mejorados
        """
        limite = int(request.query_params.get('limite', 10))
        fuente_id = request.query_params.get('fuente_id')
        solo_mejoradas = request.query_params.get('solo_mejoradas', 'false').lower() == 'true'
        
        queryset = CapturaCruda.objects.filter(
            estado_http='exito'
        ).order_by('-fecha_captura')
        
        if fuente_id:
            queryset = queryset.filter(fuente_id=fuente_id)
        
        if solo_mejoradas:
            queryset = queryset.filter(
                metadata_tecnica__has_key='metodo_captura'
            )
        
        capturas = queryset[:limite]
        
        resultados = []
        for captura in capturas:
            metadata = captura.metadata_tecnica or {}
            
            resultados.append({
                'id': captura.id,
                'fuente_id': captura.fuente_id,
                'fuente_nombre': captura.fuente.nombre,
                'url': captura.fuente.url,
                'fecha_captura': captura.fecha_captura,
                'tamaño_bytes': captura.tamaño_bytes,
                'metodo_captura': metadata.get('metodo_captura', 'desconocido'),
                'tiene_contenido_principal': bool(captura.texto_extraido),
                'calidad_analisis': metadata.get('analisis_calidad', {}),
            })
        
        return Response({
            'total': len(resultados),
            'capturas': resultados,
        })


class ReprocesamientoAPIView(APIView):
    """
    Vista para operaciones de reprocesamiento de capturas.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Reprocesa capturas que pueden estar incompletas.
        
        Parámetros esperados en el body:
        - limite: Número máximo de capturas a reprocesar (default: 10)
        - fuente_id: Reprocesar solo capturas de una fuente específica
        - forzar_todas: Si es True, reprocesa todas las capturas sin filtrar por calidad
        """
        limite = int(request.data.get('limite', 10))
        fuente_id = request.data.get('fuente_id')
        forzar_todas = request.data.get('forzar_todas', False)
        
        # Si se especifica fuente_id, limitar a esa fuente
        filtros = {}
        if fuente_id:
            filtros['fuente_id'] = fuente_id
        
        # Ejecutar tarea de reprocesamiento
        tarea = reprocesar_capturas_incompletas.delay(limite=limite)
        
        return Response({
            'estado': 'en_proceso',
            'mensaje': f'Reprocesamiento de hasta {limite} capturas iniciado',
            'task_id': tarea.id,
            'limite': limite,
            'filtros': filtros,
        }, status=status.HTTP_202_ACCEPTED)
    
    def get(self, request):
        """
        Obtiene estadísticas de reprocesamientos recientes.
        """
        # Esta sería una implementación futura que consultaría una tabla
        # de historial de reprocesamientos
        return Response({
            'estado': 'info',
            'mensaje': 'Funcionalidad de historial de reprocesamientos en desarrollo',
            'sugerencia': 'Use el endpoint POST para iniciar un reprocesamiento',
        })


class CalidadCapturasAPIView(APIView):
    """
    Vista para evaluar y consultar la calidad de las capturas.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Ejecuta una evaluación de calidad de capturas.
        
        Parámetros esperados en el body:
        - limite: Número máximo de capturas a evaluar (default: 50)
        - solo_baja_calidad: Si es True, solo evalúa capturas de baja calidad
        """
        limite = int(request.data.get('limite', 50))
        solo_baja_calidad = request.data.get('solo_baja_calidad', False)
        
        tarea = evaluar_calidad_capturas.delay(limite=limite)
        
        return Response({
            'estado': 'en_proceso',
            'mensaje': f'Evaluación de calidad de hasta {limite} capturas iniciada',
            'task_id': tarea.id,
            'limite': limite,
            'solo_baja_calidad': solo_baja_calidad,
        }, status=status.HTTP_202_ACCEPTED)
    
    def get(self, request):
        """
        Obtiene un resumen de la calidad de las capturas.
        
        Parámetros de query:
        - dias: Número de días a considerar (default: 7)
        - fuente_id: Filtrar por fuente específica
        """
        dias = int(request.query_params.get('dias', 7))
        fuente_id = request.query_params.get('fuente_id')
        
        fecha_limite = timezone.now() - timezone.timedelta(days=dias)
        
        queryset = CapturaCruda.objects.filter(
            fecha_captura__gte=fecha_limite,
            estado_http='exito',
            tipo_documento='html',
        )
        
        if fuente_id:
            queryset = queryset.filter(fuente_id=fuente_id)
        
        total_capturas = queryset.count()
        
        # Analizar calidad basada en tamaño y contenido
        capturas_pequenas = queryset.filter(
            tamaño_bytes__lt=5000  # Menos de 5KB
        ).count()
        
        capturas_sin_texto = queryset.filter(
            texto_extraido__isnull=True
        ).count()
        
        capturas_con_metodo_mejorado = queryset.filter(
            metadata_tecnica__has_key='metodo_captura'
        ).count()
        
        return Response({
            'periodo_dias': dias,
            'fecha_desde': fecha_limite,
            'total_capturas': total_capturas,
            'estadisticas_calidad': {
                'capturas_pequenas': capturas_pequenas,
                'capturas_sin_texto': capturas_sin_texto,
                'capturas_con_metodo_mejorado': capturas_con_metodo_mejorado,
                'porcentaje_pequenas': (capturas_pequenas / max(total_capturas, 1)) * 100,
                'porcentaje_sin_texto': (capturas_sin_texto / max(total_capturas, 1)) * 100,
                'porcentaje_mejoradas': (capturas_con_metodo_mejorado / max(total_capturas, 1)) * 100,
            },
            'recomendaciones': self._generar_recomendaciones(
                total_capturas, capturas_pequenas, capturas_sin_texto
            ),
        })
    
    def _generar_recomendaciones(self, total, pequenas, sin_texto):
        """Genera recomendaciones basadas en las estadísticas de calidad."""
        recomendaciones = []
        
        if total == 0:
            recomendaciones.append("No hay capturas recientes para analizar")
            return recomendaciones
        
        porcentaje_pequenas = (pequenas / total) * 100
        porcentaje_sin_texto = (sin_texto / total) * 100
        
        if porcentaje_pequenas > 30:
            recomendaciones.append(
                f"Alto porcentaje ({porcentaje_pequenas:.1f}%) de capturas pequeñas. "
                "Considere usar captura mejorada con Selenium."
            )
        
        if porcentaje_sin_texto > 20:
            recomendaciones.append(
                f"Alto porcentaje ({porcentaje_sin_texto:.1f}%) de capturas sin texto extraído. "
                "Revise el proceso de extracción de texto."
            )
        
        if porcentaje_pequenas < 10 and porcentaje_sin_texto < 10:
            recomendaciones.append("La calidad general de las capturas es buena.")
        
        return recomendaciones


class ComparacionCapturasAPIView(APIView):
    """
    Vista para comparar capturas de la misma fuente.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, fuente_id):
        """
        Compara las últimas capturas de una fuente.
        
        Args:
            fuente_id: ID de la fuente a comparar
        """
        try:
            fuente = FuenteWeb.objects.get(id=fuente_id)
        except FuenteWeb.DoesNotExist:
            return Response(
                {'error': f'Fuente con ID {fuente_id} no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Obtener las últimas 5 capturas exitosas
        capturas = CapturaCruda.objects.filter(
            fuente=fuente,
            estado_http='exito'
        ).order_by('-fecha_captura')[:5]
        
        if len(capturas) < 2:
            return Response({
                'estado': 'info',
                'mensaje': f'Se necesitan al menos 2 capturas para comparar. '
                          f'Esta fuente tiene {len(capturas)} capturas exitosas.',
                'fuente_id': fuente_id,
                'fuente_nombre': fuente.nombre,
            })
        
        resultados = []
        for i, captura in enumerate(capturas):
            metadata = captura.metadata_tecnica or {}
            
            resultados.append({
                'id': captura.id,
                'fecha_captura': captura.fecha_captura,
                'tamaño_bytes': captura.tamaño_bytes,
                'metodo_captura': metadata.get('metodo_captura', 'desconocido'),
                'tiene_texto': bool(captura.texto_extraido),
                'num_palabras': len(captura.texto_extraido.split()) if captura.texto_extraido else 0,
                'calidad': metadata.get('analisis_calidad', {}).get('calidad', 'desconocida'),
            })
        
        # Calcular diferencias
        diferencias = []
        for i in range(len(resultados) - 1):
            actual = resultados[i]
            anterior = resultados[i + 1]
            
            diff_tamaño = actual['tamaño_bytes'] - anterior['tamaño_bytes']
            diff_porcentaje = (diff_tamaño / max(anterior['tamaño_bytes'], 1)) * 100
            
            diferencias.append({
                'entre_capturas': f"{actual['id']} vs {anterior['id']}",
                'dias_diferencia': (capturas[i].fecha_captura - capturas[i + 1].fecha_captura).days,
                'diferencia_tamaño_bytes': diff_tamaño,
                'diferencia_porcentaje': diff_porcentaje,
                'cambio_metodo': actual['metodo_captura'] != anterior['metodo_captura'],
                'mejora_calidad': self._es_mejora_calidad(
                    actual.get('calidad'), anterior.get('calidad')
                ),
            })
        
        return Response({
            'fuente_id': fuente_id,
            'fuente_nombre': fuente.nombre,
            'total_capturas_comparadas': len(resultados),
            'capturas': resultados,
            'diferencias': diferencias,
            'resumen': self._generar_resumen_comparacion(diferencias),
        })
    
    def _es_mejora_calidad(self, calidad_actual, calidad_anterior):
        """Determina si hay una mejora en la calidad."""
        niveles = {'muy_baja': 0, 'baja': 1, 'media': 2, 'alta': 3, 'desconocida': -1}
        
        if calidad_actual not in niveles or calidad_anterior not in niveles:
            return None
        
        return niveles[calidad_actual] > niveles[calidad_anterior]
    
    def _generar_resumen_comparacion(self, diferencias):
        """Genera un resumen de la comparación."""
        if not diferencias:
            return "No hay diferencias para analizar"
        
        mejoras = sum(1 for d in diferencias if d.get('mejora_calidad') is True)
        cambios_metodo = sum(1 for d in diferencias if d.get('cambio_metodo'))
        
        resumen = f"Se analizaron {len(diferencias)} comparaciones. "
        
        if mejoras > 0:
            resumen += f"{mejoras} muestran mejora en calidad. "
        
        if cambios_metodo > 0:
            resumen += f"{cambios_metodo} cambios en método de captura. "
        
        # Analizar tendencia de tamaño
        cambios_tamaño = [d['diferencia_porcentaje'] for d in diferencias]
        promedio_cambio = sum(cambios_tamaño) / len(cambios_tamaño)
        
        if promedio_cambio > 10:
            resumen += "Tendencia general de aumento en tamaño de capturas. "
        elif promedio_cambio < -10:
            resumen += "Tendencia general de disminución en tamaño de capturas. "
        else:
            resumen += "Tamaño de capturas relativamente estable. "
        
        return resumen


# Vista para integración con la interfaz web existente
class CapturaManualMejoradaAPIView(APIView):
    """
    Vista para captura manual mejorada (compatible con la interfaz web existente).
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Endpoint para captura manual mejorada.
        
        Compatible con el endpoint existente /api/capturas/manual/
        """
        url = request.data.get('url')
        
        if not url:
            return Response(
                {'error': 'Se requiere el parámetro url'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        tarea = capturar_url_manual_mejorada.delay(url=url)
        
        return Response({
            'success': True,
            'message': 'Captura mejorada iniciada',
            'task_id': tarea.id,
            'url': url,
            'fuente_nueva': True,  # Siempre crea fuente temporal
        }, status=status.HTTP_202_ACCEPTED)