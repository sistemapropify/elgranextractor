"""
FAISS Index Manager para búsqueda vectorial eficiente.
Usa índice HNSWFlat para búsqueda aproximada O(log n).

Estructura:
- Un índice FAISS por colección
- Persistencia en disco (carpeta data/faiss_indexes/)
- Reconstrucción automática después de sync
- Carga de todos los índices al iniciar la aplicación
- Validación de dimensionalidad (FIX-OOM: 384d desde multilingual-e5-small)

Dependencia: faiss-cpu (instalar con: pip install faiss-cpu)
"""

import os
import pickle
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
import logging

logger = logging.getLogger(__name__)


class FAISSIndexManager:
    """
    Gestiona índices FAISS HNSW para búsqueda vectorial.

    HNSWFlat: Hierarchical Navigable Small World graph
    - d = 384 (dimensionalidad del embedding, configurable)
    - M = 32 (conexiones por nodo)
    - efConstruction = 200 (precisión vs velocidad en construcción)
    - efSearch = 50 (balance precisión/velocidad en búsqueda)

    Singleton por colección: get_instance(collection_name)
    """

    _instances: Dict[str, 'FAISSIndexManager'] = {}
    _index_dir: Optional[str] = None

    def __init__(self, collection_name: str, dimension: int = 384):
        """
        Inicializa el manager para una colección.

        Args:
            collection_name: Nombre único de la colección
            dimension: Dimensionalidad del embedding (384 para multilingual-e5-small)
        """
        self.collection_name = collection_name
        self.dimension = dimension
        self.index: Any = None  # faiss.Index, pero evitamos import temprano
        self.id_map: Dict[int, str] = {}  # posición FAISS -> document_id (UUID string)
        self.is_loaded = False
        self._faiss_available = False

        # Configuración HNSW
        self.hnsw_m = 32
        self.ef_construction = 200
        self.ef_search = 50

        # Verificar disponibilidad de FAISS
        try:
            import faiss
            self._faiss_available = True
        except ImportError:
            logger.warning(
                "FAISS no está instalado. La búsqueda vectorial usará el método O(n) por similitud de coseno. "
                "Instala con: pip install faiss-cpu"
            )

    @classmethod
    def get_index_dir(cls) -> str:
        """Obtiene el directorio donde se persisten los índices FAISS."""
        if cls._index_dir is None:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            cls._index_dir = os.path.join(base, 'data', 'faiss_indexes')
            os.makedirs(cls._index_dir, exist_ok=True)
            logger.info(f"Directorio de índices FAISS: {cls._index_dir}")
        return cls._index_dir

    @classmethod
    def get_instance(cls, collection_name: str, dimension: int = 384) -> 'FAISSIndexManager':
        """
        Obtiene o crea una instancia singleton para una colección.

        Args:
            collection_name: Nombre de la colección
            dimension: Dimensionalidad del embedding

        Returns:
            Instancia de FAISSIndexManager para esa colección
        """
        if collection_name not in cls._instances:
            cls._instances[collection_name] = cls(collection_name, dimension)
        return cls._instances[collection_name]

    def build_index(self, embeddings: List[bytes], doc_ids: List[str]) -> int:
        """
        Construye o reconstruye el índice HNSW.

        Args:
            embeddings: Lista de embeddings en bytes (cada uno es un vector float32)
            doc_ids: Lista de UUIDs de documentos (misma posición que embeddings)

        Returns:
            Número de vectores indexados, 0 si FAISS no está disponible
        """
        if not self._faiss_available:
            logger.warning(f"FAISS no disponible, no se puede construir índice para '{self.collection_name}'")
            return 0

        if not embeddings:
            logger.warning(f"No hay embeddings para construir índice de '{self.collection_name}'")
            return 0

        import faiss

        # Convertir bytes a numpy array
        vectors = np.array([
            np.frombuffer(emb, dtype=np.float32) for emb in embeddings
        ]).astype(np.float32)

        # Verificar dimensiones
        if vectors.shape[1] != self.dimension:
            logger.error(
                f"Dimensión incorrecta en embeddings: esperada {self.dimension}, "
                f"recibida {vectors.shape[1]}"
            )
            return 0

        # Normalizar vectores (para similitud coseno con Inner Product)
        faiss.normalize_L2(vectors)

        # Crear índice HNSWFlat
        self.index = faiss.IndexHNSWFlat(self.dimension, self.hnsw_m)
        self.index.hnsw.efConstruction = self.ef_construction

        # Entrenar y añadir vectores
        self.index.train(vectors)
        self.index.add(vectors)

        # Mapear posiciones FAISS a document_ids
        self.id_map = {i: doc_ids[i] for i in range(len(doc_ids))}
        self.is_loaded = True

        # Persistir a disco
        self._save()

        logger.info(
            f"Índice FAISS construido para '{self.collection_name}': "
            f"{len(embeddings)} vectores, dimensión={self.dimension}, "
            f"M={self.hnsw_m}, efConstruction={self.ef_construction}"
        )
        return len(embeddings)

    def search(self, query_vector: np.ndarray, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Busca los top_k vecinos más cercanos usando el índice HNSW.

        Args:
            query_vector: Vector de query (numpy array float32, 1D o 2D)
            top_k: Número máximo de resultados

        Returns:
            Lista de dicts con {document_id, similarity, faiss_position}
            Vacía si el índice no está cargado o FAISS no disponible
        """
        if not self._faiss_available:
            return []

        if not self.is_loaded or self.index is None:
            logger.warning(f"Índice FAISS no cargado para '{self.collection_name}'")
            return []

        import faiss

        # Asegurar shape correcto (1, dimension)
        if query_vector.ndim == 1:
            query_vector = query_vector.reshape(1, -1)

        # Verificar dimensiones
        if query_vector.shape[1] != self.dimension:
            logger.error(
                f"Dimensión incorrecta en query vector: esperada {self.dimension}, "
                f"recibida {query_vector.shape[1]}"
            )
            return []

        # Normalizar query vector (para IP = cosine similarity)
        faiss.normalize_L2(query_vector)

        # Configurar efSearch para esta búsqueda
        self.index.hnsw.efSearch = self.ef_search

        # Buscar
        distances, indices = self.index.search(query_vector, top_k)

        results = []
        for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
            if idx == -1:
                continue  # FAISS retorna -1 cuando no hay suficientes resultados

            doc_id = self.id_map.get(int(idx))
            if doc_id:
                # FAISS IndexHNSWFlat usa distancia L2, no similitud coseno.
                # Para vectores L2-normalizados: cos_sim = 1 - L2²/2
                l2_dist = float(dist)
                similarity = 1.0 - (l2_dist * l2_dist) / 2.0
                if similarity < 0:
                    similarity = 0.0
                results.append({
                    'document_id': doc_id,
                    'similarity': similarity,
                    'faiss_position': int(idx)
                })

        return results

    def _save(self):
        """Persiste el índice FAISS y el id_map a disco."""
        if not self._faiss_available or self.index is None:
            return

        import faiss
        index_dir = self.get_index_dir()

        try:
            # Guardar índice FAISS
            faiss_path = os.path.join(index_dir, f"{self.collection_name}.faiss")
            faiss.write_index(self.index, faiss_path)

            # Guardar id_map
            map_path = os.path.join(index_dir, f"{self.collection_name}_id_map.pkl")
            with open(map_path, 'wb') as f:
                pickle.dump(self.id_map, f)

            logger.debug(f"Índice FAISS persistido para '{self.collection_name}'")
        except Exception as e:
            logger.error(f"Error persistiendo índice FAISS para '{self.collection_name}': {e}")

    def load(self) -> bool:
        """
        Carga el índice FAISS desde disco.
        
        Valida que la dimensión del índice coincida con la esperada.
        Si no coincide (ej: migración 1024→384), elimina el índice antiguo
        para que sea reconstruido en el próximo sync.

        Returns:
            True si se cargó exitosamente, False si no existe o hay error
        """
        if not self._faiss_available:
            return False

        import faiss
        index_dir = self.get_index_dir()
        faiss_path = os.path.join(index_dir, f"{self.collection_name}.faiss")
        map_path = os.path.join(index_dir, f"{self.collection_name}_id_map.pkl")

        if not os.path.exists(faiss_path) or not os.path.exists(map_path):
            logger.info(f"No hay índice FAISS persistido para '{self.collection_name}'")
            return False

        try:
            self.index = faiss.read_index(faiss_path)
            with open(map_path, 'rb') as f:
                self.id_map = pickle.load(f)
            
            # ── Validación de dimensionalidad (FIX-OOM) ──
            # Si el índice fue creado con una dimensión diferente (ej: 1024 antigua),
            # se descarta para que sea reconstruido con la dimensión actual (384).
            index_dim = self.index.d
            if index_dim != self.dimension:
                logger.warning(
                    f"Índice FAISS para '{self.collection_name}' tiene dimensión "
                    f"{index_dim}, pero se espera {self.dimension}. "
                    f"Descartando índice antiguo para reconstrucción..."
                )
                self.index = None
                self.id_map = {}
                self.is_loaded = False
                # Eliminar archivos antiguos
                try:
                    os.remove(faiss_path)
                    os.remove(map_path)
                    logger.info(f"Índice FAISS antiguo eliminado para '{self.collection_name}'")
                except OSError as rm_err:
                    logger.warning(f"No se pudo eliminar índice antiguo: {rm_err}")
                return False
            
            self.is_loaded = True
            logger.info(
                f"Índice FAISS cargado para '{self.collection_name}': "
                f"{self.index.ntotal} vectores, dimensión={self.dimension}"
            )
            return True
        except Exception as e:
            logger.error(f"Error cargando índice FAISS para '{self.collection_name}': {e}")
            self.is_loaded = False
            return False

    @classmethod
    def load_all(cls):
        """Carga todos los índices FAISS desde disco."""
        index_dir = cls.get_index_dir()
        if not os.path.exists(index_dir):
            logger.info(f"No existe directorio de índices FAISS: {index_dir}")
            return

        loaded_count = 0
        for fname in os.listdir(index_dir):
            if fname.endswith('.faiss'):
                collection_name = fname[:-6]  # quitar extensión .faiss
                instance = cls.get_instance(collection_name)
                if instance.load():
                    loaded_count += 1

        if loaded_count > 0:
            logger.info(f"Índices FAISS cargados: {loaded_count} colecciones")
        else:
            logger.info("No se cargaron índices FAISS (puede ser la primera ejecución)")

    @classmethod
    def rebuild_for_collection(cls, collection_name: str, dimension: int = 384) -> int:
        """
        Reconstruye el índice FAISS para una colección desde los documentos en BD.

        Args:
            collection_name: Nombre de la colección
            dimension: Dimensionalidad del embedding

        Returns:
            Número de vectores indexados, 0 si no hay documentos o FAISS no disponible
        """
        from ..models import IntelligenceDocument

        instance = cls.get_instance(collection_name, dimension)

        # Obtener documentos con embedding de esta colección
        docs = IntelligenceDocument.objects.filter(
            collection__name=collection_name,
            embedding__isnull=False
        ).values_list('id', 'embedding')

        if not docs:
            logger.warning(f"No hay documentos con embedding para '{collection_name}'")
            return 0

        doc_ids = [str(doc[0]) for doc in docs]
        embeddings = [doc[1] for doc in docs]

        return instance.build_index(embeddings, doc_ids)

    @classmethod
    def rebuild_all(cls, dimension: int = 384) -> Dict[str, int]:
        """
        Reconstruye índices FAISS para todas las colecciones que tengan documentos.

        Args:
            dimension: Dimensionalidad del embedding

        Returns:
            Dict {collection_name: vectores_indexados}
        """
        from ..models import IntelligenceCollection

        results = {}
        collections = IntelligenceCollection.objects.filter(is_active=True)

        for collection in collections:
            count = cls.rebuild_for_collection(collection.name, dimension)
            if count > 0:
                results[collection.name] = count

        logger.info(f"Índices FAISS reconstruidos para {len(results)} colecciones")
        return results

    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        """
        Obtiene el estado de todos los índices FAISS.

        Returns:
            Dict con información de estado
        """
        status = {
            'faiss_available': False,
            'collections': {},
            'total_vectors': 0,
            'index_dir': cls.get_index_dir()
        }

        # Verificar si al menos una instancia tiene FAISS disponible
        for name, instance in cls._instances.items():
            if instance._faiss_available:
                status['faiss_available'] = True

            collection_status = {
                'loaded': instance.is_loaded,
                'vectors': instance.index.ntotal if instance.is_loaded and instance.index is not None else 0,
                'dimension': instance.dimension
            }
            status['collections'][name] = collection_status
            status['total_vectors'] += collection_status['vectors']

        return status
