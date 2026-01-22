# Модели и таймауты

**Принцип:** Система агностична к конкретным моделям — автоматически выбирает оптимальную из доступных в Ollama на основе сложности задачи и требований к качеству.

## Выбор модели (SmartModelRouter)

Модель выбирается автоматически через `infrastructure/model_router.py` на основе:
- Сложности задачи (SIMPLE/MEDIUM/COMPLEX)
- Доступных моделей в Ollama
- Требований к качеству (пороги в config.toml)
- Доступной памяти (VRAM)

**Принципы выбора:**

| Сложность | Характеристики модели | Использование |
|-----------|----------------------|---------------|
| SIMPLE | Малые модели (1-4B), быстрые | Intent, короткие ответы, классификация |
| MEDIUM | Средние модели (7-13B), специализированные для кода | Код, тесты, планы, рефакторинг |
| COMPLEX | Reasoning модели или крупные (13B+) | Сложные задачи с рассуждениями, архитектура |

**Важно:** Конкретные модели не хардкодятся — система автоматически выбирает из доступных в Ollama.

## Reasoning Models

Reasoning модели имеют встроенный chain-of-thought и рассуждают в `<think>` блоках.

**Преимущества:**
- Сами разбивают задачу на шаги
- Лучше справляются со сложными задачами
- Не требуют промптов "think step by step"

**Определение:** Модель считается reasoning, если имеет флаг `is_reasoning=True` в `ModelInfo` (определяется автоматически по имени или характеристикам).

**Настройка в config.toml:**
```toml
[reasoning]
prefer_reasoning_models = true  # Предпочитать для COMPLEX задач
show_thinking = false           # Показывать <think> блоки в UI
```

**Парсинг ответа:**
```python
from infrastructure.reasoning_utils import parse_reasoning_response

response = llm.generate(prompt)
parsed = parse_reasoning_response(response)

print(parsed.thinking)  # Рассуждения из <think> блока
print(parsed.answer)    # Финальный ответ
```

**Real-time стриминг рассуждений и кода:**
```python
from infrastructure.reasoning_stream import get_reasoning_stream_manager
from infrastructure.local_llm import create_llm_for_stage

# Модель выбирается автоматически через ModelRouter
llm = create_llm_for_stage("coding", model=None)  # None = авто-выбор
manager = get_reasoning_stream_manager()

# Real-time стриминг с разделением thinking и content
async for event_type, data in manager.stream_from_llm(llm, prompt, "coding"):
    if event_type == "thinking":
        yield data  # SSE: thinking_started, thinking_in_progress, thinking_completed
    elif event_type == "content":
        yield create_code_chunk_event(data)  # Чанк кода для IDE
    elif event_type == "done":
        final_code = extract_code_from_reasoning(data)
```

**Низкоуровневый стриминг от LLM:**
```python
from infrastructure.local_llm import LocalLLM, StreamChunk

# Модель выбирается через ModelRouter или передаётся явно
llm = LocalLLM(model=None)  # None = авто-выбор через router

async for chunk in llm.generate_stream(prompt):
    if chunk.is_thinking:
        # Внутри <think> блока
        print(f"Thinking: {chunk.content}")
    else:
        # Основной контент (код)
        print(f"Code: {chunk.content}")
    
    if chunk.is_done:
        print(f"Full response: {chunk.full_response}")
```

См. `infrastructure/reasoning_stream.md` для полной документации.

**Реализованные файлы:**
- `infrastructure/reasoning_stream.py` — ReasoningStreamManager
- `infrastructure/reasoning_utils.py` — parse_reasoning_response()
- `agents/streaming_*.py` — все стриминговые агенты (6 шт.)

## Таймауты по этапам (config.toml)

```toml
[timeouts]
intent = 60      # Быстрая классификация
planning = 90
research = 90
testing = 120
coding = 180     # Самый долгий
validation = 120
debug = 120
fixing = 150
reflection = 90
critic = 90
chat = 90
default = 120
```

## Параметры генерации

```toml
[default]
temperature = 0.25   # 0.15-0.35 для кода (настраивается по этапам)
top_p = 0.9
max_retries = 3      # С exponential backoff
```

**Важно:** Температура может быть разной для разных этапов (настраивается в `[stages]` секции config.toml).

## Создание LLM

```python
from infrastructure.local_llm import create_llm_for_stage

# Автоматически использует таймаут из config.toml
# model=None — автоматический выбор через ModelRouter
llm = create_llm_for_stage(
    stage="coding",
    model=None,  # Авто-выбор оптимальной модели для этапа
    temperature=0.25
)

# Или явно указать модель (если нужно)
llm = create_llm_for_stage(
    stage="coding",
    model="custom-model:7b",  # Конкретная модель
    temperature=0.25
)
```

## Structured Output (Pydantic)

Для гарантированного формата ответа используй `generate_structured()`:

```python
from models import IntentResponse

response = llm.generate_structured(
    prompt="Classify: напиши функцию",
    response_model=IntentResponse
)

print(response.intent)       # "create" — типизировано
print(response.confidence)   # 0.95 — валидировано
```

**Доступные модели:**
- `IntentResponse` — классификация намерений
- `PlanResponse` — план реализации
- `DebugResponse` — анализ ошибок
- `CriticResponse` — критический анализ
- `AnalyzeResponse` — анализ проекта

**Настройка в config.toml:**
```toml
[structured_output]
enabled = true
max_retries = 2
fallback_to_manual_parsing = true
```

## Обработка таймаутов

При таймауте LLM:
1. Бросается `LLMTimeoutError`
2. Workflow node ловит ошибку
3. Отправляется SSE `stage_error` с типом "timeout"
4. Используется fallback значение
5. Workflow продолжает работу
