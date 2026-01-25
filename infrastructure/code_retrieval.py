"""Поиск похожего кода для few-shot примеров.

Принцип: Show, Don't Tell — модель видит реальный код вместо инструкций.
"""

from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any

from utils.config import get_config
from utils.logger import get_logger

logger = get_logger()


@dataclass
class CodeExample:
    """Пример кода для few-shot промптов."""
    
    code: str
    description: str
    source: str  # "local" | "github" | "history"
    file_path: str | None = None
    relevance_score: float = 0.0
    quality_score: float = 0.0
    language: str = "python"
    
    @property
    def formatted(self) -> str:
        """Форматирует пример для промпта.
        
        Улучшенное форматирование с указанием качества и релевантности.
        """
        source_label = {
            "local": "from project",
            "github": "from GitHub",
            "history": "from history"
        }.get(self.source, self.source)
        
        # Добавляем информацию о качестве если доступна
        quality_info = ""
        if self.quality_score > 0:
            quality_star = "⭐" if self.quality_score > 0.7 else "✓"
            quality_info = f" {quality_star}"
        
        return f"""# Example ({source_label}){quality_info}:
# {self.description}
{self.code}"""


class CodeRetriever:
    """Ищет похожий код для few-shot примеров.
    
    Использует ChromaDB для локального индекса и опционально GitHub Code Search.
    """
    
    def __init__(
        self,
        embedding_model: str = "all-MiniLM-L6-v2",
        collection_name: str = "code_examples",
        chroma_path: str = ".chroma_code"
    ):
        """Инициализирует retriever.
        
        Args:
            embedding_model: Модель для embeddings (sentence-transformers)
            collection_name: Имя коллекции в ChromaDB
            chroma_path: Путь к директории ChromaDB
        """
        self._embedding_model_name = embedding_model
        self._collection_name = collection_name
        self._chroma_path = chroma_path
        
        # Ленивая инициализация (Any для совместимости с опциональными зависимостями)
        self._embedding_model: Any = None
        self._chroma_client: Any = None
        self._collection: Any = None
        
        # Кэш для GitHub
        self._github_cache: dict[str, list[CodeExample]] = {}
    
    def _ensure_initialized(self) -> bool:
        """Инициализирует модели при первом использовании.
        
        Returns:
            True если инициализация успешна
        """
        if self._embedding_model is not None:
            return True
        
        try:
            from sentence_transformers import SentenceTransformer
            import chromadb
            
            logger.info(f"🔍 Инициализирую Code Retriever ({self._embedding_model_name})...")
            
            self._embedding_model = SentenceTransformer(self._embedding_model_name)
            self._chroma_client = chromadb.PersistentClient(path=self._chroma_path)
            self._collection = self._chroma_client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            
            logger.info("✅ Code Retriever инициализирован")
            return True
            
        except ImportError as e:
            logger.warning(f"⚠️ Code Retrieval недоступен: {e}")
            logger.info("   Установите: pip install sentence-transformers chromadb")
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации Code Retriever: {e}")
            return False
    
    def find_similar(
        self,
        query: str,
        n: int = 3,
        sources: list[str] | None = None,
        language: str = "python"
    ) -> list[CodeExample]:
        """Находит похожие примеры кода.
        
        Args:
            query: Описание задачи или контекст
            n: Количество примеров для возврата
            sources: Источники для поиска ["local", "history", "github"]
            language: Язык программирования
            
        Returns:
            Список CodeExample, отсортированный по релевантности
        """
        if not self._ensure_initialized():
            return []
        
        if sources is None:
            sources = ["local", "history"]
        
        examples: list[CodeExample] = []
        
        # 1. Поиск в локальном индексе
        if "local" in sources or "history" in sources:
            local = self._search_local(query, n=n, language=language)
            examples.extend(local)
        
        # 2. Поиск в GitHub (если нужны дополнительные)
        if "github" in sources and len(examples) < n:
            github = self._search_github(query, n=n - len(examples), language=language)
            examples.extend(github)
        
        # 3. Ранжирование
        ranked = self._rank_examples(examples, query)
        
        logger.info(f"🔍 Найдено {len(ranked[:n])} примеров для: {query[:50]}...")
        
        return ranked[:n]
    
    def _search_local(
        self,
        query: str,
        n: int,
        language: str
    ) -> list[CodeExample]:
        """Поиск в локальном ChromaDB индексе."""
        if self._collection is None or self._embedding_model is None:
            return []
        
        try:
            query_embedding = self._embedding_model.encode(query).tolist()
            
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=n,
                where={"language": language} if language else None
            )
            
            examples: list[CodeExample] = []
            documents = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]
            
            for i, doc in enumerate(documents):
                metadata = metadatas[i] if i < len(metadatas) else {}
                distance = distances[i] if i < len(distances) else 1.0
                
                examples.append(CodeExample(
                    code=doc,
                    description=metadata.get("description", ""),
                    source=metadata.get("source", "local"),
                    file_path=metadata.get("file_path"),
                    relevance_score=1.0 - distance,
                    language=language
                ))
            
            return examples
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка локального поиска: {e}")
            return []
    
    def _search_github(
        self,
        query: str,
        n: int,
        language: str
    ) -> list[CodeExample]:
        """Поиск в GitHub Code Search."""
        cache_key = f"{query}:{language}:{n}"
        if cache_key in self._github_cache:
            return self._github_cache[cache_key]
        
        try:
            from github import Github
            
            config = get_config()
            retrieval_config = config._config_data.get("code_retrieval", {})
            github_token = retrieval_config.get("github_token", "")
            
            g = Github(github_token) if github_token else Github()
            
            search_query = f"{query} language:{language} stars:>100"
            results = g.search_code(search_query)
            
            examples: list[CodeExample] = []
            for item in list(results)[:n]:
                try:
                    content = item.decoded_content.decode('utf-8')
                    snippet = self._extract_relevant_snippet(content, query)
                    
                    if snippet:
                        examples.append(CodeExample(
                            code=snippet,
                            description=f"From {item.repository.full_name}",
                            source="github",
                            file_path=item.path,
                            relevance_score=0.7,
                            language=language
                        ))
                except Exception as e:
                    logger.debug(f"⚠️ Ошибка обработки примера из GitHub: {e}")
                    continue
            
            self._github_cache[cache_key] = examples
            return examples
            
        except ImportError:
            logger.debug("PyGithub не установлен, GitHub поиск пропущен")
            return []
        except Exception as e:
            logger.warning(f"⚠️ GitHub поиск не удался: {e}")
            return []
    
    def _extract_relevant_snippet(self, content: str, query: str) -> str | None:
        """Извлекает релевантный фрагмент кода из файла."""
        try:
            tree = ast.parse(content)
            query_words = set(query.lower().split())
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    name = node.name.lower()
                    docstring = (ast.get_docstring(node) or "").lower()
                    
                    if any(word in name or word in docstring for word in query_words):
                        segment = ast.get_source_segment(content, node)
                        if segment and len(segment) > 30:
                            return segment
            
            # Fallback: первые 50 строк
            lines = content.split('\n')[:50]
            return '\n'.join(lines)
            
        except SyntaxError:
            return None
    
    def _rank_examples(
        self,
        examples: list[CodeExample],
        query: str
    ) -> list[CodeExample]:
        """Ранжирует примеры по качеству и релевантности."""
        for ex in examples:
            ex.quality_score = self._estimate_quality(ex.code)
            
            # Комбинированный скор
            source_weight = 1.0 if ex.source == "local" else 0.8 if ex.source == "history" else 0.6
            combined = (
                0.5 * ex.relevance_score +
                0.3 * ex.quality_score +
                0.2 * source_weight
            )
            ex.relevance_score = combined
        
        return sorted(examples, key=lambda x: x.relevance_score, reverse=True)
    
    def _estimate_quality(self, code: str) -> float:
        """Оценивает качество кода эвристически."""
        score = 0.5
        
        # Плюсы
        if 'def ' in code or 'class ' in code:
            score += 0.1
        if '"""' in code or "'''" in code:
            score += 0.1
        if ': ' in code and ' -> ' in code:
            score += 0.1
        if 'return ' in code:
            score += 0.05
        
        # Минусы
        if 'TODO' in code or 'FIXME' in code:
            score -= 0.1
        if code.count('pass') > 1:
            score -= 0.1
        if len(code) < 50:
            score -= 0.1
        
        return max(0.0, min(1.0, score))
    
    def index_project(
        self,
        project_path: str,
        extensions: list[str] | None = None
    ) -> int:
        """Индексирует проект для локального поиска.
        
        Args:
            project_path: Путь к проекту
            extensions: Расширения файлов для индексации
            
        Returns:
            Количество проиндексированных функций/классов
        """
        if not self._ensure_initialized():
            return 0
        
        if extensions is None:
            extensions = [".py"]
        
        indexed = 0
        project = Path(project_path)
        skip_patterns = ['.venv', '__pycache__', '.git', 'node_modules', '.chroma']
        
        logger.info(f"📂 Индексирую проект: {project_path}")
        
        for ext in extensions:
            for file_path in project.rglob(f"*{ext}"):
                if any(skip in str(file_path) for skip in skip_patterns):
                    continue
                
                try:
                    content = file_path.read_text(encoding='utf-8')
                    tree = ast.parse(content)
                    
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            code = ast.get_source_segment(content, node)
                            if code and len(code) > 30:
                                docstring = ast.get_docstring(node) or node.name
                                self._index_code(
                                    code=code,
                                    description=docstring[:200],
                                    source="local",
                                    file_path=str(file_path.relative_to(project)),
                                    language="python"
                                )
                                indexed += 1
                                
                except Exception as e:
                    logger.debug(f"Не удалось проиндексировать {file_path}: {e}")
        
        logger.info(f"✅ Проиндексировано {indexed} функций из {project_path}")
        return indexed
    
    def _index_code(
        self,
        code: str,
        description: str,
        source: str,
        file_path: str | None,
        language: str
    ) -> None:
        """Добавляет код в индекс."""
        if self._collection is None or self._embedding_model is None:
            return
        
        doc_id = hashlib.md5(code.encode()).hexdigest()
        embedding = self._embedding_model.encode(f"{description}\n{code}").tolist()
        
        self._collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[code],
            metadatas=[{
                "description": description[:500],
                "source": source,
                "file_path": file_path or "",
                "language": language
            }]
        )
    
    def add_from_history(self, task: str, code: str, success: bool) -> None:
        """Добавляет успешный код из истории генераций.
        
        Args:
            task: Описание задачи
            code: Сгенерированный код
            success: Была ли генерация успешной
        """
        if success and len(code) > 50:
            self._index_code(
                code=code,
                description=task[:200],
                source="history",
                file_path=None,
                language="python"
            )
            logger.debug("📝 Добавлен успешный код в историю")
    
    def get_stats(self) -> dict:
        """Возвращает статистику индекса."""
        if self._collection is None:
            return {"count": 0, "initialized": False}
        
        try:
            count = self._collection.count()
            return {
                "count": count,
                "initialized": True,
                "embedding_model": self._embedding_model_name,
                "chroma_path": self._chroma_path
            }
        except Exception as e:
            logger.debug(f"⚠️ Ошибка получения статистики CodeRetrieval: {e}")
            return {"count": 0, "initialized": True}


def is_code_retrieval_enabled() -> bool:
    """Проверяет включён ли code retrieval в конфигурации."""
    config = get_config()
    retrieval_config = config._config_data.get("code_retrieval", {})
    return retrieval_config.get("enabled", False)


def get_code_retriever() -> CodeRetriever | None:
    """Возвращает синглтон CodeRetriever или None если отключён.
    
    Returns:
        CodeRetriever если включён, иначе None
    """
    if not is_code_retrieval_enabled():
        return None
    
    config = get_config()
    retrieval_config = config._config_data.get("code_retrieval", {})
    
    return CodeRetriever(
        embedding_model=retrieval_config.get("embedding_model", "all-MiniLM-L6-v2"),
        collection_name="code_examples",
        chroma_path=retrieval_config.get("chroma_path", ".chroma_code")
    )
