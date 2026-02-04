"""
Utilidades para almacenar documentos crudos en Azure Blob Storage.
"""
import os
import logging
from datetime import datetime
from django.conf import settings

try:
    from azure.storage.blob import BlobServiceClient, ContentSettings
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False
    logging.warning("azure-storage-blob no está instalado. Instalar con: pip install azure-storage-blob")

logger = logging.getLogger(__name__)


class AzureStorageError(Exception):
    """Excepción personalizada para errores de Azure Storage."""
    pass


def get_blob_service_client():
    """
    Crea y retorna un cliente de BlobServiceClient usando la cadena de conexión.
    """
    if not AZURE_AVAILABLE:
        raise AzureStorageError("azure-storage-blob no está instalado")
    
    connection_string = settings.AZURE_STORAGE_CONNECTION_STRING
    if not connection_string:
        # Intentar con account name y key
        account_name = settings.AZURE_STORAGE_ACCOUNT_NAME
        account_key = settings.AZURE_STORAGE_ACCOUNT_KEY
        if account_name and account_key:
            connection_string = (
                f"DefaultEndpointsProtocol=https;"
                f"AccountName={account_name};"
                f"AccountKey={account_key};"
                f"EndpointSuffix=core.windows.net"
            )
        else:
            raise AzureStorageError(
                "Se requiere AZURE_STORAGE_CONNECTION_STRING o "
                "AZURE_STORAGE_ACCOUNT_NAME + AZURE_STORAGE_ACCOUNT_KEY"
            )
    
    try:
        return BlobServiceClient.from_connection_string(connection_string)
    except Exception as e:
        raise AzureStorageError(f"Error al conectar con Azure Storage: {e}")


def ensure_container_exists(container_name=None):
    """
    Asegura que el contenedor exista en Azure Storage.
    """
    if container_name is None:
        container_name = settings.AZURE_STORAGE_CONTAINER_NAME
    
    try:
        blob_service_client = get_blob_service_client()
        container_client = blob_service_client.get_container_client(container_name)
        if not container_client.exists():
            container_client.create_container()
            logger.info(f"Contenedor '{container_name}' creado en Azure Storage")
        return container_client
    except Exception as e:
        raise AzureStorageError(f"Error al verificar/crear contenedor: {e}")


def upload_raw_content(content, fuente_id, timestamp=None, tipo_documento='html', metadata=None):
    """
    Sube contenido crudo (HTML, PDF, texto extraído) a Azure Blob Storage.
    
    Args:
        content (str|bytes): Contenido a subir (texto o binario).
        fuente_id (int): ID de la fuente web para nombrar el blob.
        timestamp (datetime, optional): Marca de tiempo para el nombre.
        tipo_documento (str): Tipo de documento ('html', 'pdf_nativo', 'json', etc.).
        metadata (dict, optional): Metadatos adicionales para el blob.
    
    Returns:
        dict: Información del blob subido {'url': str, 'nombre': str}.
    """
    if settings.RAW_HTML_STORAGE != 'blob_storage':
        logger.warning("RAW_HTML_STORAGE no está configurado como 'blob_storage'. No se subirá a Azure.")
        return None
    
    if timestamp is None:
        timestamp = datetime.utcnow()
    
    # Determinar extensión del archivo
    extensiones = {
        'html': 'html',
        'pdf_nativo': 'pdf',
        'pdf_escaneado': 'pdf',
        'json': 'json',
        'xml': 'xml',
        'otro': 'txt',
    }
    extension = extensiones.get(tipo_documento, 'txt')
    
    # Formato del nombre del blob: fuentes/{fuente_id}/{año}/{mes}/{dia}/{timestamp}_{fuente_id}.{ext}
    date_path = timestamp.strftime("%Y/%m/%d")
    timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
    blob_name = f"fuentes/{fuente_id}/{date_path}/{timestamp_str}_{fuente_id}.{extension}"
    
    try:
        container_client = ensure_container_exists()
        blob_client = container_client.get_blob_client(blob_name)
        
        # Determinar content-type
        content_types = {
            'html': 'text/html',
            'pdf_nativo': 'application/pdf',
            'pdf_escaneado': 'application/pdf',
            'json': 'application/json',
            'xml': 'application/xml',
            'otro': 'text/plain',
        }
        content_type = content_types.get(tipo_documento, 'text/plain')
        
        # Configurar metadatos
        blob_metadata = {
            'fuente_id': str(fuente_id),
            'upload_time': timestamp.isoformat(),
            'tipo_documento': tipo_documento,
            'content_type': content_type,
        }
        if metadata:
            blob_metadata.update({k: str(v) for k, v in metadata.items()})
        
        # Subir contenido
        content_settings = ContentSettings(
            content_type=content_type,
            content_encoding='utf-8' if isinstance(content, str) else None
        )
        
        # Convertir a bytes si es necesario
        if isinstance(content, str):
            content_bytes = content.encode('utf-8')
        else:
            content_bytes = content
        
        blob_client.upload_blob(
            content_bytes,
            overwrite=True,
            content_settings=content_settings,
            metadata=blob_metadata
        )
        
        blob_url = blob_client.url
        logger.info(f"Contenido {tipo_documento} subido a Azure: {blob_name} ({len(content_bytes)} bytes)")
        
        return {
            'url': blob_url,
            'nombre': blob_name,
            'tamaño': len(content_bytes),
            'tipo': tipo_documento,
        }
        
    except Exception as e:
        logger.error(f"Error al subir contenido a Azure Storage: {e}")
        raise AzureStorageError(f"Error al subir contenido: {e}")


def upload_raw_html(html_content, fuente_id, timestamp=None, metadata=None):
    """
    Sube contenido HTML crudo a Azure Blob Storage.
    DEPRECATED: Usar upload_raw_content en su lugar.
    
    Args:
        html_content (str): Contenido HTML a subir.
        fuente_id (int): ID de la fuente web para nombrar el blob.
        timestamp (datetime, optional): Marca de tiempo para el nombre.
        metadata (dict, optional): Metadatos adicionales para el blob.
    
    Returns:
        str: URL del blob subido.
    """
    result = upload_raw_content(
        html_content,
        fuente_id,
        timestamp=timestamp,
        tipo_documento='html',
        metadata=metadata
    )
    return result['url'] if result else None


def download_raw_content(blob_name, container_name=None):
    """
    Descarga contenido crudo desde Azure Blob Storage.
    
    Args:
        blob_name (str): Nombre del blob a descargar.
        container_name (str, optional): Nombre del contenedor.
    
    Returns:
        bytes: Contenido del blob.
    """
    try:
        if container_name is None:
            container_client = ensure_container_exists()
        else:
            container_client = ensure_container_exists(container_name)
        
        blob_client = container_client.get_blob_client(blob_name)
        
        # Descargar contenido
        download_stream = blob_client.download_blob()
        content = download_stream.readall()
        
        logger.info(f"Contenido descargado desde Azure: {blob_name} ({len(content)} bytes)")
        return content
        
    except Exception as e:
        logger.error(f"Error al descargar contenido desde Azure: {e}")
        raise AzureStorageError(f"Error al descargar: {e}")


def upload_pdf_binario(pdf_content: bytes, fuente_id: int, timestamp=None, metadata=None):
    """
    Sube contenido binario de PDF a Azure Blob Storage.
    
    Args:
        pdf_content (bytes): Contenido del PDF en bytes.
        fuente_id (int): ID de la fuente web.
        timestamp (datetime, optional): Marca de tiempo.
        metadata (dict, optional): Metadatos adicionales.
    
    Returns:
        dict: Información del blob subido.
    """
    return upload_raw_content(
        pdf_content,
        fuente_id,
        timestamp=timestamp,
        tipo_documento='pdf_nativo',
        metadata=metadata
    )


def upload_file(file_path, blob_name=None, container_name=None, content_type=None):
    """
    Sube un archivo local a Azure Blob Storage.
    
    Args:
        file_path (str): Ruta local del archivo.
        blob_name (str, optional): Nombre del blob. Si es None, se usa el nombre del archivo.
        container_name (str, optional): Nombre del contenedor. Si es None, se usa el configurado.
        content_type (str, optional): Tipo MIME del contenido.
    
    Returns:
        str: URL del blob subido.
    """
    if not os.path.exists(file_path):
        raise AzureStorageError(f"Archivo no encontrado: {file_path}")
    
    if blob_name is None:
        blob_name = os.path.basename(file_path)
    
    try:
        if container_name is None:
            container_client = ensure_container_exists()
        else:
            container_client = ensure_container_exists(container_name)
        
        blob_client = container_client.get_blob_client(blob_name)
        
        with open(file_path, 'rb') as file_data:
            blob_client.upload_blob(file_data, overwrite=True)
        
        # Actualizar content type si se especificó
        if content_type:
            blob_client.set_http_headers(ContentSettings(content_type=content_type))
        
        logger.info(f"Archivo subido a Azure Blob Storage: {blob_name} desde {file_path}")
        return blob_client.url
    except Exception as e:
        logger.error(f"Error al subir archivo a Azure Storage: {e}")
        raise AzureStorageError(f"Error al subir archivo: {e}")


def delete_blob(blob_name, container_name=None):
    """
    Elimina un blob de Azure Storage.
    
    Args:
        blob_name (str): Nombre del blob a eliminar.
        container_name (str, optional): Nombre del contenedor.
    
    Returns:
        bool: True si se eliminó correctamente.
    """
    try:
        if container_name is None:
            container_client = ensure_container_exists()
        else:
            container_client = ensure_container_exists(container_name)
        
        blob_client = container_client.get_blob_client(blob_name)
        blob_client.delete_blob()
        logger.info(f"Blob eliminado: {blob_name}")
        return True
    except Exception as e:
        logger.error(f"Error al eliminar blob: {e}")
        return False


def list_blobs(prefix=None, container_name=None):
    """
    Lista blobs en el contenedor.
    
    Args:
        prefix (str, optional): Prefijo para filtrar blobs.
        container_name (str, optional): Nombre del contenedor.
    
    Returns:
        list: Lista de nombres de blobs.
    """
    try:
        if container_name is None:
            container_client = ensure_container_exists()
        else:
            container_client = ensure_container_exists(container_name)
        
        blobs = container_client.list_blobs(name_starts_with=prefix) if prefix else container_client.list_blobs()
        return [blob.name for blob in blobs]
    except Exception as e:
        logger.error(f"Error al listar blobs: {e}")
        return []