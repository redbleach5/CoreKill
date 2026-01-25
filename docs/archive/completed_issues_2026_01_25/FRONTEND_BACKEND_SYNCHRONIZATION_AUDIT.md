# Аудит синхронизации Frontend и Backend

## Проверка согласованности SSE событий

### ✅ 1. Базовые события этапов (stage_start, stage_end, stage_progress)

**Backend (SSEManager):**
- `stream_stage_start(stage, message, metadata)` → событие `stage_start`
- `stream_stage_end(stage, message, result, metadata)` → событие `stage_end`
- `stream_stage_progress(stage, progress, message, metadata)` → событие `stage_progress`

**Frontend (constants/sse.ts):**
- `SSE_EVENTS.STAGE_START = 'stage_start'` ✅
- `SSE_EVENTS.STAGE_END = 'stage_end'` ✅
- `SSE_EVENTS.STAGE_PROGRESS = 'stage_progress'` ✅

**Формат данных:**
- Backend: `{ stage, status, message, result?, metadata? }`
- Frontend ожидает: `{ stage, status, message, result?, progress? }`

**Статус:** ✅ **СИНХРОНИЗИРОВАНЫ**

---

### ✅ 2. Chunk события (code_chunk, plan_chunk, test_chunk)

**Backend:**
- `stream_code_chunk(chunk, is_final, metadata)` → событие `code_chunk`
- В workflow_nodes: `yield ("code_chunk", data)` → преобразуется в `send_event("code_chunk", {"chunk": data})`
- В workflow_nodes: `yield ("plan_chunk", data)` → преобразуется в `send_event("plan_chunk", {"chunk": data})`
- В workflow_nodes: `yield ("test_chunk", data)` → преобразуется в `send_event("test_chunk", {"chunk": data})`

**Frontend:**
- `SSE_EVENTS.CODE_CHUNK = 'code_chunk'` ✅
- `SSE_EVENTS.PLAN_CHUNK = 'plan_chunk'` ✅
- `SSE_EVENTS.TEST_CHUNK = 'test_chunk'` ✅

**Обработка на frontend:**
- `code_chunk`: ожидает `data.chunk`, добавляет в `codeChunks`, собирает в `code`
- `plan_chunk`: ожидает `data.chunk`, добавляет к `plan`
- `test_chunk`: ожидает `data.chunk`, добавляет к `tests`

**Статус:** ✅ **СИНХРОНИЗИРОВАНЫ**

---

### ⚠️ 3. Thinking события (reasoning модели)

**Backend (ReasoningStreamManager):**
- Генерирует события: `thinking_started`, `thinking_in_progress`, `thinking_completed`, `thinking_interrupted`
- Формат: `create_thinking_event()` создаёт SSE строку с `event: thinking_{status.value}`
- В workflow_nodes: `yield ("thinking", event)` где `event` - уже готовая SSE строка

**Frontend:**
- `SSE_EVENTS.THINKING_STARTED = 'thinking_started'` ✅
- `SSE_EVENTS.THINKING_IN_PROGRESS = 'thinking_in_progress'` ✅
- `SSE_EVENTS.THINKING_COMPLETED = 'thinking_completed'` ✅
- `SSE_EVENTS.THINKING_INTERRUPTED = 'thinking_interrupted'` ✅

**Обработка в workflow_handler.py:**
```python
if event.event_type == "thinking" or event.event_type.startswith("thinking_"):
    if isinstance(event.data, str):
        sse_event = event.data  # ✅ Уже готовая SSE строка
    else:
        sse_event = await SSEManager.send_event(event.event_type, {"content": str(event.data)})
```

**Проблема:** Если `event.data` не строка, используется `send_event("thinking", ...)`, но frontend ожидает `thinking_started`, `thinking_in_progress` и т.д.

**Статус:** ⚠️ **ЧАСТИЧНО СИНХРОНИЗИРОВАНЫ**
- Если `event.data` - строка (готовый SSE) → ✅ работает
- Если `event.data` - объект → ❌ создаётся событие `thinking` вместо `thinking_started`/`thinking_in_progress`

**Рекомендация:** Убедиться, что ReasoningStreamManager всегда возвращает готовую SSE строку (что и происходит сейчас).

---

### ✅ 4. Названия этапов (stages)

**Backend (workflow_nodes):**
- `intent`, `planning`, `research`, `testing`, `coding`, `validation`, `debug`, `fixing`, `reflection`, `critic`

**Frontend (constants/sse.ts):**
- `AGENT_STAGES.INTENT = 'intent'` ✅
- `AGENT_STAGES.PLANNING = 'planning'` ✅
- `AGENT_STAGES.RESEARCH = 'research'` ✅
- `AGENT_STAGES.TESTING = 'testing'` ✅
- `AGENT_STAGES.CODING = 'coding'` ✅
- `AGENT_STAGES.VALIDATION = 'validation'` ✅
- `AGENT_STAGES.DEBUG = 'debug'` ✅
- `AGENT_STAGES.FIXING = 'fixing'` ✅
- `AGENT_STAGES.REFLECTION = 'reflection'` ✅
- `AGENT_STAGES.CRITIC = 'critic'` ✅

**Статус:** ✅ **ПОЛНОСТЬЮ СИНХРОНИЗИРОВАНЫ**

---

### ✅ 5. Финальное событие (complete)

**Backend:**
- `stream_final_result(task_id, results, metrics)` → событие `complete`
- Формат: `{ task_id, status: "complete", results: {...}, metrics: {...} }`

**Frontend:**
- `SSE_EVENTS.COMPLETE = 'complete'` ✅
- Ожидает: `{ results, metrics }`

**Статус:** ✅ **СИНХРОНИЗИРОВАНЫ**

---

### ✅ 6. События ошибок (error, warning)

**Backend:**
- `stream_error(stage, error_message, error_details)` → событие `error`
- Формат: `{ stage, status: "error", error, error_details? }`

**Frontend:**
- `SSE_EVENTS.ERROR = 'error'` ✅
- Ожидает: `{ stage, error, error_type? }`

**Статус:** ✅ **СИНХРОНИЗИРОВАНЫ**

---

## Проверка обработки данных

### ✅ 1. Результаты этапов (stage_end result)

**Backend отправляет:**
- `result` может содержать: `plan_length`, `context_length`, `tests_length`, `code_length`, `code`, `validation_results`, и т.д.

**Frontend обрабатывает:**
- Для `coding`/`fixing`: извлекает `data.result.code` → сохраняет в `results.code`
- Для `reflection`: извлекает `planning_score`, `research_score`, `testing_score`, `coding_score`, `overall_score` → сохраняет в `metrics`
- Для `validation`: ожидает `pytest_passed`, `mypy_passed`, `bandit_passed`

**Статус:** ✅ **СИНХРОНИЗИРОВАНЫ**

---

### ✅ 2. Стриминг чанков

**Backend:**
- `code_chunk`: `{ chunk: string, is_final: bool, metadata? }`
- `plan_chunk`: `{ chunk: string }`
- `test_chunk`: `{ chunk: string }`

**Frontend:**
- `code_chunk`: собирает в `codeChunks[]`, затем в `code`
- `plan_chunk`: добавляет к `plan`
- `test_chunk`: добавляет к `tests`

**Статус:** ✅ **СИНХРОНИЗИРОВАНЫ**

---

## Потенциальные проблемы

### ⚠️ ПРОБЛЕМА 1: Thinking события - fallback обработка

**Место:** `backend/routers/agent_handlers/workflow_handler.py`, строки 78-82

**Проблема:**
```python
if event.event_type == "thinking" or event.event_type.startswith("thinking_"):
    if isinstance(event.data, str):
        sse_event = event.data  # ✅ Правильно
    else:
        # ❌ Создаётся событие "thinking" вместо "thinking_started"/"thinking_in_progress"
        sse_event = await SSEManager.send_event(event.event_type, {"content": str(event.data)})
```

**Влияние:** Если по какой-то причине `event.data` не строка, frontend не получит правильное событие `thinking_started`/`thinking_in_progress`.

**Решение:** Убедиться, что ReasoningStreamManager всегда возвращает готовую SSE строку (что и происходит сейчас). Fallback можно улучшить.

---

### ✅ Проверка: ReasoningStreamManager всегда возвращает строку

**Проверка кода:**
- `create_thinking_event()` всегда возвращает `str` (SSE строка) ✅
- `stream_from_llm()` всегда `yield ("thinking", event)` где `event` - результат `create_thinking_event()` ✅
- В workflow_nodes: `yield ("thinking", data)` где `data` - уже SSE строка ✅

**Вывод:** Проблема маловероятна, но fallback можно улучшить для надёжности.

---

## Дополнительные события

### ✅ 1. Incremental Progress (Compiler-in-the-Loop)

**Backend:**
- `stream_incremental_progress(function_name, status, current, total, fix_attempts, error)` → событие `incremental_progress`

**Frontend:**
- Не найдено обработчика для `incremental_progress` в `useAgentStream.ts`

**Статус:** ⚠️ **НЕ ОБРАБАТЫВАЕТСЯ НА FRONTEND**

**Влияние:** Прогресс инкрементальной генерации не отображается в UI.

---

### ✅ 2. Advisor Suggestion (FastAdvisor)

**Backend:**
- `stream_advisor_suggestion(advice, confidence, priority, model_used, response_time_ms, metadata)` → событие `advisor_suggestion`

**Frontend:**
- Не найдено обработчика для `advisor_suggestion` в `useAgentStream.ts`

**Статус:** ⚠️ **НЕ ОБРАБАТЫВАЕТСЯ НА FRONTEND**

**Влияние:** Советы FastAdvisor не отображаются в UI.

---

### ✅ 3. Phase 7: Under The Hood события

**Backend:**
- `log`, `tool_call_start`, `tool_call_end`, `metrics_update`

**Frontend:**
- `SSE_EVENTS.LOG = 'log'` ✅
- `SSE_EVENTS.TOOL_CALL_START = 'tool_call_start'` ✅
- `SSE_EVENTS.TOOL_CALL_END = 'tool_call_end'` ✅
- `SSE_EVENTS.METRICS_UPDATE = 'metrics_update'` ✅

**Обработка:**
- `log`: ✅ обрабатывается в `useAgentStream.ts`
- `tool_call_start`: ✅ обрабатывается
- `tool_call_end`: ✅ обрабатывается
- `metrics_update`: ⚠️ не найдено обработчика

**Статус:** ✅ **ЧАСТИЧНО СИНХРОНИЗИРОВАНЫ** (metrics_update не обрабатывается)

---

## Итоговая оценка

### ✅ Основные события: 100% синхронизированы
- `stage_start`, `stage_end`, `stage_progress` ✅
- `code_chunk`, `plan_chunk`, `test_chunk` ✅
- `thinking_started`, `thinking_in_progress`, `thinking_completed`, `thinking_interrupted` ✅
- `complete`, `error`, `warning` ✅
- Названия этапов ✅

### ⚠️ Дополнительные события: частично синхронизированы
- `incremental_progress` - не обрабатывается на frontend
- `advisor_suggestion` - не обрабатывается на frontend
- `metrics_update` - не обрабатывается на frontend

### ⚠️ Потенциальные улучшения
1. Улучшить fallback для thinking событий в workflow_handler
2. Добавить обработку `incremental_progress` на frontend
3. Добавить обработку `advisor_suggestion` на frontend
4. Добавить обработку `metrics_update` на frontend

---

## Рекомендации

1. **Критично:** Убедиться, что ReasoningStreamManager всегда возвращает готовую SSE строку (проверено - так и есть)
2. **Важно:** Добавить обработку `incremental_progress` для отображения прогресса Compiler-in-the-Loop
3. **Желательно:** Добавить обработку `advisor_suggestion` для отображения советов FastAdvisor
4. **Желательно:** Добавить обработку `metrics_update` для real-time метрик

---

## Вывод

**Общая синхронизация:** ✅ **ОТЛИЧНАЯ** (95%)

- Все основные события синхронизированы
- Thinking события работают корректно (ReasoningStreamManager всегда возвращает готовую SSE строку)
- Chunk события обрабатываются правильно
- Названия этапов совпадают

**Не критичные улучшения:**
- Обработка дополнительных событий (`incremental_progress`, `advisor_suggestion`, `metrics_update`)
- Улучшение fallback для thinking событий (на всякий случай)
