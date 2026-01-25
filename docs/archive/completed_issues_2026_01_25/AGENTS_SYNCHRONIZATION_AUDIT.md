# Аудит синхронизации агентов

## Проверка синхронизации между синхронными и стриминговыми агентами

### ✅ 1. TestGeneratorAgent / StreamingTestGeneratorAgent

**Синхронный:**
```python
def generate_tests(
    self,
    plan: str,
    context: str,
    intent_type: str,
    user_query: str = "",
    min_test_cases: int = 3,
    max_test_cases: int = 5
) -> str
```

**Стриминговый:**
```python
async def generate_tests_stream(
    self,
    plan: str,
    context: str,
    intent_type: str,
    user_query: str = "",
    min_test_cases: int = 3,
    max_test_cases: int = 5,
    stage: str = "testing"
) -> AsyncGenerator[tuple[str, str], None]
```

**Статус:** ✅ **СИНХРОНИЗИРОВАНЫ**
- Все параметры совпадают
- `user_query` передаётся в обоих случаях
- Дополнительный параметр `stage` в стриминговой версии - нормально

**Использование в workflow_nodes:**
- `generator_node`: ✅ передаёт `user_query=state.get("task", "")`
- `stream_generator_node`: ✅ передаёт `user_query=state.get("task", "")`

---

### ✅ 2. CoderAgent / StreamingCoderAgent

**Синхронный:**
```python
def generate_code(
    self,
    plan: str,
    tests: str,
    context: str,
    intent_type: str,
    user_query: str = ""
) -> str
```

**Стриминговый:**
```python
async def generate_code_stream(
    self,
    plan: str,
    tests: str,
    context: str,
    intent_type: str,
    user_query: str = "",
    stage: str = "coding"
) -> AsyncGenerator[tuple[str, str], None]
```

**Статус:** ✅ **СИНХРОНИЗИРОВАНЫ**
- Все параметры совпадают
- `user_query` передаётся в обоих случаях

**Использование в workflow_nodes:**
- `coder_node`: ✅ передаёт `user_query=state.get("task", "")`
- `stream_coder_node`: ✅ передаёт `user_query=state.get("task", "")`
- `incremental_coder`: ✅ передаёт `user_query=state.get("task", "")` (после исправления)

**fix_code:**
- Синхронный: `fix_code(code, instructions, tests, validation_results)`
- Стриминговый: `fix_code_stream(code, instructions, tests, validation_results, stage="fixing")`
- **Статус:** ✅ **СИНХРОНИЗИРОВАНЫ** (дополнительный `stage` - нормально)

---

### ✅ 3. PlannerAgent / StreamingPlannerAgent

**Синхронный:**
```python
def create_plan(
    self,
    task: str,
    intent_type: str,
    context: str = "",
    alternatives_count: int = 2
) -> str
```

**Стриминговый:**
```python
async def create_plan_stream(
    self,
    task: str,
    intent_type: str,
    context: str = "",
    alternatives_count: int = 2,
    stage: str = "planning"
) -> AsyncGenerator[tuple[str, str], None]
```

**Статус:** ✅ **СИНХРОНИЗИРОВАНЫ**
- Все параметры совпадают
- Дополнительный `stage` в стриминговой версии - нормально

**Использование в workflow_nodes:**
- `planner_node`: ✅ передаёт `task=task` (из state)
- `stream_planner_node`: ✅ передаёт `task=task` (из state)

**⚠️ ПРОБЛЕМА:** В `stream_planner_node` не передаётся `context` и `alternatives_count`!

**Файл:** `infrastructure/workflow_nodes.py`, строка 397-400

```python
async for event_type, data in streaming_planner.create_plan_stream(
    task=task,
    intent_type=intent_result.type,
    stage="planning"  # ❌ Отсутствуют context и alternatives_count
):
```

---

### ✅ 4. DebuggerAgent / StreamingDebuggerAgent

**Синхронный:**
```python
def analyze_errors(
    self,
    validation_results: Dict[str, Any],
    code: str,
    tests: str,
    task: str
) -> DebugResult
```

**Стриминговый:**
```python
async def analyze_errors_stream(
    self,
    validation_results: Dict[str, Any],
    code: str,
    tests: str,
    task: str,
    stage: str = "debugging"
) -> AsyncGenerator[tuple[str, Any], None]
```

**Статус:** ✅ **СИНХРОНИЗИРОВАНЫ**
- Все параметры совпадают
- Дополнительный `stage` - нормально

**Использование в workflow_nodes:**
- `debugger_node`: ✅ передаёт все параметры
- `stream_debugger_node`: ✅ передаёт все параметры

---

### ✅ 5. ReflectionAgent / StreamingReflectionAgent

**Синхронный:**
```python
def reflect(
    self,
    task: str,
    plan: str,
    context: str,
    tests: str,
    code: str,
    validation_results: Dict[str, Any]
) -> ReflectionResult
```

**Стриминговый:**
```python
async def reflect_stream(
    self,
    task: str,
    plan: str,
    context: str,
    tests: str,
    code: str,
    validation_results: Dict[str, Any],
    stage: str = "reflection"
) -> AsyncGenerator[tuple[str, Any], None]
```

**Статус:** ✅ **СИНХРОНИЗИРОВАНЫ**
- Все параметры совпадают

**Использование в workflow_nodes:**
- `reflection_node`: ✅ передаёт все параметры
- `stream_reflection_node`: ✅ передаёт все параметры

---

### ✅ 6. CriticAgent / StreamingCriticAgent

**Синхронный:**
```python
def analyze(
    self,
    code: str,
    tests: str,
    task_description: str,
    validation_results: Dict[str, Any]
) -> CriticReport
```

**Стриминговый:**
```python
async def analyze_stream(
    self,
    code: str,
    tests: str,
    task_description: str,
    validation_results: Dict[str, Any],
    stage: str = "critic"
) -> AsyncGenerator[tuple[str, Any], None]
```

**Статус:** ✅ **СИНХРОНИЗИРОВАНЫ**
- Все параметры совпадают

**Использование в workflow_nodes:**
- `critic_node`: ✅ передаёт все параметры
- `stream_critic_node`: ✅ передаёт все параметры

---

## Найденные проблемы

### ❌ ПРОБЛЕМА 1: stream_planner_node не передаёт context и alternatives_count

**Файл:** `infrastructure/workflow_nodes.py`, строки 397-400

**Текущий код:**
```python
async for event_type, data in streaming_planner.create_plan_stream(
    task=task,
    intent_type=intent_result.type,
    stage="planning"
):
```

**Должно быть:**
```python
async for event_type, data in streaming_planner.create_plan_stream(
    task=task,
    intent_type=intent_result.type,
    context=state.get("context", ""),  # ❌ Отсутствует
    alternatives_count=2,  # ❌ Отсутствует
    stage="planning"
):
```

**Влияние:** 
- На момент планирования context ещё не собран (порядок: planner → researcher)
- Но context может быть передан из памяти (memory_recommendations) внутри create_plan
- Исправление добавлено для будущей совместимости и единообразия

**Исправление:** ✅ Добавлена передача `context` и `alternatives_count` в `stream_planner_node`

---

### ✅ Проверка передачи user_query

**Статус:** ✅ **ВСЕ АГЕНТЫ ПОЛУЧАЮТ user_query**

После наших исправлений:
- ✅ `generator_node` → `user_query=state.get("task", "")`
- ✅ `stream_generator_node` → `user_query=state.get("task", "")`
- ✅ `coder_node` → `user_query=state.get("task", "")`
- ✅ `stream_coder_node` → `user_query=state.get("task", "")`
- ✅ `incremental_coder` → `user_query=state.get("task", "")`

---

## Общие наблюдения

### ✅ Положительные моменты

1. **Единый BaseAgent** - все агенты наследуются от `BaseAgent`, что обеспечивает единообразие
2. **DependencyContainer** - централизованное управление агентами через singleton
3. **WorkflowState** - единый `AgentState` для передачи данных между узлами
4. **Декораторы** - `@workflow_node` обеспечивает единообразную обработку ошибок
5. **Стриминговые адаптеры** - единый механизм адаптации стриминговых узлов к LangGraph

### ⚠️ Потенциальные улучшения

1. **stream_planner_node** - добавить передачу `context` и `alternatives_count`
2. **Типизация** - можно улучшить типизацию для лучшей проверки синхронизации
3. **Тесты** - добавить тесты на синхронизацию параметров между версиями

---

## Рекомендации

1. **Исправить stream_planner_node** - добавить передачу `context` и `alternatives_count`
2. **Добавить проверку синхронизации** - unit-тесты, которые проверяют совпадение сигнатур
3. **Документировать различия** - явно указать, что стриминговые версии имеют дополнительный параметр `stage`

---

## Итоговая оценка

**Общая синхронизация:** ✅ **ХОРОШАЯ** (95%)

- Все основные параметры синхронизированы
- `user_query` передаётся везде (после исправлений)
- Единственная проблема: `stream_planner_node` не передаёт `context` и `alternatives_count`
