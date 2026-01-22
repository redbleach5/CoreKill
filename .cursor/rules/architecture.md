# Архитектура проекта

**Принцип:** Модульная архитектура через LangGraph с автоматическим выбором моделей и конфигурируемыми компонентами.

## Workflow (LangGraph)

```
START → intent_node → [greeting: END, else: planner_node]
planner_node → researcher_node → test_generator_node → coder_node → validator_node
validator_node → [passed: reflection_node, failed: debugger_node → fixer_node → validator_node]
reflection_node → critic_node → END
```

**Файлы:**
- `infrastructure/workflow_graph.py` — граф
- `infrastructure/workflow_nodes.py` — узлы (async + streaming)
- `infrastructure/workflow_edges.py` — условные переходы
- `infrastructure/workflow_state.py` — AgentState
- `infrastructure/workflow_config.py` — централизованная конфигурация
- `infrastructure/workflow_decorators.py` — декораторы @workflow_node и @streaming_node
- `infrastructure/workflow_types.py` — Protocol интерфейсы для типизации
- `infrastructure/streaming_agents_cache.py` — потокобезопасный кэш стриминговых агентов
- `infrastructure/event_store.py` — хранилище событий для стриминговых узлов

**Стриминговые узлы:**
- `stream_planner_node()` — планирование с thinking
- `stream_generator_node()` — генерация тестов с thinking
- `stream_coder_node()` — генерация кода с thinking
- `stream_debugger_node()` — анализ ошибок с thinking
- `stream_fixer_node()` — исправление кода с thinking
- `stream_reflection_node()` — рефлексия с thinking
- `stream_critic_node()` — критика с thinking

Используйте `get_streaming_node("coder")` для получения стриминговой версии.

## Агенты

### Синхронные агенты

| Агент | Файл | Назначение |
|-------|------|------------|
| Intent | `agents/intent.py` | Определение типа задачи (кэширование, калибровка confidence, определение языка, унифицированные промпты) |
| Planner | `agents/planner.py` | Создание плана |
| Researcher | `agents/researcher.py` | Сбор контекста (RAG + web) |
| TestGenerator | `agents/test_generator.py` | Генерация pytest тестов |
| Coder | `agents/coder.py` | Генерация кода |
| Debugger | `agents/debugger.py` | Анализ ошибок |
| Reflection | `agents/reflection.py` | Оценка качества |
| Critic | `agents/critic.py` | Критический анализ |
| Chat | `agents/chat.py` | Диалоговый режим |
| Memory | `agents/memory.py` | Долгосрочная память агентов |
| ConversationMemory | `agents/conversation.py` | История диалога в сессии |

### Стриминговые агенты (real-time `<think>` блоки)

| Агент | Файл | Назначение |
|-------|------|------------|
| StreamingPlanner | `agents/streaming_planner.py` | Планирование со стримингом |
| StreamingTestGenerator | `agents/streaming_test_generator.py` | Генерация тестов со стримингом |
| StreamingCoder | `agents/streaming_coder.py` | Генерация кода со стримингом |
| StreamingDebugger | `agents/streaming_debugger.py` | Отладка со стримингом |
| StreamingReflection | `agents/streaming_reflection.py` | Рефлексия со стримингом |
| StreamingCritic | `agents/streaming_critic.py` | Критика со стримингом |

**Особенности стриминговых агентов:**
- Асинхронные методы `*_stream()` возвращают `AsyncGenerator`
- Поддержка прерывания через `agent.interrupt()`
- События: `("thinking", sse)`, `("*_chunk", data)`, `("done", result)`
- Обратная совместимость через синхронные методы

## Dependency Injection

```python
from backend.dependencies import get_memory_agent, get_rag_system, shutdown_dependencies
from infrastructure.local_llm import create_llm_for_stage

# Singleton агенты (потокобезопасные)
memory = get_memory_agent()
rag = get_rag_system(collection_name="task_memory")  # Поддержка разных коллекций

# LLM с правильным таймаутом (модель выбирается автоматически)
llm = create_llm_for_stage(stage="coding", model=None)

# Graceful shutdown
shutdown_dependencies()
```

**Особенности:**
- Потокобезопасность через `threading.Lock`
- Параметризация RAGSystem (разные коллекции)
- Конфигурация из `config.toml`
- Корректное завершение работы

## Ключевые модули

| Модуль | Назначение |
|--------|------------|
| `infrastructure/local_llm.py` | Работа с Ollama (sync/async, JSON парсинг, ThreadPoolExecutor) |
| `infrastructure/connection_pool.py` | Асинхронный пул соединений Ollama (HTTP/2, connection pooling) |
| `infrastructure/model_router.py` | Выбор модели по задаче (кэш, fallback, динамическая проверка памяти) |
| `infrastructure/performance_metrics.py` | Метрики производительности |
| `infrastructure/task_checkpointer.py` | Сохранение состояния задач |
| `infrastructure/workflow_config.py` | Централизованная конфигурация workflow (стриминг, инкрементальное кодирование) |
| `infrastructure/streaming_agents_cache.py` | Потокобезопасный кэш стриминговых агентов |
| `infrastructure/workflow_decorators.py` | Декораторы @workflow_node и @streaming_node |
| `infrastructure/event_store.py` | Хранилище событий для стриминговых узлов |
| `infrastructure/circuit_breaker.py` | Circuit Breaker для защиты от каскадных сбоев |
| `backend/dependencies.py` | Dependency Injection (потокобезопасный, с graceful shutdown) |
| `backend/sse_manager.py` | Server-Sent Events |
| `utils/config.py` | Конфигурация из config.toml |

## Передовая архитектура

См. `future/ROADMAP_2026.md` для плана развития.

### Реализовано (Фазы 1-6)

| Технология | Описание | Ключевые файлы |
|------------|----------|----------------|
| Reasoning Models | Reasoning модели с chain-of-thought + стриминг thinking | `reasoning_stream.py`, `streaming_*.py` |
| Structured Output | Pydantic для Intent/Debugger/Reflection | `structured_helpers.py`, `agent_responses.py` |
| Compiler-in-the-Loop | Инкрементальная генерация | `incremental_coder.py`, `validate_code_quick()` |
| Code Retrieval | Few-shot примеры из кода | `code_retrieval.py` |
| Multi-Agent Debate | Несколько критиков | `specialized_reviewers.py`, `debate.py` |
| AST Analysis | Парсинг вместо LLM | `ast_analyzer.py` |

### Frontend UI

| Компонент | Описание | Файл |
|-----------|----------|------|
| ThinkingBlock | Отображение `<think>` блоков | `ThinkingBlock.tsx` |
| MetricsDashboard | Визуализация метрик | `MetricsDashboard.tsx` |
| UnderTheHoodPanel | Debug панель Phase 7 | `debug/UnderTheHoodPanel.tsx` |
| LiveLogsPanel | Real-time логи | `debug/LiveLogsPanel.tsx` |
| ToolCallsPanel | Отслеживание вызовов | `debug/ToolCallsPanel.tsx` |
| WorkflowGraph | Граф workflow | `debug/WorkflowGraph.tsx` |

### Будущее

| Технология | Описание | Документ |
|------------|----------|----------|
| Tree-sitter | Мультиязычный парсинг | `future/tree_sitter_multilang.md` |

### Принципы архитектуры

- Reasoning models вместо prompt engineering
- Structured output вместо хрупкого парсинга
- Немедленная валидация вместо отложенной
- Примеры кода вместо инструкций
- AST для структурного анализа, LLM для понимания

### Ключевые компоненты

```
infrastructure/
├── reasoning_stream.py      # Стриминг <think> блоков
├── reasoning_utils.py       # Парсинг thinking
├── model_router.py          # Выбор модели по сложности
├── code_retrieval.py        # Few-shot примеры (Phase 4)
├── debate.py                # Multi-Agent Debate (Phase 5)
├── ast_analyzer.py          # AST Analysis (Phase 6)
├── workflow_nodes.py        # Интеграция всех фаз
├── workflow_config.py       # Централизованная конфигурация
├── workflow_decorators.py   # Декораторы для узлов
├── workflow_types.py        # Protocol интерфейсы
├── streaming_agents_cache.py # Потокобезопасный кэш агентов
├── event_store.py           # Хранилище событий
└── circuit_breaker.py       # Circuit Breaker

agents/
├── streaming_*.py           # 6 стриминговых агентов
├── incremental_coder.py     # Compiler-in-the-Loop
├── specialized_reviewers.py # Security/Performance/Correctness
├── chat.py                  # + AST анализ проекта
├── coder.py                 # + интеграция CodeRetriever
└── intent.py                # Structured output + кэширование + калибровка

utils/
├── structured_helpers.py    # generate_with_fallback()
└── validation.py            # validate_code_quick()

models/
└── agent_responses.py       # Pydantic модели
```