# Модели и таймауты

## Выбор модели (SmartModelRouter)

Модель выбирается автоматически через `infrastructure/model_router.py`:

| Сложность | Модель | Использование |
|-----------|--------|---------------|
| SIMPLE | phi3:mini, tinyllama | Intent, короткие ответы |
| MEDIUM | qwen2.5-coder:7b | Код, тесты, планы |
| COMPLEX | codellama:13b, deepseek-coder | Сложные задачи |

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
temperature = 0.25   # 0.15-0.35 для кода
top_p = 0.9
max_retries = 3      # С exponential backoff
```

## Создание LLM

```python
from infrastructure.local_llm import create_llm_for_stage

# Автоматически использует таймаут из config.toml
llm = create_llm_for_stage(
    stage="coding",
    model="qwen2.5-coder:7b",
    temperature=0.25
)
```

## Обработка таймаутов

При таймауте LLM:
1. Бросается `LLMTimeoutError`
2. Workflow node ловит ошибку
3. Отправляется SSE `stage_error` с типом "timeout"
4. Используется fallback значение
5. Workflow продолжает работу
