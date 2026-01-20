# Фаза 2: Миграция агентов на Structured Output

## Статус: ⏳ ЗАПЛАНИРОВАНО

## Цель

Мигрировать все агенты на использование `generate_structured()` с Pydantic моделями для гарантированного формата ответов.

---

## Текущее состояние

### Готовая инфраструктура (Фаза 1 ✅)

```
infrastructure/local_llm.py     # generate_structured() готов
models/agent_responses.py       # Pydantic модели готовы
config.toml                     # [structured_output] секция
```

### Агенты для миграции

| Агент | Файл | Pydantic модель | Статус |
|-------|------|-----------------|--------|
| IntentAgent | `agents/intent.py` | `IntentResponse` | ⏳ Планируется |
| PlannerAgent | `agents/planner.py` | `PlanResponse` | ⏳ Планируется |
| DebuggerAgent | `agents/debugger.py` | `DebugResponse` | ⏳ Планируется |
| CriticAgent | `agents/critic.py` | `CriticResponse` | ⏳ Планируется |
| ReflectionAgent | `agents/reflection.py` | `ReflectionResponse` | ⏳ Планируется |

---

## План миграции IntentAgent

### До (текущий код)

```python
# agents/intent.py
def _classify_with_llm(self, user_query: str) -> Optional[IntentResult]:
    prompt = f"""..."""
    
    response = self.llm.generate(prompt, num_predict=128)
    
    # Хрупкий парсинг
    return self._parse_llm_classification(response)

def _parse_llm_classification(self, response: str) -> Optional[IntentResult]:
    """Парсит ответ LLM и извлекает intent."""
    try:
        # Ищем JSON в ответе
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(response[start:end])
            # ... много валидации ...
    except:
        return None  # 🤷 Silent failure
```

### После (structured output)

```python
# agents/intent.py
from models import IntentResponse
from infrastructure.local_llm import StructuredOutputError

def _classify_with_llm(self, user_query: str) -> Optional[IntentResult]:
    prompt = f"""Classify this user request for a CODE GENERATION system.

REQUEST: "{user_query}"

INTENT TYPES: greeting, help, create, modify, debug, optimize, explain, test, refactor, analyze

COMPLEXITY: simple (<100 lines), medium (100-500), complex (500+)"""

    try:
        # Гарантированный формат через Pydantic
        response = self.llm.generate_structured(
            prompt=prompt,
            response_model=IntentResponse,
            num_predict=256
        )
        
        return IntentResult(
            type=response.intent,
            confidence=response.confidence,
            description=response.reasoning or f"Классифицировано как {response.intent}",
            complexity=self._map_complexity(response.complexity)
        )
        
    except StructuredOutputError as e:
        logger.warning(f"Structured output failed: {e}, using fallback")
        return self._fallback_classification(user_query)
```

---

## План миграции PlannerAgent

### До

```python
def _generate_plan_llm(self, task: str, context: str) -> str:
    prompt = f"""Create implementation plan..."""
    response = self.llm.generate(prompt, num_predict=256)
    return response  # Просто строка, без структуры
```

### После

```python
from models import PlanResponse

def _generate_plan_llm(self, task: str, context: str) -> PlanResponse:
    prompt = f"""Create implementation plan for: {task}

Context: {context}

Return structured plan with goal, steps, complexity, and approach."""

    response = self.llm.generate_structured(
        prompt=prompt,
        response_model=PlanResponse,
        num_predict=512
    )
    
    return response  # Типизированный PlanResponse
```

---

## План миграции DebuggerAgent

### До

```python
def analyze_errors(self, validation_results: dict, code: str, ...) -> DebugResult:
    prompt = f"""Analyze error..."""
    response = self.llm.generate(prompt)
    
    # Ручной парсинг
    error_type = self._extract_error_type(response)
    fix_instructions = self._extract_fix(response)
    ...
```

### После

```python
from models import DebugResponse

def analyze_errors(self, validation_results: dict, code: str, ...) -> DebugResult:
    prompt = f"""Analyze this code error.

CODE:
```python
{code}
```

ERROR: {validation_results.get('error', 'Unknown')}

Determine error_type, location, root_cause, and fix_instructions."""

    response = self.llm.generate_structured(
        prompt=prompt,
        response_model=DebugResponse
    )
    
    return DebugResult(
        error_type=response.error_type,
        error_summary=response.root_cause,
        fix_instructions=response.fix_instructions,
        confidence=response.confidence
    )
```

---

## Стратегия Fallback

```python
# utils/structured_helpers.py

from typing import TypeVar, Type, Callable
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)

def generate_with_fallback(
    llm: LocalLLM,
    prompt: str,
    response_model: Type[T],
    fallback_fn: Callable[[], T],
    num_predict: int = 1024
) -> T:
    """Генерирует structured output с fallback на ручной парсинг.
    
    Args:
        llm: LocalLLM инстанс
        prompt: Промпт
        response_model: Pydantic модель
        fallback_fn: Функция для fallback
        num_predict: Макс токенов
        
    Returns:
        Pydantic модель или результат fallback
    """
    from utils.config import get_config
    config = get_config()
    
    if not config.structured_output_enabled:
        return fallback_fn()
    
    try:
        return llm.generate_structured(prompt, response_model, num_predict)
    except StructuredOutputError:
        if config.structured_output_fallback:
            logger.warning("Structured output failed, using fallback")
            return fallback_fn()
        raise
```

---

## Feature Flags

```toml
# config.toml

[structured_output]
enabled = true
max_retries = 2

# Постепенная миграция — включаем по одному агенту
enabled_agents = ["intent"]  # Начинаем с intent

# Позже:
# enabled_agents = ["intent", "planner", "debugger", "critic", "reflection"]

fallback_to_manual_parsing = true
```

```python
# Проверка в агенте
def _classify_with_llm(self, user_query: str):
    config = get_config()
    
    if "intent" in config.structured_output_enabled_agents:
        return self._classify_structured(user_query)
    else:
        return self._classify_legacy(user_query)
```

---

## Checklist

- [ ] Мигрировать IntentAgent
  - [ ] Обновить `_classify_with_llm()`
  - [ ] Добавить fallback на legacy парсинг
  - [ ] Обновить тесты
  
- [ ] Мигрировать PlannerAgent
  - [ ] Создать `_generate_plan_structured()`
  - [ ] Сохранить `_generate_plan_legacy()`
  - [ ] Тесты

- [ ] Мигрировать DebuggerAgent
  - [ ] Обновить `analyze_errors()`
  - [ ] Тесты

- [ ] Мигрировать CriticAgent
  - [ ] Обновить `analyze()`
  - [ ] Тесты

- [ ] Мигрировать ReflectionAgent
  - [ ] Обновить `reflect()`
  - [ ] Тесты

- [ ] Интеграционные тесты
  - [ ] Workflow с structured output
  - [ ] Fallback сценарии

---

## Риски

| Риск | Митигация |
|------|-----------|
| Модель не поддерживает format="json" | Fallback на legacy парсинг |
| Изменение формата ломает frontend | SSE формат не меняется |
| Производительность | Кэширование JSON schema |

---

## Зависимости

- ✅ `infrastructure/local_llm.py` — `generate_structured()` готов
- ✅ `models/agent_responses.py` — Pydantic модели готовы
- ✅ `config.toml` — секция `[structured_output]`
