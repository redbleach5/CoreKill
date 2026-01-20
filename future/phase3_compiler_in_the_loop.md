# Фаза 3: Compiler-in-the-Loop

## Статус: ⏳ ЗАПЛАНИРОВАНО

## Цель

Реализовать инкрементальную генерацию кода с немедленной валидацией после каждой функции вместо отложенной валидации в конце workflow.

---

## Текущая проблема

```
Текущий workflow:
┌─────────┐   ┌──────────┐   ┌───────┐   ┌───────┐   ┌──────────┐
│ Planner │ → │ Research │ → │ Tests │ → │ Coder │ → │ Validate │
└─────────┘   └──────────┘   └───────┘   └───────┘   └──────────┘
                                                           │
                                                     ❌ Ошибка!
                                                           │
                                              (контекст уже потерян)
                                                           │
                                                           ▼
                                                    ┌──────────┐
                                                    │ Debugger │ → Fixer → ...
                                                    └──────────┘
```

**Проблемы:**
1. Ошибка обнаруживается ПОСЛЕ генерации всего кода
2. К моменту debug модель "забыла" контекст генерации
3. Исправление может сломать другие части
4. Много итераций debug-fix-validate (в среднем 2.5)

---

## Новый подход

```
Новый workflow (для COMPLEX задач):
┌─────────┐   ┌──────────┐   ┌───────┐
│ Planner │ → │ Research │ → │ Tests │
└─────────┘   └──────────┘   └───────┘
                                  │
                                  ▼
                    ┌─────────────────────────┐
                    │   IncrementalCoder      │
                    │                         │
                    │  for func in plan:      │
                    │    ┌─────────────────┐  │
                    │    │ Generate func   │  │
                    │    └────────┬────────┘  │
                    │             │           │
                    │    ┌────────▼────────┐  │
                    │    │ Run tests       │◄─┼── Immediate
                    │    └────────┬────────┘  │
                    │             │           │
                    │        ✅ Pass?         │
                    │        /       \        │
                    │       ✅       ❌       │
                    │       │         │       │
                    │       │  ┌──────▼─────┐ │
                    │       │  │ Fix w/error│◄┼── Context fresh
                    │       │  └──────┬─────┘ │
                    │       │         │       │
                    │       └────┬────┘       │
                    │            │            │
                    │    ┌───────▼──────┐     │
                    │    │ Next function │    │
                    │    └──────────────┘     │
                    └─────────────────────────┘
```

---

## Реализация

### 1. IncrementalCoder Agent

```python
# agents/incremental_coder.py
"""Инкрементальный генератор кода с немедленной валидацией."""

from dataclasses import dataclass, field
from typing import List, Optional, AsyncGenerator

from infrastructure.local_llm import create_llm_for_stage
from utils.validation import validate_code_quick
from utils.logger import get_logger

logger = get_logger()


@dataclass
class FunctionSpec:
    """Спецификация одной функции из плана."""
    name: str
    signature: str
    description: str
    dependencies: List[str] = field(default_factory=list)


@dataclass
class GenerationStep:
    """Результат одного шага генерации."""
    function_name: str
    code: str
    tests_passed: bool
    error: Optional[str] = None
    fix_attempts: int = 0


class IncrementalCoder:
    """Генерирует код по частям с немедленной валидацией.
    
    Workflow:
    1. Разбивает план на функции
    2. Генерирует каждую функцию отдельно
    3. Сразу запускает тесты
    4. Исправляет ошибки пока контекст свежий
    5. Переходит к следующей функции
    """
    
    MAX_FIX_ATTEMPTS = 3
    
    def __init__(
        self,
        model: Optional[str] = None,
        temperature: float = 0.2
    ):
        self.llm = create_llm_for_stage(
            stage="coding",
            model=model,
            temperature=temperature
        )
    
    async def generate_with_feedback(
        self,
        plan: str,
        tests: str,
        context: str = ""
    ) -> AsyncGenerator[GenerationStep, None]:
        """Генерирует код инкрементально с обратной связью.
        
        Args:
            plan: План реализации
            tests: Сгенерированные тесты
            context: Дополнительный контекст
            
        Yields:
            GenerationStep для каждой функции
        """
        # Разбираем план на функции
        functions = self._parse_plan_to_functions(plan)
        logger.info(f"📋 Разобрано {len(functions)} функций из плана")
        
        generated_code: List[str] = []
        
        for i, func_spec in enumerate(functions):
            logger.info(f"⚙️ [{i+1}/{len(functions)}] Генерирую: {func_spec.name}")
            
            # Генерируем функцию
            func_code = await self._generate_function(
                func_spec=func_spec,
                existing_code=generated_code,
                tests=tests,
                context=context
            )
            
            # Сразу валидируем
            step = await self._validate_and_fix(
                func_spec=func_spec,
                func_code=func_code,
                existing_code=generated_code,
                tests=tests
            )
            
            generated_code.append(step.code)
            yield step
        
        logger.info(f"✅ Генерация завершена: {len(generated_code)} функций")
    
    def _parse_plan_to_functions(self, plan: str) -> List[FunctionSpec]:
        """Извлекает функции из плана через LLM."""
        prompt = f"""Extract functions from this implementation plan.

PLAN:
{plan}

Return JSON array:
[
  {{"name": "func_name", "signature": "def func(args) -> type", "description": "what it does", "dependencies": ["other_func"]}},
  ...
]

JSON:"""
        
        response = self.llm.generate(prompt, num_predict=1024)
        return self._parse_functions_json(response)
    
    async def _generate_function(
        self,
        func_spec: FunctionSpec,
        existing_code: List[str],
        tests: str,
        context: str
    ) -> str:
        """Генерирует одну функцию."""
        existing_str = "\n\n".join(existing_code) if existing_code else "# No existing code"
        
        prompt = f"""Generate ONLY the function: {func_spec.name}

SIGNATURE: {func_spec.signature}
DESCRIPTION: {func_spec.description}

ALREADY GENERATED:
```python
{existing_str}
```

TESTS TO PASS:
```python
{tests}
```

CONTEXT: {context}

RULES:
1. Generate ONLY this function
2. Must work with existing code
3. Must pass the tests
4. Full type hints + docstring

CODE:"""
        
        response = await asyncio.to_thread(self.llm.generate, prompt, 1024)
        return self._extract_function_code(response)
    
    async def _validate_and_fix(
        self,
        func_spec: FunctionSpec,
        func_code: str,
        existing_code: List[str],
        tests: str
    ) -> GenerationStep:
        """Валидирует и исправляет функцию."""
        
        for attempt in range(self.MAX_FIX_ATTEMPTS):
            full_code = "\n\n".join(existing_code + [func_code])
            
            # Быстрая валидация
            result = await asyncio.to_thread(
                validate_code_quick, full_code, tests
            )
            
            if result.get("passed", False):
                logger.info(f"✅ {func_spec.name}: тесты прошли")
                return GenerationStep(
                    function_name=func_spec.name,
                    code=func_code,
                    tests_passed=True,
                    fix_attempts=attempt
                )
            
            error = result.get("error", "Unknown error")
            logger.warning(f"❌ {func_spec.name} attempt {attempt+1}: {error[:100]}")
            
            # Исправляем с контекстом ошибки (контекст свежий!)
            func_code = await self._fix_function(func_spec, func_code, error)
        
        return GenerationStep(
            function_name=func_spec.name,
            code=func_code,
            tests_passed=False,
            error=error,
            fix_attempts=self.MAX_FIX_ATTEMPTS
        )
    
    async def _fix_function(
        self,
        func_spec: FunctionSpec,
        func_code: str,
        error: str
    ) -> str:
        """Исправляет функцию на основе ошибки."""
        prompt = f"""Fix this function based on the error.

FUNCTION: {func_spec.name}

CURRENT CODE:
```python
{func_code}
```

ERROR:
{error}

Fix ONLY the error. Keep the signature and docstring.

FIXED:"""
        
        response = await asyncio.to_thread(self.llm.generate, prompt, 1024)
        return self._extract_function_code(response)
```

### 2. Quick Validation

```python
# utils/validation.py (добавить)

def validate_code_quick(code: str, tests: str = "") -> dict:
    """Быстрая валидация без полного pytest.
    
    Проверяет:
    1. Синтаксис (ast.parse)
    2. Компиляция (compile)
    3. Базовые тесты (exec)
    
    Returns:
        {"passed": bool, "error": str}
    """
    import ast
    
    # 1. Синтаксис
    try:
        ast.parse(code)
    except SyntaxError as e:
        return {"passed": False, "error": f"SyntaxError: {e}"}
    
    # 2. Компиляция
    try:
        compile(code, "<string>", "exec")
    except Exception as e:
        return {"passed": False, "error": f"CompileError: {e}"}
    
    # 3. Тесты
    if tests.strip():
        try:
            namespace = {}
            exec(code, namespace)
            exec(tests, namespace)
            return {"passed": True, "error": None}
        except AssertionError as e:
            return {"passed": False, "error": f"AssertionError: {e}"}
        except Exception as e:
            return {"passed": False, "error": f"RuntimeError: {e}"}
    
    return {"passed": True, "error": None}
```

### 3. Интеграция в Workflow

```python
# infrastructure/workflow_nodes.py

from agents.incremental_coder import IncrementalCoder

@workflow_node(stage="coding", fallback_key="code", fallback_value="")
async def coder_node(state: AgentState) -> AgentState:
    """Узел для генерации кода."""
    
    intent_result = state.get("intent_result")
    complexity = intent_result.complexity if intent_result else TaskComplexity.MEDIUM
    
    # Используем инкрементальный coder для COMPLEX задач
    if complexity == TaskComplexity.COMPLEX:
        logger.info("💻 Инкрементальная генерация для complex задачи...")
        
        incremental_coder = IncrementalCoder(model=state.get("model"))
        
        code_parts = []
        async for step in incremental_coder.generate_with_feedback(
            plan=state.get("plan", ""),
            tests=state.get("tests", ""),
            context=state.get("context", "")
        ):
            code_parts.append(step.code)
            
            # SSE прогресс
            if state.get("enable_sse"):
                await _send_incremental_progress(step)
        
        state["code"] = "\n\n".join(code_parts)
    else:
        # Обычная генерация для simple/medium
        # ... существующий код ...
    
    return state
```

---

## Конфигурация

```toml
# config.toml

[incremental_coding]
# Включить инкрементальную генерацию
enabled = true

# Минимальная сложность для инкрементальной генерации
min_complexity = "complex"  # simple | medium | complex

# Максимум попыток исправления на функцию
max_fix_attempts = 3

# Таймаут на валидацию одной функции (мс)
validation_timeout = 5000
```

---

## SSE Events

```typescript
// Новые события для frontend

interface IncrementalProgressEvent {
  type: 'incremental_progress';
  data: {
    function: string;       // Имя функции
    status: 'generating' | 'validating' | 'fixing' | 'passed' | 'failed';
    fix_attempts: number;
    error?: string;
    progress: {             // Общий прогресс
      current: number;      // Текущая функция
      total: number;        // Всего функций
    };
  };
}
```

---

## Метрики

| Метрика | До | Цель |
|---------|----|----|
| Debug итераций в среднем | 2.5 | < 1.0 |
| Код компилируется сразу | 60% | > 85% |
| Время до рабочего кода | 45 сек | < 30 сек |

---

## Checklist

- [ ] Создать `agents/incremental_coder.py`
- [ ] Добавить `validate_code_quick()` в `utils/validation.py`
- [ ] Интегрировать в `workflow_nodes.py`
- [ ] SSE события для прогресса
- [ ] Frontend: отображение инкрементального прогресса
- [ ] Конфигурация в `config.toml`
- [ ] Тесты
- [ ] Метрики и бенчмарки

---

## Зависимости от других фаз

- ✅ Фаза 1: Reasoning models — IncrementalCoder может использовать reasoning для лучшего понимания ошибок
- ⏳ Фаза 2: Structured output — `_parse_plan_to_functions()` может использовать Pydantic

---

## Риски

| Риск | Митигация |
|------|-----------|
| Медленнее для simple задач | Только для COMPLEX |
| Зависимости между функциями | Topological sort в плане |
| Тесты могут зависеть от всего кода | Изолированные unit тесты |
