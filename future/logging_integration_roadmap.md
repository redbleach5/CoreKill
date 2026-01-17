# Дорожная карта интеграции системы логирования

## 📋 Обзор

Этот документ описывает дальнейшие шаги по интеграции новой системы логирования (`infrastructure/logging`) в существующий код проекта.

**Текущий статус:**
- ✅ Новая система логирования реализована
- ✅ Совместимый интерфейс создан (`utils/logger.py`)
- ✅ Все существующие файлы работают без изменений

**Следующие шаги:**
- 🔄 Постепенная миграция на прямое использование новой системы
- 🔄 Интеграция с UI через SSE стриминг
- 🔄 Расширение использования структурированных событий

---

## 🎯 Приоритет 1: Backend — SSE стриминг логов

### Цель
Интегрировать `LogStreamAdapter` в FastAPI backend для стриминга логов через SSE.

### Файлы для изменения
- `backend/api.py` — инициализация LogManager с UI конфигурацией
- `backend/routers/agent.py` — использование LogManager для логирования workflow
- Новый endpoint: `backend/routers/logs.py` — SSE endpoint для стриминга логов

### Шаги реализации

#### 1. Инициализация LogManager в backend

**Файл:** `backend/api.py`

```python
from infrastructure.logging import LogManager, LoggingConfig
from utils.logger import set_log_manager

# При старте приложения
@app.on_event("startup")
async def startup_event():
    """Инициализация системы логирования для UI."""
    config = LoggingConfig.for_ui()  # С памятью для стриминга
    log_manager = LogManager(config)
    set_log_manager(log_manager)  # Устанавливаем глобальный экземпляр
```

#### 2. Создание SSE endpoint для логов

**Новый файл:** `backend/routers/logs.py`

```python
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from infrastructure.logging import LogStreamAdapter, create_sse_event
from utils.logger import get_log_manager

router = APIRouter(prefix="/api", tags=["logs"])

@router.get("/logs/stream/{task_id}")
async def stream_logs(task_id: str):
    """SSE endpoint для стриминга логов задачи.
    
    Args:
        task_id: ID задачи для фильтрации логов
        
    Returns:
        SSE поток с событиями логирования
    """
    log_manager = get_log_manager()
    adapter = LogStreamAdapter(log_manager)
    
    async def event_generator():
        async for log_event in adapter.stream_events(task_id=task_id):
            yield create_sse_event(log_event)
        adapter.stop()
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
```

**Добавить в:** `backend/api.py`
```python
from backend.routers import logs
app.include_router(logs.router)
```

#### 3. Интеграция логирования в workflow

**Файл:** `backend/routers/agent.py`

Обновить `run_workflow_stream()` для использования LogManager:

```python
from utils.logger import get_log_manager
from infrastructure.logging.models import LogSource, LogStage

async def run_workflow_stream(...):
    task_id = str(uuid.uuid4())
    log_manager = get_log_manager()
    
    try:
        # Шаг 1: Определение намерения
        log_manager.log_stage_start(
            task_id=task_id,
            stage=LogStage.INTENT,
            message="Определяю намерение...",
            source=LogSource.AGENT
        )
        
        intent_result = _intent_agent.determine_intent(task)
        
        log_manager.log_stage_end(
            task_id=task_id,
            stage=LogStage.INTENT,
            message=f"Намерение определено: {intent_result.type}",
            source=LogSource.AGENT,
            payload={"type": intent_result.type, "confidence": intent_result.confidence}
        )
        
        # Продолжить для остальных этапов...
        
    except Exception as e:
        log_manager.log_error(
            message=f"Ошибка выполнения workflow: {str(e)}",
            source=LogSource.SYSTEM,
            task_id=task_id,
            error=e
        )
```

### Преимущества
- Логи доступны в UI в реальном времени
- Структурированные события для лучшей фильтрации
- История логов сохраняется в памяти для анализа

---

## 🎯 Приоритет 2: Агенты — Использование структурированных событий

### Цель
Обновить агенты для использования новой системы логирования с поддержкой stage, source, task_id.

### Файлы для изменения
- `agents/intent.py`
- `agents/planner.py`
- `agents/researcher.py`
- `agents/test_generator.py`
- `agents/coder.py`
- `agents/reflection.py`
- `agents/memory.py`

### Стратегия миграции

#### Вариант 1: Добавить task_id в методы агентов (рекомендуется)

**Пример:** `agents/intent.py`

```python
from utils.logger import get_log_manager
from infrastructure.logging.models import LogSource, LogStage

class IntentAgent:
    def determine_intent(
        self, 
        user_query: str,
        task_id: Optional[str] = None  # Добавляем опциональный task_id
    ) -> IntentResult:
        """Определяет намерение пользователя из запроса.
        
        Args:
            user_query: Текст запроса пользователя
            task_id: ID задачи для логирования (опционально)
            
        Returns:
            IntentResult с типом намерения, уверенностью и описанием
        """
        log_manager = get_log_manager()
        
        # Логируем начало этапа
        if task_id:
            log_manager.log_stage_start(
                task_id=task_id,
                stage=LogStage.INTENT,
                message=f"Определяю намерение для запроса: {user_query[:60]}...",
                source=LogSource.AGENT,
                payload={"query": user_query[:100]}
            )
        
        # ... логика определения намерения ...
        
        # Логируем результат
        if task_id:
            log_manager.log_stage_end(
                task_id=task_id,
                stage=LogStage.INTENT,
                message=f"Намерение определено: {intent_result.type} (уверенность: {intent_result.confidence:.2f})",
                source=LogSource.AGENT,
                payload={
                    "type": intent_result.type,
                    "confidence": intent_result.confidence
                }
            )
        
        return intent_result
```

#### Вариант 2: Использовать контекст задачи (альтернатива)

Создать класс `TaskContext` для передачи контекста:

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class TaskContext:
    """Контекст задачи для логирования."""
    task_id: str
    iteration: Optional[int] = None
    
    def with_iteration(self, iteration: int) -> 'TaskContext':
        """Создаёт новый контекст с итерацией."""
        return TaskContext(task_id=self.task_id, iteration=iteration)
```

Использование:
```python
def determine_intent(self, user_query: str, context: Optional[TaskContext] = None) -> IntentResult:
    if context:
        log_manager.log_stage_start(
            task_id=context.task_id,
            stage=LogStage.INTENT,
            ...
        )
```

### Порядок обновления агентов

1. **IntentAgent** — самый простой, без зависимостей
2. **PlannerAgent** — использует IntentResult
3. **ResearcherAgent** — использует результаты планирования
4. **TestGeneratorAgent** — независимый
5. **CoderAgent** — использует тесты и план
6. **ReflectionAgent** — анализирует результаты
7. **MemoryAgent** — использует результаты рефлексии

### Преимущества
- Логи привязаны к задачам
- Легче отслеживать выполнение workflow
- Структурированные данные для анализа

---

## 🎯 Приоритет 3: CLI — Улучшенное логирование

### Цель
Обновить CLI для использования структурированных событий с task_id.

### Файл для изменения
- `cli.py`

### Шаги реализации

```python
import uuid
from utils.logger import get_log_manager
from infrastructure.logging.models import LogSource, LogStage

def main() -> None:
    """Основной цикл CLI."""
    log_manager = get_log_manager()
    
    log_manager.log_info(
        message="=" * 70,
        source=LogSource.SYSTEM
    )
    log_manager.log_info(
        message="🚀 Локальная многоагентная система генерации кода",
        source=LogSource.SYSTEM
    )
    
    # ... инициализация агентов ...
    
    while True:
        try:
            user_task = input("\n📝 Введите задачу (или 'quit' для выхода): ").strip()
            
            if not user_task or user_task.lower() in ["quit", "exit", "q"]:
                log_manager.log_info("👋 До свидания!", source=LogSource.SYSTEM)
                break
            
            # Генерируем task_id для этой задачи
            task_id = str(uuid.uuid4())
            
            log_manager.log_info(
                message=f"Обработка задачи: {user_task}",
                source=LogSource.SYSTEM,
                task_id=task_id
            )
            
            # Шаг 1: Определение намерения
            log_manager.log_stage_start(
                task_id=task_id,
                stage=LogStage.INTENT,
                message="Определение намерения...",
                source=LogSource.AGENT
            )
            
            intent_result = intent_agent.determine_intent(user_task, task_id=task_id)
            
            log_manager.log_stage_end(
                task_id=task_id,
                stage=LogStage.INTENT,
                message=f"Тип: {intent_result.type} (уверенность: {intent_result.confidence:.2f})",
                source=LogSource.AGENT,
                payload={"type": intent_result.type, "confidence": intent_result.confidence}
            )
            
            # Продолжить для остальных этапов...
            
        except KeyboardInterrupt:
            log_manager.log_info("👋 До свидания!", source=LogSource.SYSTEM)
            break
        except Exception as e:
            log_manager.log_error(
                message=f"Ошибка при обработке задачи: {str(e)}",
                source=LogSource.SYSTEM,
                task_id=task_id if 'task_id' in locals() else None,
                error=e
            )
```

### Преимущества
- Единообразное логирование в CLI и backend
- Возможность отслеживания задач
- Лучшая отладка

---

## 🎯 Приоритет 4: Конфигурация — Настройки логирования

### Цель
Добавить настройки логирования в `config.toml`.

### Файл для изменения
- `config.toml`
- `utils/config.py` — добавление свойств для логирования

### Шаги реализации

#### 1. Обновить `config.toml`

```toml
[default]
default_model = "codellama:13b-instruct-q4_0"
max_iterations = 5
enable_web = true
temperature = 0.25
max_tokens_warning = 30000
output_dir = "output"

[logging]
# Уровень логирования: DEBUG, INFO, WARNING, ERROR
level = "INFO"

# Включить/отключить sink-и
enable_file = true
enable_console = true
enable_memory = false  # Включается автоматически для UI

# Настройки файлового sink
log_file = "logs/app.jsonl"
max_file_size_mb = 100
file_backup_count = 5

# Настройки консольного sink
console_colors = true

# Настройки memory sink (для UI)
memory_max_events = 5000
```

#### 2. Обновить `utils/config.py`

```python
class Config:
    # ... существующий код ...
    
    @property
    def log_level(self) -> str:
        """Уровень логирования."""
        return self._config_data.get("logging", {}).get("level", "INFO")
    
    @property
    def log_enable_file(self) -> bool:
        """Включена ли запись в файл."""
        return self._config_data.get("logging", {}).get("enable_file", True)
    
    @property
    def log_enable_console(self) -> bool:
        """Включен ли вывод в консоль."""
        return self._config_data.get("logging", {}).get("enable_console", True)
    
    @property
    def log_file(self) -> str:
        """Путь к файлу логов."""
        return self._config_data.get("logging", {}).get("log_file", "logs/app.jsonl")
    
    @property
    def log_memory_max_events(self) -> int:
        """Максимальное количество событий в памяти."""
        return self._config_data.get("logging", {}).get("memory_max_events", 5000)
```

#### 3. Обновить `utils/logger.py` для использования config

```python
from utils.config import get_config

def _get_log_manager() -> LogManager:
    """Получает глобальный LogManager с настройками из config.toml."""
    global _default_log_manager
    if _default_log_manager is None:
        config_data = get_config()
        
        # Маппинг уровня из строки в LogLevel
        level_map = {
            "DEBUG": LogLevel.DEBUG,
            "INFO": LogLevel.INFO,
            "WARNING": LogLevel.WARNING,
            "ERROR": LogLevel.ERROR,
        }
        
        logging_config = LoggingConfig(
            level=level_map.get(config_data.log_level, LogLevel.INFO),
            enable_file=config_data.log_enable_file,
            enable_console=config_data.log_enable_console,
            enable_memory=os.getenv('UI_MODE', '0') == '1',
            log_file=Path(config_data.log_file),
            memory_max_events=config_data.log_memory_max_events,
            console_colors=config_data.log_enable_console  # Можно добавить в config
        )
        
        _default_log_manager = LogManager(logging_config)
    return _default_log_manager
```

### Преимущества
- Централизованная конфигурация
- Легко менять настройки без изменения кода
- Разные конфигурации для dev/prod

---

## 🎯 Приоритет 5: Тесты — Расширенное покрытие

### Цель
Добавить интеграционные тесты для проверки работы логирования с агентами.

### Файлы для создания
- `tests/test_logging_integration.py`

### Примеры тестов

```python
"""Интеграционные тесты системы логирования с агентами."""
import pytest
from agents.intent import IntentAgent
from utils.logger import get_log_manager, set_log_manager
from infrastructure.logging import LogManager, LoggingConfig
from infrastructure.logging.models import LogLevel, LogStage

def test_intent_agent_logging():
    """Тест логирования в IntentAgent."""
    # Создаём LogManager с памятью для тестов
    config = LoggingConfig(
        level=LogLevel.DEBUG,
        enable_file=False,
        enable_console=False,
        enable_memory=True
    )
    log_manager = LogManager(config)
    set_log_manager(log_manager)
    
    # Выполняем операцию
    agent = IntentAgent()
    task_id = "test-task-123"
    result = agent.determine_intent("создай функцию", task_id=task_id)
    
    # Проверяем логи
    memory_sink = log_manager.get_memory_sink()
    assert memory_sink is not None
    
    events = memory_sink.get_events(task_id=task_id)
    assert len(events) >= 2  # Начало и конец этапа
    
    # Проверяем начало этапа
    start_events = [e for e in events if e.stage == LogStage.INTENT and "Определяю" in e.message]
    assert len(start_events) >= 1
    
    # Проверяем конец этапа
    end_events = [e for e in events if "определено" in e.message.lower()]
    assert len(end_events) >= 1
    assert end_events[0].payload is not None
    assert "type" in end_events[0].payload
    
    log_manager.close()
```

---

## 📊 Метрики успеха

### Технические метрики
- ✅ Все существующие тесты проходят
- ✅ Новая система логирования используется в 50%+ кода
- ✅ SSE стриминг логов работает в UI
- ✅ Все агенты логируют с task_id

### Качественные метрики
- ✅ Единообразное логирование во всех компонентах
- ✅ Логи легко фильтровать по task_id, stage, source
- ✅ История логов доступна для анализа
- ✅ Отладка стала проще благодаря структурированным событиям

---

## 🚀 Порядок выполнения

1. **Неделя 1:** Приоритет 1 (Backend SSE стриминг)
   - Инициализация LogManager в backend
   - Создание SSE endpoint
   - Интеграция в workflow

2. **Неделя 2:** Приоритет 2 (Агенты)
   - Обновление IntentAgent
   - Обновление PlannerAgent
   - Обновление ResearcherAgent

3. **Неделя 3:** Приоритет 2 (Агенты, продолжение)
   - Обновление TestGeneratorAgent
   - Обновление CoderAgent
   - Обновление ReflectionAgent и MemoryAgent

4. **Неделя 4:** Приоритет 3 и 4 (CLI + Конфигурация)
   - Обновление CLI
   - Добавление настроек в config.toml
   - Тестирование

5. **Неделя 5:** Приоритет 5 (Тесты)
   - Интеграционные тесты
   - Рефакторинг и оптимизация

---

## 📝 Примечания

- Все изменения обратно совместимы благодаря `utils/logger.py`
- Можно выполнять постепенно, без больших рефакторингов
- Старый код продолжает работать во время миграции
- Новые возможности доступны сразу через `get_log_manager()`

---

## 🔗 Связанные документы

- `infrastructure/logging/README.md` — документация системы логирования
- `infrastructure/logging/integration_example.py` — примеры использования
- `tests/test_logging.py` — unit-тесты системы логирования