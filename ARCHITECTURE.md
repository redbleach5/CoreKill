# Архитектура Cursor Killer

## Обзор

Cursor Killer — локальная многоагентная система для генерации кода с гибридным UX, встроенной IDE и умным выбором моделей. Использует LangGraph для workflow и Ollama для LLM.

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
│       │   ├── chat/       # Компоненты чата
│       │   │   ├── ChatInput.tsx    # Поле ввода
│       │   │   ├── MessageList.tsx  # Список сообщений
│       │   │   └── WelcomeScreen.tsx
│       │   ├── header/     # Компоненты шапки
│       │   │   ├── AppHeader.tsx    # Главный header
│       │   │   └── QuickSettings.tsx
│       │   ├── ChatHistory.tsx  # Сайдбар истории диалогов
│       │   ├── IDEPanel.tsx     # Встроенная IDE
│       │   ├── CodeEditor.tsx   # Редактор кода
│       │   └── SettingsPanel.tsx
│       ├── hooks/
│       │   └── useAgentStream.ts  # SSE hook
│       ├── types/
│       │   └── chat.ts      # TypeScript типы
│       └── constants/
│           └── sse.ts       # SSE константы
├── infrastructure/         # Инфраструктура
│   ├── local_llm.py        # Интеграция с Ollama
│   ├── model_router.py     # SmartModelRouter — выбор модели по сложности
│   ├── rag.py              # RAG с ChromaDB
│   ├── web_search.py       # Веб-поиск
│   ├── task_checkpointer.py # Сохранение прогресса задач
│   ├── workflow_state.py   # State схема LangGraph
│   ├── workflow_nodes.py   # Узлы графа
│   ├── workflow_edges.py   # Условные переходы
│   └── workflow_graph.py   # Граф LangGraph
├── utils/
│   ├── config.py           # Конфигурация из config.toml
│   ├── model_checker.py    # Сканирование моделей Ollama
│   └── ...
├── config.toml             # Конфигурация
└── output/
    └── conversations/      # Сохранённые диалоги (JSON)
```

## Frontend архитектура

### Компоненты

```
App.tsx
├── AppHeader              # Шапка: лого, режимы, модель, настройки
├── ChatHistory            # Сайдбар слева: история диалогов
│   ├── Поиск
│   ├── Список диалогов
│   └── Удаление (модальное окно)
├── Chat View              # Основная область
│   ├── MessageList        # Сообщения с markdown
│   └── ChatInput          # Поле ввода (фиксировано внизу)
└── IDEPanel               # Встроенная IDE (split/ide режим)
    ├── Project Menu       # Меню: открыть папку, индексация
    ├── File Tabs          # Табы файлов
    ├── Actions            # Выполнить, копировать, скачать
    └── CodeEditor         # Редактор с подсветкой
```

### Layout режимы

- **chat** — только чат (история слева)
- **ide** — только IDE
- **split** — чат + IDE (50/50)

Режим автоматически синхронизируется с режимом агента:
- `mode=chat` → layout=chat
- `mode=code` → layout=split
- `mode=auto` → пользователь выбирает, авто-split при генерации кода

## Гибридная система режимов

### Режимы взаимодействия

```
┌─────────────────────────────────────────────────────────┐
│                    stream_task_results                   │
│                                                          │
│  mode=chat ──────────────────────────────► run_chat_stream │
│             (ЯВНЫЙ выбор, НЕ переключается на code)     │
│                                                          │
│  mode=code ──────────────────────────────► run_workflow_stream │
│             (ЯВНЫЙ выбор, всегда полный TDD workflow)   │
│                                                          │
│  mode=auto ──► IntentAgent.is_greeting_fast() ──► chat  │
│           │                                              │
│           └─► chat_keywords & !code_keywords ──► chat   │
│           │                                              │
│           └─► code_keywords? ──► code                   │
│           │                                              │
│           └─► LLM determine_intent() ──► recommended    │
└─────────────────────────────────────────────────────────┘
```

### Ключевые слова для определения режима (auto)

| Режим | Ключевые слова |
|-------|----------------|
| **chat** | объясни, расскажи, что такое, как работает, почему, зачем, посоветуй |
| **code** | напиши, создай, сделай, реализуй, функци, класс, исправ, debug |

### ChatAgent — ограничения режима диалога

В режиме `chat` ChatAgent:
- **Делает**: объясняет концепции, обсуждает архитектуру, даёт советы, показывает короткие примеры (до 20-30 строк)
- **НЕ делает**: генерирует полноценные программы, скрипты, тесты, TDD workflow

При запросе на генерацию кода в режиме диалога — предлагает переключиться в режим "Генерация кода".

### Умный выбор моделей (SmartModelRouter)

```python
# Логика выбора модели по сложности:
SIMPLE  → минимально подходящая модель (быстрота)   → phi3:mini, gemma:1b
MEDIUM  → баланс качества и скорости                → qwen2.5-coder:7b
COMPLEX → максимальное качество                     → 13B+, 30B+, 70B+
```

## История диалогов

### Backend (ConversationMemory)

```python
# agents/conversation.py
ConversationMemory:
  - get_or_create_conversation(id)
  - add_message(conversation_id, role, content)
  - get_context(conversation_id, max_messages)
  - _summarize_conversation()  # Автосуммаризация при превышении лимита
  - Сохранение в output/conversations/{id}.json
```

### Frontend (ChatHistory)

```typescript
// components/ChatHistory.tsx
- Список диалогов из /api/conversations
- Поиск по title/preview
- Клик → загрузка из /api/conversations/{id}
- Удаление с модальным подтверждением
- Сворачиваемый сайдбар
```

## IDE Panel

### Структура

```
┌─────────────────────────────────────────────────────┐
│ [📁] [🐍 main.py] [📜 utils.js] [+] │ [▶] [📋] [⬇] [↺] │
├─────────────────────────────────────────────────────┤
│  1 │ def hello():                                   │
│  2 │     print("Hello")                             │
│  3 │                                                │
└─────────────────────────────────────────────────────┘
```

### Функции

- **Меню проекта** [📁]: открыть папку, индексировать, переиндексировать
- **Табы файлов**: многофайловый режим, закрытие
- **Действия**: выполнить, копировать, скачать, сбросить
- **Редактор**: подсветка Python, номера строк

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

## SSE Events

```typescript
// Frontend получает события:
event: stage_start  → { stage: "intent", message: "..." }
event: stage_end    → { stage: "intent", result: {...} }
event: complete     → { results: {...}, metrics: {...} }
event: error        → { error_message: "..." }
```

## API Endpoints

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/api/stream` | GET | SSE streaming (task, mode, model) |
| `/api/settings` | GET | Текущие настройки |
| `/api/models` | GET | Список моделей + рекомендации |
| `/api/conversations` | GET | Список диалогов |
| `/api/conversations/{id}` | GET | Получить диалог |
| `/api/conversations/{id}` | DELETE | Удалить диалог |
| `/api/index` | POST | Индексировать проект |

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
| `[persistence]` | Сохранение задач |
| `[context_engine]` | Индексация кодовой базы |

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
