# Архитектура Cursor Killer

## Обзор

Cursor Killer — локальная многоагентная система для генерации кода с гибридным UX и умным выбором моделей. Использует LangGraph для workflow и Ollama для LLM.

## Ключевые принципы

- **Dependency Inversion** — зависимости инжектируются через `backend/dependencies.py`
- **Явные контракты** — каждый слой имеет чёткий интерфейс
- **UI не знает о реализации агентов** — frontend общается только через API
- **Любая фича отключаема** — через `config.toml` или переменные окружения
- **Масштабируемость** — поддержка моделей от 1B до 405B

## Структура проекта

```
cursor-killer/
├── agents/                 # Агенты системы
│   ├── intent.py           # Определение намерения + сложности
│   ├── chat.py             # Агент для диалогов (chat режим)
│   ├── conversation.py     # Управление историей диалогов
│   ├── planner.py          # Планирование задачи
│   ├── researcher.py       # Сбор контекста (RAG + веб)
│   ├── test_generator.py   # Генерация тестов (TDD)
│   ├── coder.py            # Генерация кода
│   ├── debugger.py         # Self-healing
│   ├── critic.py           # Критический анализ
│   ├── reflection.py       # Рефлексия и оценка
│   └── memory.py           # Система памяти (RAG)
├── backend/                # FastAPI backend
│   ├── api.py              # Главное приложение
│   ├── dependencies.py     # Dependency Injection
│   ├── types.py            # Типы и модели данных
│   ├── sse_manager.py      # Управление SSE
│   └── routers/
│       └── agent.py        # API endpoints + роутинг режимов
├── frontend/               # React + TypeScript + Vite
│   └── src/
│       ├── App.tsx         # Главный компонент
│       ├── components/
│       │   ├── AgentProgress.tsx  # Прогресс workflow
│       │   └── ...
│       └── hooks/
│           └── useAgentStream.ts  # SSE hook
├── infrastructure/         # Инфраструктура
│   ├── local_llm.py        # Интеграция с Ollama
│   ├── model_router.py     # SmartModelRouter — выбор модели по сложности
│   ├── rag.py              # RAG с ChromaDB
│   ├── web_search.py       # Веб-поиск
│   ├── workflow_state.py   # State схема LangGraph
│   ├── workflow_nodes.py   # Узлы графа
│   ├── workflow_edges.py   # Условные переходы
│   └── workflow_graph.py   # Граф LangGraph
├── utils/
│   ├── config.py           # Конфигурация из config.toml
│   ├── model_checker.py    # Сканирование моделей Ollama
│   └── ...
└── config.toml             # Конфигурация
```

## Гибридная система режимов

### Режимы взаимодействия

```
┌─────────────────────────────────────────────────────────┐
│                    stream_task_results                   │
│                                                          │
│  mode=auto ──► IntentAgent.is_greeting_fast() ──► chat  │
│           │                                              │
│           └─► code_keywords? ──► code                   │
│           │                                              │
│           └─► LLM determine_intent() ──► recommended    │
│                                                          │
│  mode=chat ──────────────────────────────► run_chat_stream │
│  mode=code ──────────────────────────────► run_workflow_stream │
└─────────────────────────────────────────────────────────┘
```

### Умный выбор моделей (SmartModelRouter)

```python
# Логика выбора модели по сложности:
SIMPLE  → минимально подходящая модель (быстрота)   → phi3:mini, gemma:1b
MEDIUM  → баланс качества и скорости                → qwen2.5-coder:7b
COMPLEX → максимальное качество                     → 13B+, 30B+, 70B+
```

**Определение сложности:**
- `IntentAgent._estimate_complexity_heuristic()` — по ключевым словам
- `IntentAgent.determine_intent()` — через LLM
- Технические термины (async, decorator, etc.) → MEDIUM
- Системные задачи (игра, приложение) → COMPLEX

**Hardware лимиты:**
```toml
[hardware]
max_model_vram_gb = 0       # 0 = без лимита
allow_heavy_models = true   # 30-70B модели
allow_ultra_models = false  # 100B+ модели
```

## Workflow Code режима

```
Пользовательский запрос
    ↓
[Intent Agent] → greeting/help? → END (быстрый ответ)
    ↓
[Planner Agent] → план выполнения
    ↓
[Researcher Agent] → Codebase Index → RAG → Web Search
    ↓
[Test Generator] → pytest тесты (TDD)
    ↓
[Coder Agent] → генерация кода
    ↓
[Validator] → pytest, mypy, bandit
    ↓ (ошибки?)
[Debugger] ← [Fixer] ← [Validator] (до 5 итераций)
    ↓
[Reflection Agent] → оценка + сохранение в память
    ↓
[Critic Agent] → критический анализ
    ↓
Результат
```

## Codebase Indexing (Context Engine)

При указании `project_path` система автоматически индексирует кодовую базу:

```
project_path указан?
    ↓ да
[ContextEngine] → индексация файлов по расширениям
    ↓
[CodeChunker] → разбиение на чанки (классы, функции)
    ↓
[RelevanceScorer] → BM25-подобная оценка релевантности
    ↓
[ContextComposer] → сборка контекста в пределах лимита токенов
    ↓
Релевантный контекст кодовой базы → Researcher
```

**Настройки в config.toml:**
```toml
[context_engine]
enabled = true
max_context_tokens = 4000
max_chunk_tokens = 500
default_extensions = [".py"]
```

**API параметры:**
- `project_path` — путь к корню проекта
- `file_extensions` — расширения файлов (через запятую)

## Chat режим

```
Пользовательский запрос
    ↓
[ConversationMemory] → получить историю диалога
    ↓
[ChatAgent] → генерация ответа (лёгкая модель)
    ↓
[ConversationMemory] → сохранить ответ
    ↓
Результат (SSE: chat stage)
```

**Суммаризация:** При превышении `max_context_messages` старые сообщения автоматически суммаризируются LLM.

## ModelInfo и оценка качества

```python
@dataclass
class ModelInfo:
    name: str
    parameter_size: str      # "7B", "13B", "70B"
    estimated_quality: float # 0.0-1.0
    is_coder: bool
    
    @property
    def tier(self) -> str:   # light, medium, heavy, ultra
    
    @property
    def estimated_vram_gb(self) -> float
```

**Динамическая оценка качества:**
```python
# Для неизвестных размеров вычисляется автоматически:
# 25B → ~0.87, 45B → ~0.92, 180B → ~0.98
```

## SSE Events

```typescript
// Frontend получает события:
event: stage_start  → { stage: "intent", message: "..." }
event: stage_end    → { stage: "intent", result: {...} }
event: complete     → { results: {...}, metrics: {...} }
event: error        → { error_message: "..." }
```

## Конфигурация

### config.toml секции

| Секция | Описание |
|--------|----------|
| `[default]` | Основные настройки (модель, температура) |
| `[llm]` | Настройки LLM (токены) |
| `[interaction]` | Режимы (default_mode, chat_model) |
| `[hardware]` | Лимиты (VRAM, heavy/ultra модели) |
| `[quality]` | Метрики качества |
| `[web_search]` | Веб-поиск |
| `[rag]` | ChromaDB настройки |

## API Endpoints

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/api/stream` | GET | SSE streaming (task, mode, model) |
| `/api/settings` | GET | Текущие настройки |
| `/api/models` | GET | Список моделей + рекомендации |
| `/api/conversations` | GET | Список диалогов |
| `/api/conversations/new` | POST | Новый диалог |

## Масштабирование

### Добавление новых моделей

Модели подхватываются автоматически через `ollama.list()`. Оценка качества вычисляется динамически по размеру.

### Добавление нового агента

1. Создать `agents/new_agent.py`
2. Добавить узел в `infrastructure/workflow_nodes.py`
3. Добавить в граф `infrastructure/workflow_graph.py`

### Добавление нового режима

1. Добавить в `InteractionMode` enum
2. Создать `run_<mode>_stream()` функцию
3. Добавить роутинг в `stream_task_results()`

## Безопасность

- Rate Limiting (middleware)
- CORS (ограниченные origins)
- Input Validation (Pydantic)
- Error Handling (не раскрывает внутренности)

## Тестирование

```bash
pytest tests/                    # Все тесты
pytest tests/ --cov=agents       # С покрытием
pytest tests/test_intent.py -v   # Конкретный файл
```

## Документация

- [README.md](README.md) — быстрый старт
- [DEPLOYMENT.md](DEPLOYMENT.md) — развёртывание
- [future/](future/) — планы развития
- `/docs` — Swagger UI (при запущенном backend)
