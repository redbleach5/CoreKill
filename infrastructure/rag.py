"""RAG-система на базе ChromaDB для локального поиска по документам."""
from typing import List, Dict, Optional, Any, TYPE_CHECKING
import os
import ollama
from utils.config import get_config
from utils.logger import get_logger

logger = get_logger()

# Опциональный импорт ChromaDB
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    chromadb = None  # type: ignore[assignment]
    Settings = None  # type: ignore[assignment,misc]
    CHROMADB_AVAILABLE = False
    logger.warning("⚠️ ChromaDB недоступен. RAG будет работать в режиме без векторной БД.")


class RAGSystem:
    """Система поиска релевантных документов на базе ChromaDB и nomic-embed-text.
    
    Позволяет хранить документы и находить релевантный контекст по запросу.
    """

    def __init__(self, collection_name: str = "codebase_docs", persist_directory: str = ".chromadb") -> None:
        """Инициализация RAG-системы.
        
        Args:
            collection_name: Название коллекции в ChromaDB
            persist_directory: Директория для персистентного хранения ChromaDB
        """
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        self.enabled = CHROMADB_AVAILABLE
        config = get_config()
        self.embedding_model = getattr(config, 'embedding_model', 'nomic-embed-text')
        
        # Типизация для Optional клиента и коллекции
        self.client: Any = None
        self.collection: Any = None
        
        # Инициализируем ChromaDB только если доступен
        if self.enabled:
            try:
                # Создаём директорию если её нет
                os.makedirs(persist_directory, exist_ok=True)
                
                # Инициализируем клиент ChromaDB
                self.client = chromadb.PersistentClient(
                    path=persist_directory,
                    settings=Settings(anonymized_telemetry=False)
                )
                
                # Получаем или создаём коллекцию
                try:
                    self.collection = self.client.get_collection(name=collection_name)
                except Exception:
                    self.collection = self.client.create_collection(
                        name=collection_name,
                        metadata={"description": "Codebase documentation and context"}
                    )
                logger.info(f"✅ RAG система инициализирована с ChromaDB (коллекция: {collection_name})")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка инициализации ChromaDB: {e}. RAG будет работать без векторной БД.")
                self.enabled = False
                self.client = None
                self.collection = None
        else:
            self.client = None
            self.collection = None
            logger.info("ℹ️ RAG система работает без ChromaDB (векторная БД недоступна)")

    def _get_embedding(self, text: str) -> List[float]:
        """Получает embedding для текста через Ollama.
        
        Args:
            text: Текст для получения embedding
            
        Returns:
            Список чисел (вектор embedding)
        """
        try:
            response = ollama.embeddings(
                model=self.embedding_model,
                prompt=text
            )
            return response["embedding"]
        except Exception as e:
            logger.error(f"❌ Ошибка получения embedding: {e}", error=e)
            # Возвращаем пустой embedding (нулевой вектор нужной размерности)
            # nomic-embed-text обычно возвращает 768 измерений
            return [0.0] * 768

    def add_documents(self, documents: List[str], metadatas: Optional[List[Dict[str, str]]] = None) -> None:
        """Добавляет документы в коллекцию.
        
        Args:
            documents: Список текстов документов
            metadatas: Опциональные метаданные для каждого документа
        """
        if not self.enabled or not self.collection:
            logger.debug("RAG без ChromaDB: документы не сохраняются")
            return
        
        if not documents:
            return
        
        if metadatas is None:
            metadatas = [{}] * len(documents)
        elif len(metadatas) != len(documents):
            metadatas = [{}] * len(documents)
        
        # Генерируем ID для документов
        ids = [f"doc_{i}_{hash(doc) % 1000000}" for i, doc in enumerate(documents)]
        
        # Получаем embeddings для всех документов
        embeddings: List[List[float]] = []
        for doc in documents:
            embedding = self._get_embedding(doc)
            embeddings.append(embedding)
        
        # Добавляем в коллекцию
        try:
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )
            logger.info(f"✅ Добавлено {len(documents)} документов в RAG")
        except Exception as e:
            logger.error(f"❌ Ошибка добавления документов в RAG: {e}", error=e)

    def get_relevant_context(self, query: str, n_results: int = 4) -> str:
        """Находит релевантный контекст по запросу.
        
        Args:
            query: Текст запроса
            n_results: Количество возвращаемых результатов
            
        Returns:
            Объединённый контекст из найденных документов. Пустая строка если ничего не найдено.
        """
        if not self.enabled or not self.collection:
            return ""  # RAG без ChromaDB не может искать
        
        if not query.strip():
            return ""
        
        try:
            # Получаем embedding для запроса
            query_embedding = self._get_embedding(query)
            
            # Ищем похожие документы
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )
            
            # Извлекаем документы из результатов
            documents = results.get("documents", [])
            if not documents or not documents[0]:
                return ""
            
            # Объединяем найденные документы
            context_parts: List[str] = []
            for i, doc in enumerate(documents[0]):
                if doc:
                    context_parts.append(f"[Контекст {i + 1}]\n{doc}\n")
            
            context = "\n".join(context_parts).strip()
            return context
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска в RAG: {e}", error=e)
            return ""

    def get_relevant_context_with_metadata(
        self,
        query: str,
        n_results: int = 4
    ) -> List[Dict[str, Any]]:
        """Находит релевантный контекст с метаданными.
        
        Args:
            query: Текст запроса
            n_results: Количество возвращаемых результатов
            
        Returns:
            Список словарей с полями: document, metadata, distance
        """
        if not self.enabled or not self.collection:
            return []  # RAG без ChromaDB не может искать
        
        if not query.strip():
            return []
        
        try:
            query_embedding = self._get_embedding(query)
            
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                include=["documents", "metadatas", "distances"]
            )
            
            documents = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]
            
            result_list: List[Dict[str, Any]] = []
            for i, doc in enumerate(documents):
                if doc:
                    result_list.append({
                        "document": doc,
                        "metadata": metadatas[i] if i < len(metadatas) else {},
                        "distance": distances[i] if i < len(distances) else 0.0
                    })
            
            return result_list
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска в RAG с метаданными: {e}", error=e)
            return []
