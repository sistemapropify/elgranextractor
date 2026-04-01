"""
Módulo para generar gráficos de calidad de datos usando Matplotlib/Seaborn.
Este módulo proporciona funciones para crear visualizaciones para el dashboard
de calidad de datos y detección de anomalías.
"""

import io
import base64
import logging
from typing import Dict, List, Tuple, Optional, Any
from django.db.models import Count, Q
from ingestas.models import PropiedadRaw
from propifai.models import PropifaiProperty

logger = logging.getLogger(__name__)

# Intentar importar matplotlib con manejo de errores
try:
    import matplotlib
    matplotlib.use('Agg')  # Usar backend no interactivo para servidor
    import matplotlib.pyplot as plt
    import seaborn as sns
    import numpy as np
    import pandas as pd
    
    # Configurar estilo de gráficos
    plt.style.use('seaborn-v0_8-darkgrid')
    sns.set_palette("husl")
    
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    logger.warning("Matplotlib no está instalado. Los gráficos no estarán disponibles.")
    MATPLOTLIB_AVAILABLE = False
    plt = None
    sns = None
    np = None
    pd = None

def create_completeness_chart(data_source: str = 'local') -> str:
    """
    Crea un gráfico de barras mostrando la completitud de campos clave.
    
    Args:
        data_source: 'local' para PropiedadRaw, 'propifai' para PropifaiProperty
        
    Returns:
        Base64 encoded PNG image o mensaje de error
    """
    if not MATPLOTLIB_AVAILABLE:
        return _create_no_matplotlib_chart()
    
    try:
        if data_source == 'local':
            model = PropiedadRaw
            using_db = 'default'
            fields_to_check = [
                ('precio_usd', 'Precio'),
                ('coordenadas', 'Coordenadas'),
                ('area_construida', 'Área construida'),
                ('area_terreno', 'Área terreno'),
                ('numero_habitaciones', 'Habitaciones'),
                ('numero_banos', 'Baños'),
                ('departamento', 'Departamento'),
                ('distrito', 'Distrito'),
            ]
        else:
            model = PropifaiProperty
            using_db = 'propifai'
            fields_to_check = [
                ('price', 'Precio'),
                ('coordinates', 'Coordenadas'),
                ('built_area', 'Área construida'),
                ('lot_area', 'Área terreno'),
                ('bedrooms', 'Habitaciones'),
                ('bathrooms', 'Baños'),
                ('department', 'Departamento'),
                ('district', 'Distrito'),
            ]
        
        total_count = model.objects.using(using_db).count()
        if total_count == 0:
            return _create_empty_chart("Sin datos disponibles")
        
        completeness_data = []
        labels = []
        
        for field_name, display_name in fields_to_check:
            try:
                # Contar registros donde el campo no es nulo ni vacío
                if hasattr(model, field_name):
                    non_null_count = model.objects.using(using_db).filter(
                        **{f"{field_name}__isnull": False}
                    ).exclude(**{field_name: ''}).count()
                    
                    percentage = (non_null_count / total_count * 100) if total_count > 0 else 0
                    completeness_data.append(percentage)
                    labels.append(display_name)
            except Exception as e:
                logger.warning(f"Error al verificar campo {field_name}: {e}")
                continue
        
        if not completeness_data:
            return _create_empty_chart("No se pudieron calcular métricas")
        
        # Crear gráfico
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Colores basados en porcentaje
        colors = ['#2ecc71' if p >= 80 else '#f39c12' if p >= 50 else '#e74c3c' for p in completeness_data]
        
        bars = ax.barh(labels, completeness_data, color=colors, edgecolor='black', linewidth=0.5)
        ax.set_xlabel('Porcentaje de completitud (%)', fontsize=12)
        ax.set_title(f'Completitud de campos - {data_source.capitalize()}', fontsize=14, fontweight='bold')
        ax.set_xlim(0, 100)
        
        # Añadir etiquetas de valor
        for bar, value in zip(bars, completeness_data):
            width = bar.get_width()
            ax.text(width + 1, bar.get_y() + bar.get_height()/2,
                   f'{value:.1f}%', va='center', fontsize=10)
        
        # Añadir líneas de referencia
        ax.axvline(x=80, color='green', linestyle='--', alpha=0.3, label='Objetivo (80%)')
        ax.axvline(x=50, color='orange', linestyle='--', alpha=0.3, label='Mínimo (50%)')
        
        ax.legend(loc='lower right')
        plt.tight_layout()
        
        return _fig_to_base64(fig)
        
    except Exception as e:
        logger.error(f"Error en create_completeness_chart: {e}")
        return _create_error_chart(str(e))

def create_outliers_chart(data_source: str = 'local') -> str:
    """
    Crea un gráfico de caja (boxplot) para detectar valores atípicos en precios y áreas.
    
    Args:
        data_source: 'local' o 'propifai'
        
    Returns:
        Base64 encoded PNG image
    """
    try:
        if data_source == 'local':
            model = PropiedadRaw
            using_db = 'default'
            price_field = 'precio_usd'
            area_field = 'area_construida'
        else:
            model = PropifaiProperty
            using_db = 'propifai'
            price_field = 'price'
            area_field = 'built_area'
        
        # Obtener datos para análisis
        price_data = list(model.objects.using(using_db).filter(
            **{f"{price_field}__isnull": False}
        ).exclude(**{price_field: 0}).values_list(price_field, flat=True)[:1000])
        
        area_data = list(model.objects.using(using_db).filter(
            **{f"{area_field}__isnull": False}
        ).exclude(**{area_field: 0}).values_list(area_field, flat=True)[:1000])
        
        if not price_data and not area_data:
            return _create_empty_chart("Sin datos numéricos para análisis")
        
        # Crear gráfico con subplots
        fig, axes = plt.subplots(1, 2, figsize=(12, 6))
        
        # Gráfico de precios
        if price_data:
            ax1 = axes[0]
            bp1 = ax1.boxplot(price_data, vert=True, patch_artist=True)
            bp1['boxes'][0].set_facecolor('#3498db')
            bp1['medians'][0].set_color('red')
            ax1.set_title('Distribución de Precios', fontsize=12, fontweight='bold')
            ax1.set_ylabel('Precio (USD)', fontsize=10)
            
            # Calcular y mostrar outliers
            q1 = np.percentile(price_data, 25)
            q3 = np.percentile(price_data, 75)
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            outliers = [x for x in price_data if x < lower_bound or x > upper_bound]
            
            ax1.text(0.95, 0.95, f'Outliers: {len(outliers)}',
                    transform=ax1.transAxes, fontsize=10,
                    verticalalignment='top', horizontalalignment='right',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
        
        # Gráfico de áreas
        if area_data:
            ax2 = axes[1]
            bp2 = ax2.boxplot(area_data, vert=True, patch_artist=True)
            bp2['boxes'][0].set_facecolor('#2ecc71')
            bp2['medians'][0].set_color('red')
            ax2.set_title('Distribución de Áreas', fontsize=12, fontweight='bold')
            ax2.set_ylabel('Área (m²)', fontsize=10)
            
            # Calcular y mostrar outliers
            q1 = np.percentile(area_data, 25)
            q3 = np.percentile(area_data, 75)
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            outliers = [x for x in area_data if x < lower_bound or x > upper_bound]
            
            ax2.text(0.95, 0.95, f'Outliers: {len(outliers)}',
                    transform=ax2.transAxes, fontsize=10,
                    verticalalignment='top', horizontalalignment='right',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
        
        fig.suptitle(f'Detección de Valores Atípicos - {data_source.capitalize()}', 
                    fontsize=14, fontweight='bold')
        plt.tight_layout()
        
        return _fig_to_base64(fig)
        
    except Exception as e:
        logger.error(f"Error en create_outliers_chart: {e}")
        return _create_error_chart(str(e))

def create_duplicates_chart(data_source: str = 'local') -> str:
    """
    Crea un gráfico de barras mostrando posibles duplicados basados en campos clave.
    
    Args:
        data_source: 'local' o 'propifai'
        
    Returns:
        Base64 encoded PNG image
    """
    try:
        if data_source == 'local':
            model = PropiedadRaw
            using_db = 'default'
            duplicate_fields = [
                ('coordenadas', 'Misma coordenada'),
                ('url_propiedad', 'Misma URL'),
                ('descripcion', 'Descripción similar'),
            ]
        else:
            model = PropifaiProperty
            using_db = 'propifai'
            duplicate_fields = [
                ('coordinates', 'Misma coordenada'),
                ('property_url', 'Misma URL'),
                ('description', 'Descripción similar'),
            ]
        
        duplicate_counts = []
        labels = []
        
        for field_name, label in duplicate_fields:
            try:
                if hasattr(model, field_name):
                    # Contar valores que aparecen más de una vez
                    duplicates = model.objects.using(using_db).filter(
                        **{f"{field_name}__isnull": False}
                    ).exclude(**{field_name: ''}).values(field_name).annotate(
                        count=Count(field_name)
                    ).filter(count__gt=1).count()
                    
                    duplicate_counts.append(duplicates)
                    labels.append(label)
            except Exception as e:
                logger.warning(f"Error al verificar duplicados en {field_name}: {e}")
                continue
        
        if not duplicate_counts:
            return _create_empty_chart("No se detectaron posibles duplicados")
        
        # Crear gráfico
        fig, ax = plt.subplots(figsize=(10, 6))
        
        colors = ['#e74c3c' if count > 10 else '#f39c12' if count > 5 else '#2ecc71' 
                 for count in duplicate_counts]
        
        bars = ax.bar(labels, duplicate_counts, color=colors, edgecolor='black', linewidth=0.5)
        ax.set_ylabel('Número de posibles duplicados', fontsize=12)
        ax.set_title(f'Detección de Posibles Duplicados - {data_source.capitalize()}', 
                    fontsize=14, fontweight='bold')
        
        # Añadir etiquetas de valor
        for bar, value in zip(bars, duplicate_counts):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                   f'{value}', ha='center', va='bottom', fontsize=10)
        
        # Añadir línea de umbral
        ax.axhline(y=5, color='orange', linestyle='--', alpha=0.5, label='Umbral de alerta (5)')
        ax.axhline(y=10, color='red', linestyle='--', alpha=0.5, label='Umbral crítico (10)')
        
        ax.legend(loc='upper right')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        
        return _fig_to_base64(fig)
        
    except Exception as e:
        logger.error(f"Error en create_duplicates_chart: {e}")
        return _create_error_chart(str(e))

def create_empty_fields_chart(data_source: str = 'local') -> str:
    """
    Crea un gráfico de torta mostrando la proporción de campos vacíos vs completos.
    
    Args:
        data_source: 'local' o 'propifai'
        
    Returns:
        Base64 encoded PNG image
    """
    try:
        if data_source == 'local':
            model = PropiedadRaw
            using_db = 'default'
            critical_fields = ['precio_usd', 'coordenadas', 'area_construida', 'departamento']
        else:
            model = PropifaiProperty
            using_db = 'propifai'
            critical_fields = ['price', 'coordinates', 'built_area', 'department']
        
        total_records = model.objects.using(using_db).count()
        if total_records == 0:
            return _create_empty_chart("Sin datos disponibles")
        
        # Analizar cada campo crítico
        empty_counts = []
        field_labels = []
        
        for field in critical_fields:
            try:
                if hasattr(model, field):
                    empty_count = model.objects.using(using_db).filter(
                        Q(**{f"{field}__isnull": True}) | Q(**{field: ''})
                    ).count()
                    
                    empty_percentage = (empty_count / total_records * 100) if total_records > 0 else 0
                    empty_counts.append(empty_percentage)
                    field_labels.append(field.replace('_', ' ').title())
            except Exception as e:
                logger.warning(f"Error al analizar campo {field}: {e}")
                continue
        
        if not empty_counts:
            return _create_empty_chart("No se pudieron analizar campos críticos")
        
        # Crear gráfico de barras apiladas
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Datos para barras apiladas
        complete_counts = [100 - empty for empty in empty_counts]
        
        bar_width = 0.6
        indices = np.arange(len(field_labels))
        
        bar1 = ax.bar(indices, complete_counts, bar_width, label='Completos', color='#2ecc71')
        bar2 = ax.bar(indices, empty_counts, bar_width, bottom=complete_counts, 
                     label='Vacíos/Nulos', color='#e74c3c')
        
        ax.set_xlabel('Campos críticos', fontsize=12)
        ax.set_ylabel('Porcentaje (%)', fontsize=12)
        ax.set_title(f'Proporción de Campos Vacíos - {data_source.capitalize()}', 
                    fontsize=14, fontweight='bold')
        ax.set_xticks(indices)
        ax.set_xticklabels(field_labels, rotation=45, ha='right')
        ax.set_ylim(0, 100)
        
        # Añadir etiquetas de valor
        for i, (complete, empty) in enumerate(zip(complete_counts, empty_counts)):
            ax.text(i, complete/2, f'{complete:.1f}%', ha='center', va='center', 
                   color='white', fontweight='bold', fontsize=9)
            if empty > 5:  # Solo mostrar si hay suficiente espacio
                ax.text(i, complete + empty/2, f'{empty:.1f}%', ha='center', va='center', 
                       color='white', fontweight='bold', fontsize=9)
        
        ax.legend(loc='upper right')
        plt.tight_layout()
        
        return _fig_to_base64(fig)
        
    except Exception as e:
        logger.error(f"Error en create_empty_fields_chart: {e}")
        return _create_error_chart(str(e))

def create_data_quality_summary() -> Dict[str, str]:
    """
    Crea todas las visualizaciones principales y las retorna como diccionario.
    
    Returns:
        Diccionario con todas las imágenes en base64
    """
    charts = {
        'local_completeness': create_completeness_chart('local'),
        'propifai_completeness': create_completeness_chart('propifai'),
        'local_outliers': create_outliers_chart('local'),
        'propifai_outliers': create_outliers_chart('propifai'),
        'local_duplicates': create_duplicates_chart('local'),
        'propifai_duplicates': create_duplicates_chart('propifai'),
        'local_empty_fields': create_empty_fields_chart('local'),
        'propifai_empty_fields': create_empty_fields_chart('propifai'),
    }
    
    # Agregar información sobre el estado de matplotlib
    charts['matplotlib_available'] = MATPLOTLIB_AVAILABLE
    charts['matplotlib_status'] = 'Disponible' if MATPLOTLIB_AVAILABLE else 'No disponible - usando gráficos SVG'
    
    return charts

def calculate_data_quality_metrics() -> Dict[str, Any]:
    """
    Calcula métricas de calidad de datos para ambos orígenes.
    
    Returns:
        Diccionario con métricas detalladas
    """
    metrics = {
        'local': _calculate_source_metrics('local'),
        'propifai': _calculate_source_metrics('propifai'),
        'overall': {}
    }
    
    # Calcular métricas generales
    local_metrics = metrics['local']
    propifai_metrics = metrics['propifai']
    
    if local_metrics['total_records'] > 0 or propifai_metrics['total_records'] > 0:
        total_records = local_metrics['total_records'] + propifai_metrics['total_records']
        
        # Calcular promedios ponderados
        metrics['overall'] = {
            'total_records': total_records,
            'avg_completeness': (
                local_metrics['avg_completeness'] * local_metrics['total_records'] +
                propifai_metrics['avg_completeness'] * propifai_metrics['total_records']
            ) / total_records if total_records > 0 else 0,
            'data_quality_score': (
                local_metrics['data_quality_score'] * local_metrics['total_records'] +
                propifai_metrics['data_quality_score'] * propifai_metrics['total_records']
            ) / total_records if total_records > 0 else 0,
            'critical_issues': local_metrics['critical_issues'] + propifai_metrics['critical_issues'],
            'warning_issues': local_metrics['warning_issues'] + propifai_metrics['warning_issues'],
        }
    
    return metrics


def get_problematic_examples(data_source: str = 'local', limit: int = 5) -> Dict[str, Any]:
    """
    Obtiene ejemplos concretos de registros con problemas de calidad.
    
    Args:
        data_source: 'local' o 'propifai'
        limit: Número máximo de ejemplos por tipo de problema
        
    Returns:
        Diccionario con ejemplos de problemas
    """
    examples = {
        'missing_coordinates': [],
        'missing_price': [],
        'missing_area': [],
        'zero_price': [],
        'zero_area': [],
        'duplicate_candidates': []
    }
    
    try:
        if data_source == 'local':
            from ingestas.models import PropiedadRaw
            
            # Verificar si hay datos en la base local
            total_local = PropiedadRaw.objects.using('default').count()
            logger.info(f"[DEBUG] Total registros en base local: {total_local}")
            
            # Registros sin coordenadas - usar campo 'coordenadas' no 'coordinates'
            missing_coords = PropiedadRaw.objects.using('default').filter(
                Q(coordenadas__isnull=True) | Q(coordenadas='')
            )
            examples['missing_coordinates'] = list(missing_coords.values(
                'id', 'descripcion', 'precio_usd', 'area_construida', 'coordenadas', 'url_propiedad'
            )[:limit])
            logger.info(f"[DEBUG] Base local - sin coordenadas: {len(examples['missing_coordinates'])}")
            
            # Registros sin precio
            missing_price = PropiedadRaw.objects.using('default').filter(precio_usd__isnull=True)
            examples['missing_price'] = list(missing_price.values(
                'id', 'descripcion', 'precio_usd', 'area_construida', 'url_propiedad'
            )[:limit])
            logger.info(f"[DEBUG] Base local - sin precio: {len(examples['missing_price'])}")
            
            # Registros sin área
            missing_area = PropiedadRaw.objects.using('default').filter(area_construida__isnull=True)
            examples['missing_area'] = list(missing_area.values(
                'id', 'descripcion', 'precio_usd', 'area_construida', 'url_propiedad'
            )[:limit])
            logger.info(f"[DEBUG] Base local - sin área: {len(examples['missing_area'])}")
            
            # Registros con precio 0
            zero_price = PropiedadRaw.objects.using('default').filter(precio_usd=0)
            examples['zero_price'] = list(zero_price.values(
                'id', 'descripcion', 'precio_usd', 'area_construida', 'url_propiedad'
            )[:limit])
            logger.info(f"[DEBUG] Base local - precio cero: {len(examples['zero_price'])}")
            
            # Registros con área 0
            zero_area = PropiedadRaw.objects.using('default').filter(area_construida=0)
            examples['zero_area'] = list(zero_area.values(
                'id', 'descripcion', 'precio_usd', 'area_construida', 'url_propiedad'
            )[:limit])
            logger.info(f"[DEBUG] Base local - área cero: {len(examples['zero_area'])}")
                
        elif data_source == 'propifai':
            from propifai.models import PropifaiProperty
            
            # Verificar si hay datos en Propifai
            total_propifai = PropifaiProperty.objects.using('propifai').count()
            logger.info(f"[DEBUG] Total registros en Propifai: {total_propifai}")
            
            # Registros sin coordenadas
            missing_coords = PropifaiProperty.objects.using('propifai').filter(
                Q(coordinates__isnull=True) | Q(coordinates='')
            )
            examples['missing_coordinates'] = list(missing_coords.values(
                'id', 'title', 'price', 'built_area', 'coordinates', 'code'
            )[:limit])
            logger.info(f"[DEBUG] Propifai - sin coordenadas: {len(examples['missing_coordinates'])}")
            
            # Registros sin precio
            missing_price = PropifaiProperty.objects.using('propifai').filter(price__isnull=True)
            examples['missing_price'] = list(missing_price.values(
                'id', 'title', 'price', 'built_area', 'code'
            )[:limit])
            logger.info(f"[DEBUG] Propifai - sin precio: {len(examples['missing_price'])}")
            
            # Registros sin área
            missing_area = PropifaiProperty.objects.using('propifai').filter(built_area__isnull=True)
            examples['missing_area'] = list(missing_area.values(
                'id', 'title', 'price', 'built_area', 'code'
            )[:limit])
            logger.info(f"[DEBUG] Propifai - sin área: {len(examples['missing_area'])}")
            
            # Registros con precio 0
            zero_price = PropifaiProperty.objects.using('propifai').filter(price=0)
            examples['zero_price'] = list(zero_price.values(
                'id', 'title', 'price', 'built_area', 'code'
            )[:limit])
            logger.info(f"[DEBUG] Propifai - precio cero: {len(examples['zero_price'])}")
            
            # Registros con área 0
            zero_area = PropifaiProperty.objects.using('propifai').filter(built_area=0)
            examples['zero_area'] = list(zero_area.values(
                'id', 'title', 'price', 'built_area', 'code'
            )[:limit])
            logger.info(f"[DEBUG] Propifai - área cero: {len(examples['zero_area'])}")
                
    except Exception as e:
        logger.error(f"Error al obtener ejemplos problemáticos para {data_source}: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    return examples

def _calculate_source_metrics(data_source: str) -> Dict[str, Any]:
    """
    Calcula métricas detalladas para una fuente de datos específica.
    
    Args:
        data_source: 'local' o 'propifai'
        
    Returns:
        Diccionario con métricas
    """
    try:
        if data_source == 'local':
            model = PropiedadRaw
            using_db = 'default'
            critical_fields = ['precio_usd', 'coordenadas', 'area_construida', 'departamento']
        else:
            model = PropifaiProperty
            using_db = 'propifai'
            critical_fields = ['price', 'coordinates', 'built_area', 'department']
        
        total_records = model.objects.using(using_db).count()
        
        if total_records == 0:
            return {
                'total_records': 0,
                'avg_completeness': 0,
                'data_quality_score': 0,
                'critical_issues': 0,
                'warning_issues': 0,
                'completeness_by_field': {},
                'field_stats': {}
            }
        
        # Calcular completitud por campo
        completeness_by_field = {}
        for field in critical_fields:
            try:
                if hasattr(model, field):
                    non_null_count = model.objects.using(using_db).filter(
                        Q(**{f"{field}__isnull": False}) & ~Q(**{field: ''})
                    ).count()
                    completeness = (non_null_count / total_records * 100) if total_records > 0 else 0
                    completeness_by_field[field] = completeness
            except Exception:
                completeness_by_field[field] = 0
        
        # Calcular promedio de completitud
        avg_completeness = sum(completeness_by_field.values()) / len(completeness_by_field) if completeness_by_field else 0
        
        # Detectar posibles duplicados (simplificado)
        duplicate_count = 0
        for field in ['coordenadas', 'coordinates']:
            if hasattr(model, field):
                try:
                    duplicates = model.objects.using(using_db).filter(
                        **{f"{field}__isnull": False}
                    ).exclude(**{field: ''}).values(field).annotate(
                        count=Count(field)
                    ).filter(count__gt=1).count()
                    duplicate_count += duplicates
                except Exception:
                    pass
        
        # Calcular puntaje de calidad (0-100)
        data_quality_score = avg_completeness * 0.7  # 70% por completitud
        
        # Penalizar por duplicados
        duplicate_penalty = min(duplicate_count * 2, 30)  # Máximo 30% de penalización
        data_quality_score -= duplicate_penalty
        
        # Asegurar que el puntaje esté entre 0 y 100
        data_quality_score = max(0, min(100, data_quality_score))
        
        # Clasificar problemas
        critical_issues = 0
        warning_issues = 0
        
        if avg_completeness < 50:
            critical_issues += 1
        elif avg_completeness < 70:
            warning_issues += 1
        
        if duplicate_count > 10:
            critical_issues += 1
        elif duplicate_count > 5:
            warning_issues += 1
        
        return {
            'total_records': total_records,
            'avg_completeness': avg_completeness,
            'data_quality_score': data_quality_score,
            'critical_issues': critical_issues,
            'warning_issues': warning_issues,
            'duplicate_count': duplicate_count,
            'completeness_by_field': completeness_by_field,
        }
        
    except Exception as e:
        logger.error(f"Error en _calculate_source_metrics para {data_source}: {e}")
        return {
            'total_records': 0,
            'avg_completeness': 0,
            'data_quality_score': 0,
            'critical_issues': 1,
            'warning_issues': 0,
            'completeness_by_field': {},
        }

def _fig_to_base64(fig) -> str:
    """
    Convierte una figura de matplotlib a base64.
    
    Args:
        fig: Figura de matplotlib
        
    Returns:
        String base64
    """
    if not MATPLOTLIB_AVAILABLE or fig is None:
        return _create_no_matplotlib_chart()
    
    try:
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        return f"data:image/png;base64,{img_base64}"
    except Exception as e:
        logger.error(f"Error al convertir figura a base64: {e}")
        return _create_error_chart(str(e))

def _create_empty_chart(message: str) -> str:
    """
    Crea un gráfico vacío con un mensaje.
    
    Args:
        message: Mensaje a mostrar
        
    Returns:
        Base64 encoded PNG image
    """
    if not MATPLOTLIB_AVAILABLE:
        return _create_no_matplotlib_chart()
    
    try:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, message, ha='center', va='center', fontsize=14,
                transform=ax.transAxes, color='gray')
        ax.set_axis_off()
        plt.tight_layout()
        return _fig_to_base64(fig)
    except Exception as e:
        logger.error(f"Error en _create_empty_chart: {e}")
        return _create_no_matplotlib_chart()

def _create_error_chart(error_message: str) -> str:
    """
    Crea un gráfico de error.
    
    Args:
        error_message: Mensaje de error
        
    Returns:
        Base64 encoded PNG image
    """
    if not MATPLOTLIB_AVAILABLE:
        return _create_no_matplotlib_chart()
    
    try:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.6, 'Error al generar gráfico', ha='center', va='center',
                fontsize=14, fontweight='bold', transform=ax.transAxes, color='red')
        ax.text(0.5, 0.4, error_message[:100], ha='center', va='center',
                fontsize=10, transform=ax.transAxes, color='gray')
        ax.set_axis_off()
        plt.tight_layout()
        return _fig_to_base64(fig)
    except Exception as e:
        logger.error(f"Error en _create_error_chart: {e}")
        return _create_no_matplotlib_chart()

def _create_no_matplotlib_chart() -> str:
    """
    Crea un gráfico de reemplazo cuando matplotlib no está disponible.
    
    Returns:
        Base64 encoded SVG image simple
    """
    # SVG más detallado con gráfico de ejemplo y mensaje
    svg_content = '''<svg width="400" height="300" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <linearGradient id="grad1" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style="stop-color:#4a90e2;stop-opacity:1" />
                <stop offset="100%" style="stop-color:#2ecc71;stop-opacity:1" />
            </linearGradient>
        </defs>
        <rect width="400" height="300" fill="#f8f9fa" rx="8" ry="8"/>
        
        <!-- Título -->
        <text x="200" y="40" font-family="Arial, sans-serif" font-size="16" font-weight="bold" fill="#2c3e50" text-anchor="middle">
            Gráfico de Ejemplo (Matplotlib no instalado)
        </text>
        
        <!-- Gráfico de barras simple -->
        <rect x="80" y="80" width="40" height="150" fill="url(#grad1)" opacity="0.8"/>
        <rect x="140" y="100" width="40" height="130" fill="url(#grad1)" opacity="0.8"/>
        <rect x="200" y="120" width="40" height="110" fill="url(#grad1)" opacity="0.8"/>
        <rect x="260" y="140" width="40" height="90" fill="url(#grad1)" opacity="0.8"/>
        
        <!-- Etiquetas de barras -->
        <text x="100" y="240" font-family="Arial" font-size="12" fill="#34495e" text-anchor="middle">Local</text>
        <text x="160" y="240" font-family="Arial" font-size="12" fill="#34495e" text-anchor="middle">Propify</text>
        <text x="220" y="240" font-family="Arial" font-size="12" fill="#34495e" text-anchor="middle">Mixto</text>
        <text x="280" y="240" font-family="Arial" font-size="12" fill="#34495e" text-anchor="middle">Otros</text>
        
        <!-- Mensaje informativo -->
        <rect x="50" y="260" width="300" height="30" fill="#e3f2fd" rx="4" ry="4"/>
        <text x="200" y="280" font-family="Arial" font-size="11" fill="#1976d2" text-anchor="middle">
            Instala: pip install matplotlib seaborn
        </text>
        
        <!-- Leyenda -->
        <circle cx="60" cy="210" r="6" fill="#4a90e2"/>
        <text x="75" y="215" font-family="Arial" font-size="11" fill="#2c3e50">Datos de calidad</text>
    </svg>'''
    import base64
    svg_base64 = base64.b64encode(svg_content.encode('utf-8')).decode('utf-8')
    return f"data:image/svg+xml;base64,{svg_base64}"