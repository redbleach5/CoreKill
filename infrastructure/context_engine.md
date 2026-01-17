# Context Engine v0.1 - API Документация

## Проблема, которую решает

Небольшие модели (7B) не могут обработать большие кодовые базы (50-500K токенов) в контексте (4-8K). Простой RAG не учитывает структуру кода и зависимости.

## Решение v0.1

Минимальная реализация, которая:
- **Умно разбивает код** на чанки с учётом структуры (классы, функции)
- **Оценивает релевантность** чанков к запросу (BM25-подобная оценка)
- **Собирает оптимальный контекст** в пределах лимита токенов
- **Кэширует индексы** проектов для быстрого доступа

## API

### ContextEngine (основной класс)

```python
from infrastructure.context_engine import ContextEngine

# Инициализация
engine = ContextEngine(
    max_context_tokens=4000,  # Максимальный размер контекста
    max_chunk_tokens=500,      # Максимальный размер чанка
    cache_dir=None             # Директория для кэша (по умолчанию .context_cache)
)

# Индексация проекта (один раз)
index = engine.index_project(
    project_path="/path/to/project",
    extensions=['.py']  # Расширения файлов для индексации
)

# Получение контекста для запроса
context = engine.get_context(
    query="как работает аутентификация",
    project_path="/path/to/project",
    extensions=['.py']
)
```

### CodeChunker (низкоуровневый API)

```python
from infrastructure.context_engine import CodeChunker

chunker = CodeChunker(max_chunk_tokens=500)
chunks = chunker.chunk_file("config.py", code_content)
# Возвращает List[CodeChunk]
```

### RelevanceScorer (низкоуровневый API)

```python
from infrastructure.context_engine import RelevanceScorer

scorer = RelevanceScorer()
scored = scorer.score_chunks("config manager", chunks)
# Возвращает List[ScoredChunk], отсортированный по релевантности
```

### ContextComposer (низкоуровневый API)

```python
from infrastructure.context_engine import ContextComposer

composer = ContextComposer(max_tokens=4000)
context = composer.compose(scored_chunks, query="config manager")
# Возвращает собранный контекст в пределах лимита токенов
```

## Примеры использования

### Базовое использование

```python
from infrastructure.context_engine import ContextEngine

engine = ContextEngine()

# Получить контекст для запроса
context = engine.get_context(
    query="как работает аутентификация",
    project_path="./my_project"
)

print(context)
# Вывод: отформатированный контекст с релевантными чанками кода
```

### Интеграция с Researcher

```python
from infrastructure.context_engine import ContextEngine
from agents.researcher import ResearcherAgent

# В ResearcherAgent можно добавить использование Context Engine
class ResearcherAgent:
    def __init__(self):
        self.rag = RAGSystem()
        self.context_engine = ContextEngine()  # Новый компонент
    
    def research(self, query: str, project_path: Optional[str] = None):
        context_parts = []
        
        # Если есть проект, используем Context Engine
        if project_path:
            code_context = self.context_engine.get_context(query, project_path)
            if code_context:
                context_parts.append("[Контекст кода]")
                context_parts.append(code_context)
        
        # Дополняем RAG-поиском
        rag_context = self.rag.get_relevant_context(query)
        if rag_context:
            context_parts.append(rag_context)
        
        return "\n\n".join(context_parts)
```

## Ограничения v0.1

- **Только Python**: Разбор кода работает только для Python (поиск классов/функций через regex)
- **Простая оценка**: BM25-подобная оценка без семантических embeddings
- **Базовое кэширование**: Кэш только в памяти, не персистентный
- **Нет AST**: Не использует AST парсинг (слишком сложно для v0.1)

## Расширяемость

Модуль спроектирован как независимый и расширяемый:
- Можно добавить поддержку других языков (JavaScript, TypeScript)
- Можно интегрировать семантические embeddings для улучшения оценки
- Можно добавить персистентный кэш (SQLite/JSON файлы)
- Можно добавить AST парсинг для более точного разбора структуры

## Тестирование

```bash
pytest tests/test_context_engine.py -v
```
