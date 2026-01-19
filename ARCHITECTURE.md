# Архитектура Cursor Killer

## Обзор

Cursor Killer — это локальная многоагентная система для генерации и редактирования кода. Система использует LangGraph для управления workflow и Ollama для локальных LLM моделей.

## Структура проекта

```
cursor-killer/
├── agents/              # Агенты системы
│   ├── intent.py       # Определение намерения пользователя
│   ├── planner.py      # Планирование выполнения задачи
│   ├── researcher.py   # Сбор контекста (RAG + веб)
│   ├── test_generator.py  # Генерация тестов (TDD)
│   ├── coder.py        # Генерация кода
│   ├── debugger.py     # Анализ ошибок и self-healing
│   ├── critic.py       # Критический анализ кода
│   ├── reflection.py   # Рефлексия и оценка
│   └── memory.py       # Система памяти (RAG)
├── backend/            # FastAPI backend
│   ├── api.py         # Главное приложение
│   ├── dependencies.py # Управление зависимостями (DI)
│   ├── error_handler.py # Обработка ошибок и retry логика
│   ├── validators.py   # Валидация входных данных
│   ├── types.py       # Типы и модели данных
│   ├── sse_manager.py # Управление SSE событиями
│   ├── sse_helpers.py # Вспомогательные функции SSE
│   ├── middleware/
│   │   ├── log_filter.py
│   │   └── rate_limiter.py  # Rate limiting для защиты
│   └── routers/
│       └── agent.py    # API endpoints
├── frontend/          # React + TypeScript + Vite
│   └── src/
│       ├── App.tsx     # Главный компонент
│       ├── components/ # React компоненты
│       ├── hooks/      # React хуки (useAgentStream)
│       └── lib/        # Утилиты
├── infrastructure/    # Инфраструктура
│   ├── local_llm.py    # Интеграция с Ollama
│   ├── model_router.py # Маршрутизация моделей
│   ├── prompt_enhancer.py # Улучшение промптов
│   ├── rag.py         # Retrieval-Augmented Generation
│   ├── web_search.py  # Веб-поиск
│   ├── cache.py       # Кэширование результатов
│   ├── workflow_state.py  # State схема для LangGraph
│   ├── workflow_nodes.py  # Узлы графа
│   ├── workflow_edges.py  # Условные переходы
│   └── workflow_graph.py  # Граф LangGraph
├── utils/            # Утилиты
│   ├── config.py      # Конфигурация (TOML)
│   ├── env_config.py  # Конфигурация из переменных окружения
│   ├── logger.py      # Логирование
│   ├── model_checker.py # Проверка доступности моделей
│   ├── token_counter.py # Подсчёт токенов
│   ├── validation.py  # Валидация
│   └── artifact_saver.py # Сохранение артефактов
├── tests/            # Тесты
├── config.toml       # Конфигурация (TOML)
├── .env.example      # Пример переменных окружения
└── requirements.txt  # Python зависимости
```

## Основные компоненты

### 1. Агенты (agents/)

Каждый агент отвечает за определённый этап выполнения задачи:

- **IntentAgent**: Определяет тип намерения пользователя (create, modify, debug, etc.)
- **PlannerAgent**: Создаёт план выполнения задачи
- **ResearcherAgent**: Собирает контекст из RAG и веб-поиска
- **TestGeneratorAgent**: Генерирует pytest тесты (TDD подход)
- **CoderAgent**: Генерирует рабочий код на основе тестов
- **DebuggerAgent**: Анализирует ошибки и исправляет код (self-healing)
- **CriticAgent**: Проводит критический анализ кода
- **ReflectionAgent**: Оценивает качество результатов
- **MemoryAgent**: Управляет памятью и RAG

### 2. Backend (backend/)

FastAPI приложение с поддержкой:

- **API Endpoints**: REST API для управления задачами
- **SSE Streaming**: Real-time стриминг прогресса
- **Dependency Injection**: Управление зависимостями
- **Error Handling**: Обработка ошибок и retry логика
- **Rate Limiting**: Защита от DoS атак
- **Validation**: Валидация входных данных
- **CORS**: Безопасная работа с frontend

### 3. Frontend (frontend/)

React приложение с:

- **Real-time UI**: Обновление интерфейса через SSE
- **Chat Interface**: Интерфейс чата для взаимодействия
- **Progress Tracking**: Отслеживание прогресса выполнения
- **Code Display**: Красивый вывод сгенерированного кода
- **Settings Panel**: Настройка параметров

### 4. Инфраструктура (infrastructure/)

- **LocalLLM**: Интеграция с Ollama
- **ModelRouter**: Маршрутизация запросов к моделям
- **PromptEnhancer**: Динамическое улучшение промптов
- **RAG**: Retrieval-Augmented Generation с ChromaDB
- **WebSearch**: Интеграция с веб-поиском
- **Cache**: Кэширование результатов
- **LangGraph**: Workflow управление

## Workflow выполнения

```
Пользовательский запрос
    ↓
[Intent Agent] → Определение намерения
    ↓
[Planner Agent] → Создание плана
    ↓
[Researcher Agent] → Сбор контекста
    ↓
[Test Generator] → Генерация тестов
    ↓
[Coder Agent] → Генерация кода
    ↓
[Validator] → Проверка (pytest, mypy, bandit)
    ↓
[Debugger Agent] → Анализ ошибок (до 3 итераций)
    ↓
[Reflection Agent] → Оценка качества
    ↓
[Critic Agent] → Критический анализ
    ↓
Результат пользователю
```

## Безопасность

### Защита от атак

1. **Rate Limiting**: Ограничение количества запросов
2. **CORS**: Ограничение origins
3. **Input Validation**: Валидация входных данных
4. **Trusted Hosts**: Проверка хостов
5. **Error Handling**: Безопасная обработка ошибок

### Конфигурация

- Используйте `.env` для production
- Переменные окружения переопределяют `config.toml`
- Чувствительные данные не хранятся в коде

## Производительность

### Оптимизации

1. **Кэширование**: Результаты кэшируются с TTL
2. **Connection Pooling**: Пулинг соединений с Ollama
3. **Async/Await**: Асинхронная обработка
4. **Lazy Loading**: Ленивая загрузка компонентов

### Масштабируемость

1. **Stateless Backend**: Backend не хранит состояние
2. **Horizontal Scaling**: Возможность масштабирования
3. **Load Balancing**: Поддержка load balancer

## Тестирование

### Покрытие

- Unit тесты для агентов
- Integration тесты для workflow
- E2E тесты для API

### Запуск

```bash
# Все тесты
pytest tests/

# С покрытием
pytest tests/ --cov=agents --cov=backend --cov=infrastructure

# Конкретный тест
pytest tests/test_intent.py::TestIntentAgent::test_init
```

## Развёртывание

### Development

```bash
python run.py
```

### Production

```bash
# Установить зависимости
pip install -r requirements.txt

# Установить frontend
cd frontend && npm install && npm run build

# Запустить backend
uvicorn backend.api:app --host 0.0.0.0 --port 8000 --workers 4

# Запустить frontend (nginx или другой веб-сервер)
```

## Расширение

### Добавление нового агента

1. Создайте класс в `agents/new_agent.py`
2. Наследуйте от базового класса
3. Реализуйте метод `execute()`
4. Добавьте в workflow

### Добавление нового endpoint

1. Создайте функцию в `backend/routers/agent.py`
2. Используйте декоратор `@router.get()` или `@router.post()`
3. Добавьте валидацию через Pydantic модели

## Документация

- [README.md](README.md) - Быстрый старт
- [ARCHITECTURE.md](ARCHITECTURE.md) - Эта архитектура
- [API Documentation](http://localhost:8000/docs) - Swagger UI

## Лицензия

MIT
