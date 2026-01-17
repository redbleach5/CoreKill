# Система логирования для multi-agent архитектуры

Централизованная система логирования с поддержкой структурированных событий, независимых sink-ов и подготовки к UI/стримингу.

## Архитектура

### Компоненты

1. **Модели** (`models.py`)
   - `LogEvent` - типизированная модель события
   - `LogLevel` - уровни логирования (DEBUG, INFO, WARNING, ERROR)
   - `LogSource` - источники (agent, system, ui, tool, validator, infrastructure)
   - `LogStage` - этапы выполнения (planning, research, coding, testing, validation, reflection, intent, memory)

2. **Интерфейс** (`sink.py`)
   - `LoggerSink` - абстрактный базовый класс для sink-ов
   - Методы: `emit()`, `flush()`, `close()`

3. **Реализации sink-ов**
   - `FileLoggerSink` - запись в JSONL файлы с ротацией
   - `ConsoleLoggerSink` - читаемый вывод в консоль
   - `MemoryLoggerSink` - хранение в памяти для UI/тестов

4. **Менеджер** (`manager.py`)
   - `LogManager` - единая точка входа
   - Управление несколькими sink-ами
   - Удобные методы: `log_info()`, `log_error()`, `log_stage_start()`, `log_stage_end()`

5. **Конфигурация** (`config.py`)
   - `LoggingConfig` - конфигурация системы
   - Готовые конфигурации: `for_dev()`, `for_prod()`, `for_ui()`

6. **Адаптер стриминга** (`stream_adapter.py`)
   - `LogStreamAdapter` - адаптер для SSE/WebSocket
   - `create_sse_event()` - преобразование в SSE формат

## Использование

### Базовое использование

```python
from infrastructure.logging import LogManager, LoggingConfig
from infrastructure.logging.models import LogSource, LogStage

# Создаём конфигурацию
config = LoggingConfig.for_dev()  # Для разработки

# Создаём менеджер
log_manager = LogManager(config)

# Логируем события
task_id = "task-123"
log_manager.log_stage_start(
    task_id=task_id,
    stage=LogStage.PLANNING,
    message="Начат этап планирования",
    payload={"top_k": 5}
)

log_manager.log_info(
    message="Сбор контекста завершён",
    source=LogSource.AGENT,
    stage=LogStage.RESEARCH,
    task_id=task_id
)

# Закрываем (освобождаем ресурсы)
log_manager.close()
```

### Интеграция с агентом

```python
class MyAgent:
    def __init__(self, log_manager: LogManager):
        self.log_manager = log_manager
    
    def process_task(self, task_id: str, query: str) -> dict:
        # Начало этапа
        self.log_manager.log_stage_start(
            task_id=task_id,
            stage=LogStage.RESEARCH,
            message="Начат поиск контекста в кодовой базе",
            source=LogSource.AGENT,
            payload={"query": query}
        )
        
        try:
            # ... бизнес-логика ...
            result = {"chunks": 5}
            
            # Завершение этапа
            self.log_manager.log_stage_end(
                task_id=task_id,
                stage=LogStage.RESEARCH,
                message="Контекст собран",
                source=LogSource.AGENT,
                payload=result
            )
            
            return result
            
        except Exception as e:
            # Логирование ошибки
            self.log_manager.log_error(
                message=f"Ошибка при сборе контекста: {str(e)}",
                source=LogSource.AGENT,
                stage=LogStage.RESEARCH,
                task_id=task_id,
                error=e
            )
            raise
```

### Использование с UI (SSE)

```python
from infrastructure.logging import LogManager, LoggingConfig, LogStreamAdapter, create_sse_event
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()

# Создаём менеджер с памятью для UI
config = LoggingConfig.for_ui()
log_manager = LogManager(config)

@app.get("/api/logs/stream/{task_id}")
async def stream_logs(task_id: str):
    """SSE endpoint для стриминга логов."""
    adapter = LogStreamAdapter(log_manager)
    
    async def event_generator():
        async for log_event in adapter.stream_events(task_id=task_id):
            yield create_sse_event(log_event)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
```

### Тестирование

```python
from infrastructure.logging import LogManager, LoggingConfig
from infrastructure.logging.models import LogLevel

def test_agent():
    # Создаём конфигурацию только с памятью (без файлов)
    config = LoggingConfig(
        level=LogLevel.DEBUG,
        enable_file=False,
        enable_console=False,
        enable_memory=True
    )
    
    log_manager = LogManager(config)
    
    # Используем агента с этим логгером
    agent = MyAgent(log_manager)
    
    # Выполняем операцию
    result = agent.process_task("test-123", "query")
    
    # Проверяем логи
    memory_sink = log_manager.get_memory_sink()
    assert memory_sink is not None
    
    events = memory_sink.get_events(task_id="test-123")
    assert len(events) >= 2  # Начало и конец этапа
    assert any(e.stage == LogStage.RESEARCH for e in events)
    
    log_manager.close()
```

## Принципы

1. **Логирование — инфраструктурный слой**
   - Бизнес-код НЕ знает, куда уходят логи
   - Работает только с интерфейсом `LogManager`

2. **Один лог = одно событие**
   - Структурированные данные в `payload` (не строки)
   - Типизированные поля (stage, source, level)

3. **Нет глобального состояния**
   - LogManager передаётся через DI
   - Можно использовать разные конфигурации в тестах

4. **Масштабируемость**
   - Легко добавить новые sink-и (OpenTelemetry, ELK, ClickHouse)
   - Независимые реализации не влияют друг на друга

## Конфигурация

### Для разработки
```python
config = LoggingConfig.for_dev()
# DEBUG уровень, консоль + файл, с цветами
```

### Для продакшена
```python
config = LoggingConfig.for_prod()
# INFO уровень, файл + память, без консоли
```

### Для UI
```python
config = LoggingConfig.for_ui()
# INFO уровень, файл + память (больше событий для стриминга)
```

## Миграция существующего кода

Заменяйте:
```python
logger = setup_logger()
logger.info("Сообщение")
```

На:
```python
log_manager = get_log_manager()  # Или передавайте через DI
log_manager.log_info(
    message="Сообщение",
    source=LogSource.AGENT,
    stage=LogStage.PLANNING,
    task_id=task_id
)
```