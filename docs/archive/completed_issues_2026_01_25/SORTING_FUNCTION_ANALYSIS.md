# Анализ: почему сервис не справляется с простыми задачами (например, «напиши функцию сортировки»)

## Краткий итог

Найдена **главная причина**: **исходный запрос пользователя (`task` / `user_query`) не передавался в агентов генерации тестов и кода.** Они получали только план, контекст и тип намерения. Для формулировки вроде «напиши функцию сортировки» план мог быть слишком общим, а контекст — посторонним, из‑за чего модель «теряла» суть задачи.

**Исправление (уже внесено):** в `infrastructure/workflow_nodes.py` во все вызовы `generate_tests` / `generate_tests_stream` и `generate_code` / `generate_code_stream` добавлена передача `user_query=state.get("task", "")`.

---

## Где искать дальше, если проблема останется

### 1. **`infrastructure/workflow_nodes.py`** (приоритет: высокий)

- **`generator_node` / `stream_generator_node`** — вызовы TestGenerator. Теперь в них передаётся `user_query=state.get("task", "")`. Если в `state["task"]` по какой‑то причине нет исходного запроса, генерация тестов будет неточной.
- **`coder_node` / `stream_coder_node`** — вызовы CoderAgent / StreamingCoderAgent. Аналогично передаётся `user_query=state.get("task", "")`. Проверьте, что при старте workflow в `state` всегда кладётся `task` с текстом пользователя (см. `backend/workflow_streamer.py`, `backend/routers/agent_handlers/workflow_handler.py`).

### 2. **`agents/test_generator.py`** (приоритет: высокий)

- При **пустом `user_query`** используется `_build_test_generation_prompt(plan, context, intent_type)`. В плане для простой задачи есть только общая фраза вроде «Проанализировать простую задачу: напиши функцию сортировки» — имени функции и сигнатуры нет.
- **Риск:** тесты могут вызывать выдуманные имена (`sort_list`, `sorting_func` и т.п.) или неверные сигнатуры. Coder потом пытается угадать имя по тестам — возможны расхождения.
- **Что проверить:** при наличии `user_query` вызывается `prompt_enhancer.enhance_for_tests(...)`. Убедитесь, что для «напиши функцию сортировки» enhance даёт явное уточнение: что за функция (сортировка списка), предполагаемое имя и несколько примеров.

### 3. **`infrastructure/coder_prompt_builder.py`** (приоритет: высокий)

- **`build_generation_prompt`** при `user_query=None` не подставляет явную формулировку задачи. Задача есть только в `plan` и в `context`.
- **`plan`** для простой задачи: «1. Проанализировать простую задачу: напиши функцию сортировки 2. Создать минимальную реализацию…» — этого может не хватать для однозначной реализации.
- **Рекомендация:** всегда передавать `user_query` из workflow (уже сделано в nodes) и в `build_generation_prompt` явно выносить в начало блока «Задача пользователя: {user_query}» при его наличии.

### 4. **`agents/coder.py`** (приоритет: средний)

- **Code retrieval:** `retriever.find_similar(query=f"{plan}\n{query}" if query else plan, ...)`. При пустом `user_query` поиск идёт только по `plan`. Для «сортировка» в проекте могут находиться фрагменты с `sorted()` в другом контексте (сортировка моделей, конфигов и т.д.) — **шум в few‑shot примерах**.
- **PromptEnhancer:** `if query and not examples` вызывается `prompt_enhancer.enhance_for_coding(...)`. При пустом `query` эта ветка не выполняется — используется только `prompt_builder.build_generation_prompt`. После передачи `user_query` эта ветка начнёт срабатывать. Стоит проверить, что `enhance_for_coding` для коротких задач не переусложняет промпт.

### 5. **`agents/researcher.py` + `infrastructure/context_engine.py`** (приоритет: средний)

- **Researcher** для `create` при `project_path` ищет в кодовой базе по `query` (task). Для «напиши функцию сортировки» в проекте много вхождений `sorted`, `.sort` в коде, не относящемся к «функции сортировки».  
- **Риск:** в `context` попадают куски про `model_router`, `workflow`, `cache` и т.п. Модель может отвлекаться на стиль/структуру большого проекта вместо простой функции.
- **Что проверить:**
  - для `create` и `complexity=simple` можно ограничивать объём контекста из codebase или не тянуть контекст вовсе;
  - в `context_engine` — пороги релевантности и максимальный размер `context` для простых задач.

### 6. **`agents/planner.py`** (приоритет: низкий)

- Для «напиши функцию сортировки» срабатывает `simple_patterns` (`'напиши функцию'` и т.п.) и выдаётся короткий план без вызова LLM. В плане есть формулировка задачи — это ок.
- При желании можно чуть обогатить шаблон простого плана, например:  
  «Реализовать функцию по запросу: “{task}”. Указать предполагаемое имя и сигнатуру, если очевидно».

### 7. **`agents/intent.py`** (приоритет: низкий)

- «напиши функцию сортировки» в примерах и маппится в `create` + `simple` — корректно.

### 8. **`utils/validation.py`** (приоритет: низкий)

- `_ensure_code_import` по вызовам в тестах подбирает импорты из `code`. Для `sort_list(...)` подхватит `from code import sort_list` — при условии, что тесты действительно вызывают ту же функцию, что реализована в `code`.
- Основная валидация идёт через `run_pytest` — поведение ожидаемое.

### 9. **`agents/base.py` — `_clean_code` / `_clean_code_from_reasoning`** (приоритет: низкий)

- Если в ответе модели есть только `def sort_list(lst): return sorted(lst)` без лишнего текста, код не должен обрезаться.
- Стоит в логах проверить, не возвращает ли `_clean_code` пустую строку из‑за отсутствия `def`/`class` в каком‑то краевом случае.

---

## Цепочка данных (где терялся user_query)

```
state["task"] = "напиши функцию сортировки"  (workflow_streamer / workflow_handler)
      ↓
intent_node  → intent_result (create, simple)
      ↓
planner_node → plan (короткий план с текстом задачи)
      ↓
researcher_node → context (codebase + RAG; может быть шум)
      ↓
generator_node → generate_tests(plan, context, intent_type, user_query=???)  ← раньше user_query не передавался
      ↓
coder_node    → generate_code(plan, tests, context, intent_type, user_query=???)  ← раньше user_query не передавался
```

После правок в `workflow_nodes` в оба агента уходит `user_query=state.get("task", "")`.

---

## Рекомендуемые следующие шаги

1. **Прогнать сценарий** «напиши функцию сортировки» с включённым логированием: что приходит в `generate_tests` / `generate_code` в `user_query`, что в `plan` и `context`.
2. **Проверить `prompt_enhancer.enhance_for_tests` и `enhance_for_coding`** на коротких задачах: не переусложняют ли они формулировку.
3. **Для `create` + `simple`** рассмотреть: не передавать в coder контекст из codebase или сильно его урезать (через `researcher_node` или `context_engine`).
4. **В `CoderPromptBuilder.build_generation_prompt`** при непустом `user_query` добавить явный блок «Задача пользователя: …» в начало промпта.

Если после этих шагов простые задачи всё ещё будут проваливаться, следующий фокус — логи полного промпта и ответа LLM на этапах `testing` и `coding` и просмотр сгенерированных тестов (имена и сигнатуры) vs реализацию в `code`.
