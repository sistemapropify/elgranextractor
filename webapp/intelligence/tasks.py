"""
Tareas Celery para el sistema RAG (Retrieval Augmented Generation).

Este módulo define tareas asíncronas para:
- Sincronización automática de colecciones
- Generación de embeddings en lote
- Mantenimiento del sistema RAG
"""

import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

from .services.rag import RAGService
from .models import IntelligenceCollection, IntelligenceDocument

logger = logging.getLogger(__name__)


@shared_task(bind=True, queue='analisis', name='intelligence.tasks.sincronizar_coleccion_rag')
def sincronizar_coleccion_rag(self, collection_id: int, force_full_sync: bool = False):
    """
    Tarea Celery para sincronizar una colección RAG.
    
    Args:
        collection_id: ID de la colección a sincronizar
        force_full_sync: Si True, regenera todos los embeddings
    
    Returns:
        Dict con resultados de la sincronización
    """
    logger.info(f"Iniciando sincronización RAG para colección {collection_id} (force={force_full_sync})")
    
    try:
        success, message, stats = RAGService.sync_collection(
            collection_id=collection_id,
            force_full_sync=force_full_sync
        )
        
        result = {
            'success': success,
            'message': message,
            'stats': stats,
            'collection_id': collection_id,
            'timestamp': timezone.now().isoformat(),
            'task_id': self.request.id
        }
        
        if success:
            logger.info(f"Sincronización RAG completada para colección {collection_id}: {stats}")
        else:
            logger.error(f"Sincronización RAG falló para colección {collection_id}: {message}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error en tarea sincronizar_coleccion_rag para colección {collection_id}: {e}")
        return {
            'success': False,
            'message': str(e),
            'stats': {'errors': 1},
            'collection_id': collection_id,
            'timestamp': timezone.now().isoformat(),
            'task_id': self.request.id
        }


@shared_task(bind=True, queue='analisis', name='intelligence.tasks.sincronizar_todas_colecciones_rag')
def sincronizar_todas_colecciones_rag(self, force_full_sync: bool = False,
                                      _task_id: str = None, _task_store: dict = None,
                                      _task_lock=None):
    """
    Tarea Celery para sincronizar todas las colecciones RAG activas.
    
    Args:
        force_full_sync: Si True, regenera todos los embeddings
        _task_id: Usado internamente para modo thread (sin Celery)
        _task_store: Usado internamente para modo thread
        _task_lock: Usado internamente para modo thread
    
    Returns:
        Dict con resultados de todas las sincronizaciones
    """
    # Detectar modo de ejecución
    es_sync = _task_id is not None
    if not es_sync:
        es_sync = not hasattr(self, 'request') or not self.request or not self.request.id
    
    if es_sync:
        import logging
        logging.getLogger(__name__).info(
            f"Ejecutando en modo thread (task_id={_task_id or 'sync'})"
        )
    logger.info(f"Iniciando sincronización de todas las colecciones RAG (force={force_full_sync})")
    
    # Obtener todas las colecciones activas
    collections = IntelligenceCollection.objects.filter(is_active=True)
    total_collections = collections.count()
    
    if total_collections == 0:
        logger.warning("No hay colecciones activas para sincronizar")
        return {
            'success': True,
            'message': 'No hay colecciones activas',
            'total_collections': 0,
            'results': [],
            'timestamp': timezone.now().isoformat()
        }
    
    logger.info(f"Encontradas {total_collections} colección(es) activa(s)")
    
    from .services.rag import RAGService
    from .services.faiss_index import FAISSIndexManager
    
    results = []
    logs = []
    success_count = 0
    error_count = 0
    faiss_count = 0
    
    # Registrar inicio
    logs.append({
        'level': 'info',
        'message': f'Iniciando sincronización de {total_collections} colecciones (force={force_full_sync})',
        'timestamp': timezone.now().isoformat(),
    })
    
    # Sincronizar cada colección y reconstruir FAISS
    for idx, collection in enumerate(collections, 1):
        try:
            logs.append({
                'level': 'info',
                'message': f'[{idx}/{total_collections}] Sincronizando {collection.name}...',
                'timestamp': timezone.now().isoformat(),
            })
            
            # Sync individual síncrona (no lanza sub-tarea)
            if collection.table_name:
                success, message, stats = RAGService.sync_collection_dynamic(
                    collection_name=collection.name,
                    force_full_sync=force_full_sync,
                )
            else:
                success, message, stats = RAGService.sync_collection(
                    collection_id=collection.id,
                    force_full_sync=force_full_sync,
                )
            
            if success:
                logs.append({
                    'level': 'success',
                    'message': f'  ✓ Sync OK: {stats.get("created",0)} creados, {stats.get("updated",0)} actualizados',
                    'timestamp': timezone.now().isoformat(),
                })
            else:
                logs.append({
                    'level': 'error',
                    'message': f'  ✗ Sync falló: {message}',
                    'timestamp': timezone.now().isoformat(),
                })
            
            # Reconstruir FAISS después del sync
            faiss_ok = False
            try:
                logs.append({
                    'level': 'info',
                    'message': f'  Reconstruyendo índice FAISS...',
                    'timestamp': timezone.now().isoformat(),
                })
                indexed = FAISSIndexManager.rebuild_for_collection(
                    collection.name,
                    RAGService.EMBEDDING_DIMENSIONS
                )
                faiss_ok = indexed > 0
                if faiss_ok:
                    faiss_count += 1
                    message_combined = message + f' | FAISS: {indexed} vectores'
                    logs.append({
                        'level': 'success',
                        'message': f'  ✓ FAISS: {indexed} vectores indexados',
                        'timestamp': timezone.now().isoformat(),
                    })
                else:
                    message_combined = message + f' | FAISS: 0 vectores'
                    logs.append({
                        'level': 'warn',
                        'message': f'  ⚠ FAISS: 0 vectores (sin datos para indexar)',
                        'timestamp': timezone.now().isoformat(),
                    })
            except Exception as fe:
                message_combined = message + f' | FAISS error: {fe}'
                logs.append({
                    'level': 'error',
                    'message': f'  ✗ FAISS error: {fe}',
                    'timestamp': timezone.now().isoformat(),
                })
            
            results.append({
                'collection_id': str(collection.id),
                'collection_name': collection.name,
                'success': success,
                'message': message_combined,
                'stats': stats,
                'faiss_rebuilt': faiss_ok,
            })
            
            if success:
                success_count += 1
            else:
                error_count += 1
                
            # Publicar progreso (Celery o Thread)
            progress_meta = {
                'current': success_count + error_count,
                'total': total_collections,
                'current_collection': collection.name,
                'success': success_count,
                'errors': error_count,
                'faiss': faiss_count,
                'logs': logs,
                'pct': int((success_count + error_count) / total_collections * 100),
            }
            if _task_id and _task_store and _task_lock:
                with _task_lock:
                    if _task_id in _task_store:
                        _task_store[_task_id]['state'] = 'PROGRESS'
                        _task_store[_task_id]['meta'] = progress_meta
            if not es_sync:
                self.update_state(state='PROGRESS', meta=progress_meta)
                
        except Exception as e:
            logger.error(f"Error sincronizando colección {collection.id} ({collection.name}): {e}")
            logs.append({
                'level': 'error',
                'message': f'  ✗ Error inesperado: {e}',
                'timestamp': timezone.now().isoformat(),
            })
            results.append({
                'collection_id': str(collection.id),
                'collection_name': collection.name,
                'success': False,
                'message': str(e),
                'stats': {'errors': 1},
                'faiss_rebuilt': False,
            })
            error_count += 1
            
            progress_meta = {
                'current': success_count + error_count,
                'total': total_collections,
                'current_collection': collection.name,
                'success': success_count,
                'errors': error_count,
                'faiss': faiss_count,
                'logs': logs,
                'pct': int((success_count + error_count) / total_collections * 100),
            }
            if _task_id and _task_store and _task_lock:
                with _task_lock:
                    if _task_id in _task_store:
                        _task_store[_task_id]['state'] = 'PROGRESS'
                        _task_store[_task_id]['meta'] = progress_meta
            if not es_sync:
                self.update_state(state='PROGRESS', meta=progress_meta)
    
    # Log final
    resumen_msg = f'Sincronizadas {success_count}/{total_collections} colecciones, {faiss_count} FAISS reconstruidos, {error_count} errores.'
    logs.append({
        'level': 'success' if error_count == 0 else 'warn',
        'message': resumen_msg,
        'timestamp': timezone.now().isoformat(),
    })
    
    # Resumen
    summary = {
        'success': error_count == 0,
        'message': resumen_msg,
        'total_collections': total_collections,
        'success_count': success_count,
        'error_count': error_count,
        'faiss_count': faiss_count,
        'results': results,
        'logs': logs,
        'timestamp': timezone.now().isoformat(),
        'task_id': self.request.id if hasattr(self, 'request') and self.request else None,
    }
    
    logger.info(f"Sincronización batch completada: {summary['message']}")
    return summary


@shared_task(bind=True, queue='analisis', name='intelligence.tasks.generar_embeddings_pendientes')
def generar_embeddings_pendientes(self, batch_size: int = 100):
    """
    Tarea Celery para generar embeddings para documentos que no los tienen.
    
    Args:
        batch_size: Número máximo de documentos a procesar por ejecución
    
    Returns:
        Dict con resultados de la generación
    """
    logger.info(f"Iniciando generación de embeddings pendientes (batch_size={batch_size})")
    
    # Obtener documentos sin embedding
    documents = IntelligenceDocument.objects.filter(
        embedding__isnull=True,
        content__isnull=False
    ).exclude(content='')[:batch_size]
    
    total_docs = documents.count()
    
    if total_docs == 0:
        logger.info("No hay documentos pendientes de embedding")
        return {
            'success': True,
            'message': 'No hay documentos pendientes de embedding',
            'total_processed': 0,
            'generated': 0,
            'errors': 0,
            'timestamp': timezone.now().isoformat()
        }
    
    logger.info(f"Encontrados {total_docs} documento(s) sin embedding")
    
    generated = 0
    errors = 0
    
    for doc in documents:
        try:
            # Generar embedding
            embedding = RAGService.generate_embedding(doc.content)
            
            if embedding:
                doc.embedding = embedding
                doc.save()
                generated += 1
                logger.debug(f"Embedding generado para documento {doc.id}")
            else:
                errors += 1
                logger.warning(f"No se pudo generar embedding para documento {doc.id}")
                
        except Exception as e:
            errors += 1
            logger.error(f"Error generando embedding para documento {doc.id}: {e}")
    
    result = {
        'success': errors == 0,
        'message': f'Generados {generated} embeddings de {total_docs} documentos ({errors} errores)',
        'total_processed': total_docs,
        'generated': generated,
        'errors': errors,
        'timestamp': timezone.now().isoformat(),
        'task_id': self.request.id
    }
    
    logger.info(f"Generación de embeddings completada: {result['message']}")
    return result


@shared_task(bind=True, queue='default', name='intelligence.tasks.limpiar_documentos_antiguos')
def limpiar_documentos_antiguos(self, days_old: int = 30):
    """
    Tarea Celery para limpiar documentos antiguos de colecciones inactivas.
    
    Args:
        days_old: Número de días para considerar un documento como antiguo
    
    Returns:
        Dict con resultados de la limpieza
    """
    logger.info(f"Iniciando limpieza de documentos antiguos (> {days_old} días)")
    
    # Calcular fecha límite
    cutoff_date = timezone.now() - timedelta(days=days_old)
    
    # Obtener colecciones inactivas
    inactive_collections = IntelligenceCollection.objects.filter(is_active=False)
    
    # Documentos de colecciones inactivas
    docs_from_inactive = IntelligenceDocument.objects.filter(
        collection__in=inactive_collections
    )
    
    # Documentos antiguos (de cualquier colección)
    old_docs = IntelligenceDocument.objects.filter(
        created_at__lt=cutoff_date
    )
    
    # Combinar (usando OR)
    docs_to_delete = (docs_from_inactive | old_docs).distinct()
    
    total_to_delete = docs_to_delete.count()
    
    if total_to_delete == 0:
        logger.info("No hay documentos para limpiar")
        return {
            'success': True,
            'message': 'No hay documentos para limpiar',
            'deleted': 0,
            'timestamp': timezone.now().isoformat()
        }
    
    logger.info(f"Encontrados {total_to_delete} documento(s) para eliminar")
    
    # Eliminar en lote
    deleted_count, _ = docs_to_delete.delete()
    
    result = {
        'success': True,
        'message': f'Eliminados {deleted_count} documento(s) antiguos',
        'deleted': deleted_count,
        'cutoff_date': cutoff_date.isoformat(),
        'timestamp': timezone.now().isoformat(),
        'task_id': self.request.id
    }
    
    logger.info(f"Limpieza completada: {result['message']}")
    return result


@shared_task(bind=True, queue='analisis', name='intelligence.tasks.verificar_estado_rag')
def verificar_estado_rag(self):
    """
    Tarea Celery para verificar el estado del sistema RAG.
    
    Returns:
        Dict con estadísticas del sistema RAG
    """
    logger.info("Verificando estado del sistema RAG")
    
    try:
        # Estadísticas generales
        total_collections = IntelligenceCollection.objects.count()
        active_collections = IntelligenceCollection.objects.filter(is_active=True).count()
        
        total_docs = IntelligenceDocument.objects.count()
        docs_with_embedding = IntelligenceDocument.objects.filter(embedding__isnull=False).count()
        
        # Colecciones que necesitan sincronización (más de 1 día sin sync)
        cutoff_date = timezone.now() - timedelta(days=1)
        collections_needing_sync = IntelligenceCollection.objects.filter(
            is_active=True,
            last_sync_at__lt=cutoff_date
        ).count()
        
        # Documentos sin embedding
        docs_without_embedding = total_docs - docs_with_embedding
        
        # Verificar que el modelo de embeddings esté cargado
        try:
            embedder = RAGService.get_embedder()
            embedding_model_loaded = True
            embedding_model_name = RAGService.EMBEDDING_MODEL
        except Exception as e:
            embedding_model_loaded = False
            embedding_model_name = str(e)
        
        result = {
            'success': True,
            'timestamp': timezone.now().isoformat(),
            'stats': {
                'collections': {
                    'total': total_collections,
                    'active': active_collections,
                    'needing_sync': collections_needing_sync
                },
                'documents': {
                    'total': total_docs,
                    'with_embedding': docs_with_embedding,
                    'without_embedding': docs_without_embedding,
                    'embedding_coverage': (docs_with_embedding / total_docs * 100) if total_docs > 0 else 0
                },
                'system': {
                    'embedding_model_loaded': embedding_model_loaded,
                    'embedding_model_name': embedding_model_name,
                    'embedding_dimensions': RAGService.EMBEDDING_DIMENSIONS
                }
            },
            'health': {
                'overall': embedding_model_loaded and docs_without_embedding == 0,
                'issues': []
            }
        }
        
        # Identificar problemas
        if not embedding_model_loaded:
            result['health']['issues'].append('Modelo de embeddings no cargado')
        
        if docs_without_embedding > 0:
            result['health']['issues'].append(f'{docs_without_embedding} documentos sin embedding')
        
        if collections_needing_sync > 0:
            result['health']['issues'].append(f'{collections_needing_sync} colecciones necesitan sincronización')
        
        logger.info(f"Verificación de estado RAG completada: {result['stats']}")
        return result
        
    except Exception as e:
        logger.error(f"Error verificando estado RAG: {e}")
        return {
            'success': False,
            'message': str(e),
            'timestamp': timezone.now().isoformat(),
            'task_id': self.request.id
        }