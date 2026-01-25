# Fast Advisor - Быстрые консультации

Модуль для асинхронных консультаций с легкими reasoning моделями, который решает проблему долгих ответов, предоставляя быстрые советы и подсказки параллельно с основным workflow.

## Особенности

- **Не блокирует основной процесс** - работает асинхронно в фоне
- **Использует легкие модели** - автоматически выбирает оптимальную легкую reasoning модель (phi3:mini, gemma:2b и т.д.)
- **Быстрые ответы** - таймаут по умолчанию 10 секунд, максимум 256 токенов
- **Кэширование** - типовые вопросы кэшируются для мгновенных ответов
- **Конфигурируемый** - все настройки через config.toml

## Конфигурация

```toml
[fast_advisor]
# Включить быстрые консультации
enabled = true

# Модель для консультаций (None = автовыбор легкой reasoning модели)
model = ""

# Таймаут для консультации (секунды)
timeout = 10

# Включить кэширование ответов
enable_cache = true

# Время жизни кэша (секунды)
cache_ttl = 3600
```

## Использование

### Базовое использование

```python
from infrastructure.fast_advisor import get_fast_advisor, AdvisorRequest, AdvisorPriority

advisor = get_fast_advisor()

# Создаём запрос
request = AdvisorRequest(
    query="Как оптимизировать этот код?",
    context="Используется цикл for с большим количеством итераций",
    priority=AdvisorPriority.MEDIUM
)

# Асинхронная консультация (не блокирует)
response = await advisor.consult_async(request)
print(f"Совет: {response.advice}")
print(f"Уверенность: {response.confidence}")
print(f"Время ответа: {response.response_time_ms}мс")
```

### С callback (для отправки через SSE)

```python
async def send_advice_to_frontend(response):
    """Отправляет совет на фронтенд через SSE."""
    event = await SSEManager.stream_advisor_suggestion(
        advice=response.advice,
        confidence=response.confidence,
        priority=response.priority.value,
        model_used=response.model_used,
        response_time_ms=response.response_time_ms
    )
    # Отправляем событие...

# Запускаем консультацию в фоне
await advisor.consult_async(request, callback=send_advice_to_frontend)
# Основной процесс продолжается, не ожидая ответа
```

### Синхронная консультация (если нужен немедленный ответ)

```python
response = advisor.consult_sync(request)
print(response.advice)
```

## Интеграция в workflow

FastAdvisor автоматически интегрирован в основной workflow через `backend/routers/agent.py`. При каждом запросе:

1. Запускается фоновая консультация (если `fast_advisor.enabled = true`)
2. Совет отправляется через SSE событие `advisor_suggestion`
3. Основной workflow продолжается без блокировки

## SSE События

Советы отправляются через SSE событие `advisor_suggestion`:

```json
{
  "advice": "Используй async/await для I/O операций...",
  "confidence": 0.85,
  "priority": "medium",
  "model_used": "phi3:mini",
  "response_time_ms": 234,
  "metadata": {
    "query_length": 45,
    "context_provided": true
  }
}
```

## Приоритеты

- `LOW` - Фоновые советы, не критично
- `MEDIUM` - Полезные подсказки (по умолчанию)
- `HIGH` - Важные рекомендации

## Выбор модели

FastAdvisor автоматически выбирает оптимальную легкую модель:

1. **Приоритет 1**: Легкие reasoning модели (phi3:mini, gemma:2b) до 4GB
2. **Приоритет 2**: Обычные легкие модели (tinyllama, phi3:mini)
3. **Fallback**: Любая доступная модель

## Кэширование

Типовые вопросы кэшируются для мгновенных ответов:
- Ключ: хеш от нормализованного вопроса + контекста
- TTL: по умолчанию 1 час (настраивается в config.toml)
- Использует общий кэш системы (`infrastructure/cache.py`)

## Ограничения

- Максимальная длина ответа: 500 символов
- Максимум токенов: 256
- Таймаут: 10 секунд (настраивается)
- Retry: 1 попытка (быстрота важнее надёжности)

## Примеры использования

### Оптимизация кода

```python
request = AdvisorRequest(
    query="Как ускорить этот код?",
    context="def process_data(items):\n    result = []\n    for item in items:\n        result.append(item * 2)\n    return result",
    priority=AdvisorPriority.HIGH
)
```

### Отладка

```python
request = AdvisorRequest(
    query="Почему этот код не работает?",
    context="Ошибка: AttributeError: 'NoneType' object has no attribute 'process'",
    priority=AdvisorPriority.HIGH
)
```

### Обучение

```python
request = AdvisorRequest(
    query="Объясни как работает async/await",
    priority=AdvisorPriority.MEDIUM
)
```
