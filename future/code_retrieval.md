# Code Retrieval: Example-Based Generation

## Статус: 🚀 ПРИОРИТЕТ — Фаза 4

## Принцип: Show, Don't Tell

```
❌ Текущий подход (инструкции):
"Write a function that sorts a list. Use Python 3.10+ with type hints.
Follow PEP8. Handle edge cases. Add docstring..."

✅ Новый подход (примеры):
"Write a function similar to these examples:

Example 1 (from project):
def filter_users(users: list[User]) -> list[User]:
    '''Фильтрует активных пользователей.'''
    return [u for u in users if u.is_active]

Example 2 (from GitHub):
def sort_by_date(items: list[Item]) -> list[Item]:
    '''Сортирует элементы по дате.'''
    return sorted(items, key=lambda x: x.created_at)

Now write: sort users by registration date"
```

**Почему примеры лучше инструкций:**
1. Модель видит РЕАЛЬНЫЙ рабочий код
2. Стиль автоматически копируется
3. Меньше "галлюцинаций" в синтаксисе
4. Консистентность с проектом

## Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                      Code Retrieval System                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ Local Index  │    │ GitHub Search│    │ Embedding    │       │
│  │              │    │              │    │ Model        │       │
│  │ - Project    │    │ - Public     │    │              │       │
│  │ - History    │    │ - Stars>100  │    │ MiniLM-L6    │       │
│  │ - Patterns   │    │ - Recent     │    │ or           │       │
│  │              │    │              │    │ CodeBERT     │       │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘       │
│         │                   │                   │               │
│         └───────────────────┴───────────────────┘               │
│                             │                                    │
│                    ┌────────▼────────┐                          │
│                    │  Retriever      │                          │
│                    │                 │                          │
│                    │  - Semantic     │                          │
│                    │  - Keyword      │                          │
│                    │  - Hybrid       │                          │
│                    └────────┬────────┘                          │
│                             │                                    │
│                    ┌────────▼────────┐                          │
│                    │  Ranker         │                          │
│                    │                 │                          │
│                    │  - Relevance    │                          │
│                    │  - Quality      │                          │
│                    │  - Freshness    │                          │
│                    └────────┬────────┘                          │
│                             │                                    │
│                    ┌────────▼────────┐                          │
│                    │  Examples       │                          │
│                    │  (Top 3-5)      │                          │
│                    └─────────────────┘                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Реализация

### 1. Code Retriever

```python
# infrastructure/code_retrieval.py
"""Поиск похожего кода для few-shot примеров."""

from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path
import hashlib

from sentence_transformers import SentenceTransformer
import chromadb
from utils.logger import get_logger

logger = get_logger()


@dataclass
class CodeExample:
    """Пример кода для few-shot."""
    code: str
    description: str
    source: str  # "local" | "github" | "history"
    file_path: Optional[str] = None
    relevance_score: float = 0.0
    quality_score: float = 0.0
    language: str = "python"
    
    @property
    def formatted(self) -> str:
        """Форматирует пример для промпта."""
        source_label = {
            "local": "from project",
            "github": "from GitHub",
            "history": "from history"
        }.get(self.source, self.source)
        
        return f"""# Example ({source_label}):
# {self.description}
{self.code}"""


class CodeRetriever:
    """Ищет похожий код для few-shot примеров."""
    
    def __init__(
        self,
        embedding_model: str = "all-MiniLM-L6-v2",
        collection_name: str = "code_examples"
    ):
        self.embedding_model = SentenceTransformer(embedding_model)
        
        # ChromaDB для локального индекса
        self.chroma_client = chromadb.PersistentClient(path=".chroma_code")
        self.collection = self.chroma_client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        
        # Кэш для GitHub результатов
        self._github_cache: dict[str, List[CodeExample]] = {}
    
    def find_similar(
        self,
        query: str,
        n: int = 3,
        sources: List[str] = ["local", "github", "history"],
        language: str = "python"
    ) -> List[CodeExample]:
        """Находит похожие примеры кода.
        
        Args:
            query: Описание задачи
            n: Количество примеров
            sources: Источники для поиска
            language: Язык программирования
            
        Returns:
            Список CodeExample, отсортированный по релевантности
        """
        examples: List[CodeExample] = []
        
        # 1. Поиск в локальном индексе (проект + история)
        if "local" in sources or "history" in sources:
            local = self._search_local(query, n=n, language=language)
            examples.extend(local)
        
        # 2. Поиск в GitHub
        if "github" in sources and len(examples) < n:
            github = self._search_github(query, n=n - len(examples), language=language)
            examples.extend(github)
        
        # 3. Ранжирование и отбор лучших
        ranked = self._rank_examples(examples, query)
        
        return ranked[:n]
    
    def _search_local(
        self,
        query: str,
        n: int,
        language: str
    ) -> List[CodeExample]:
        """Поиск в локальном ChromaDB индексе."""
        try:
            # Получаем embedding запроса
            query_embedding = self.embedding_model.encode(query).tolist()
            
            # Поиск в ChromaDB
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n,
                where={"language": language} if language else None
            )
            
            examples = []
            for i, doc in enumerate(results.get("documents", [[]])[0]):
                metadata = results.get("metadatas", [[]])[0][i]
                distance = results.get("distances", [[]])[0][i]
                
                examples.append(CodeExample(
                    code=doc,
                    description=metadata.get("description", ""),
                    source=metadata.get("source", "local"),
                    file_path=metadata.get("file_path"),
                    relevance_score=1.0 - distance,  # Convert distance to similarity
                    language=language
                ))
            
            return examples
            
        except Exception as e:
            logger.warning(f"Local search failed: {e}")
            return []
    
    def _search_github(
        self,
        query: str,
        n: int,
        language: str
    ) -> List[CodeExample]:
        """Поиск в GitHub Code Search."""
        # Кэш для избежания rate limits
        cache_key = f"{query}:{language}:{n}"
        if cache_key in self._github_cache:
            return self._github_cache[cache_key]
        
        try:
            from github import Github
            
            # GitHub API (требует токен для Code Search)
            # Без токена — ограничение 10 req/min
            g = Github()  # или Github(token) для больших лимитов
            
            # Формируем поисковый запрос
            search_query = f"{query} language:{language} stars:>100"
            
            results = g.search_code(search_query)
            
            examples = []
            for item in results[:n]:
                try:
                    content = item.decoded_content.decode('utf-8')
                    
                    # Извлекаем релевантную функцию/класс
                    code_snippet = self._extract_relevant_snippet(content, query)
                    
                    if code_snippet:
                        examples.append(CodeExample(
                            code=code_snippet,
                            description=f"From {item.repository.full_name}",
                            source="github",
                            file_path=item.path,
                            relevance_score=0.7,  # GitHub results are pre-filtered
                            language=language
                        ))
                except Exception:
                    continue
            
            self._github_cache[cache_key] = examples
            return examples
            
        except ImportError:
            logger.info("PyGithub not installed, skipping GitHub search")
            return []
        except Exception as e:
            logger.warning(f"GitHub search failed: {e}")
            return []
    
    def _extract_relevant_snippet(self, content: str, query: str) -> Optional[str]:
        """Извлекает релевантный фрагмент кода."""
        import ast
        
        try:
            tree = ast.parse(content)
            
            # Ищем функции и классы
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    # Простая эвристика: имя или docstring содержит ключевые слова
                    name = node.name.lower()
                    docstring = ast.get_docstring(node) or ""
                    
                    query_words = query.lower().split()
                    if any(word in name or word in docstring.lower() for word in query_words):
                        # Извлекаем код функции/класса
                        return ast.get_source_segment(content, node)
            
            # Если ничего не нашли — возвращаем первые 50 строк
            lines = content.split('\n')[:50]
            return '\n'.join(lines)
            
        except SyntaxError:
            return None
    
    def _rank_examples(
        self,
        examples: List[CodeExample],
        query: str
    ) -> List[CodeExample]:
        """Ранжирует примеры по качеству и релевантности."""
        for ex in examples:
            # Оценка качества кода
            ex.quality_score = self._estimate_quality(ex.code)
            
            # Комбинированный скор
            combined = (
                0.6 * ex.relevance_score +
                0.3 * ex.quality_score +
                0.1 * (1.0 if ex.source == "local" else 0.5)  # Предпочитаем локальные
            )
            ex.relevance_score = combined
        
        # Сортируем по комбинированному скору
        return sorted(examples, key=lambda x: x.relevance_score, reverse=True)
    
    def _estimate_quality(self, code: str) -> float:
        """Оценивает качество кода эвристически."""
        score = 0.5  # Базовый скор
        
        # Плюсы
        if 'def ' in code or 'class ' in code:
            score += 0.1
        if '"""' in code or "'''" in code:  # Docstring
            score += 0.1
        if ': ' in code and ' -> ' in code:  # Type hints
            score += 0.1
        if 'return ' in code:
            score += 0.05
        
        # Минусы
        if 'TODO' in code or 'FIXME' in code:
            score -= 0.1
        if 'pass' in code and code.count('pass') > 1:
            score -= 0.1
        if len(code) < 50:  # Слишком короткий
            score -= 0.1
        
        return max(0.0, min(1.0, score))
    
    def index_project(self, project_path: str, extensions: List[str] = [".py"]) -> int:
        """Индексирует проект для локального поиска.
        
        Args:
            project_path: Путь к проекту
            extensions: Расширения файлов
            
        Returns:
            Количество проиндексированных функций/классов
        """
        import ast
        
        indexed = 0
        project = Path(project_path)
        
        for ext in extensions:
            for file_path in project.rglob(f"*{ext}"):
                # Пропускаем служебные
                if any(skip in str(file_path) for skip in ['.venv', '__pycache__', '.git']):
                    continue
                
                try:
                    content = file_path.read_text(encoding='utf-8')
                    tree = ast.parse(content)
                    
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            code = ast.get_source_segment(content, node)
                            if code and len(code) > 30:
                                self._index_code(
                                    code=code,
                                    description=ast.get_docstring(node) or node.name,
                                    source="local",
                                    file_path=str(file_path),
                                    language="python"
                                )
                                indexed += 1
                                
                except Exception as e:
                    logger.debug(f"Failed to index {file_path}: {e}")
        
        logger.info(f"✅ Indexed {indexed} functions from {project_path}")
        return indexed
    
    def _index_code(
        self,
        code: str,
        description: str,
        source: str,
        file_path: Optional[str],
        language: str
    ):
        """Добавляет код в индекс."""
        # Уникальный ID на основе контента
        doc_id = hashlib.md5(code.encode()).hexdigest()
        
        # Embedding
        embedding = self.embedding_model.encode(f"{description}\n{code}").tolist()
        
        # Добавляем в ChromaDB
        self.collection.upsert(
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
    
    def add_from_history(self, task: str, code: str, success: bool):
        """Добавляет успешный код из истории.
        
        Вызывается после успешной генерации для обучения на своих результатах.
        """
        if success and len(code) > 50:
            self._index_code(
                code=code,
                description=task,
                source="history",
                file_path=None,
                language="python"
            )
            logger.debug(f"Added successful code to history index")
```

### 2. Интеграция в CoderAgent

```python
# agents/coder.py

from infrastructure.code_retrieval import CodeRetriever, CodeExample

class CoderAgent:
    def __init__(self, ...):
        self.retriever = CodeRetriever()
    
    def generate_code(self, plan: str, tests: str, context: str, ...) -> str:
        # Находим похожие примеры
        examples = self.retriever.find_similar(
            query=f"{plan}\n{context}",
            n=3,
            sources=["local", "history", "github"]
        )
        
        # Формируем промпт с примерами
        prompt = self._build_prompt_with_examples(
            plan=plan,
            tests=tests,
            context=context,
            examples=examples
        )
        
        response = self.llm.generate(prompt, num_predict=self.max_tokens)
        code = self._extract_code(response)
        
        # Если успешно — добавляем в историю
        if self._quick_validate(code):
            self.retriever.add_from_history(plan, code, success=True)
        
        return code
    
    def _build_prompt_with_examples(
        self,
        plan: str,
        tests: str,
        context: str,
        examples: List[CodeExample]
    ) -> str:
        """Строит промпт с примерами кода."""
        
        examples_str = "\n\n".join(ex.formatted for ex in examples)
        
        return f"""Generate Python code similar in STYLE to these examples:

{examples_str}

---

YOUR TASK:
{plan}

TESTS TO PASS:
```python
{tests}
```

CONTEXT:
{context}

RULES:
1. Follow the STYLE of the examples above
2. Use same naming conventions
3. Use same docstring format
4. Must pass the tests

CODE:"""
```

### 3. Периодическая индексация

```python
# infrastructure/indexer.py

import asyncio
from pathlib import Path
from infrastructure.code_retrieval import CodeRetriever

class ProjectIndexer:
    """Периодически индексирует проект для code retrieval."""
    
    def __init__(self, project_path: str, interval_minutes: int = 30):
        self.project_path = project_path
        self.interval = interval_minutes * 60
        self.retriever = CodeRetriever()
        self._task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Запускает периодическую индексацию."""
        self._task = asyncio.create_task(self._index_loop())
    
    async def stop(self):
        """Останавливает индексацию."""
        if self._task:
            self._task.cancel()
    
    async def _index_loop(self):
        """Цикл индексации."""
        while True:
            try:
                await asyncio.to_thread(
                    self.retriever.index_project,
                    self.project_path
                )
            except Exception as e:
                logger.error(f"Indexing failed: {e}")
            
            await asyncio.sleep(self.interval)
```

## Конфигурация

```toml
# config.toml

[code_retrieval]
# Включить code retrieval для few-shot примеров
enabled = true

# Источники для поиска
sources = ["local", "history", "github"]

# Количество примеров
num_examples = 3

# Модель для embeddings
embedding_model = "all-MiniLM-L6-v2"

# GitHub токен (опционально, для Code Search API)
# github_token = "ghp_..."

# Интервал переиндексации проекта (минуты)
reindex_interval = 30

# Минимальное качество примера (0-1)
min_quality = 0.5
```

## Зависимости

```bash
pip install sentence-transformers  # Embeddings
pip install chromadb               # Vector store
pip install PyGithub               # GitHub API (опционально)
```

## Метрики

| Метрика | Без retrieval | С retrieval |
|---------|---------------|-------------|
| Стиль соответствует проекту | ~50% | ~90% |
| Type hints корректны | ~70% | ~95% |
| Docstrings в нужном формате | ~60% | ~95% |
| Код компилируется сразу | ~60% | ~75% |

## Checklist

- [ ] Реализовать CodeRetriever
- [ ] Интеграция с ChromaDB
- [ ] Поиск в локальном проекте
- [ ] GitHub Code Search (опционально)
- [ ] Интеграция в CoderAgent
- [ ] История успешных генераций
- [ ] Периодическая индексация
- [ ] Конфигурация
- [ ] Тесты
