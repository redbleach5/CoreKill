# Синхронизация тестов с кодом

**Когда использовать:** После рефакторинга, изменения сигнатур, добавления новых агентов/фич.

При упоминании этого файла (`@test_sync.md`) выполни следующее:

## 1. Проверь состояние тестов

```bash
source .venv/bin/activate && python -m pytest tests/ --tb=short -q
```

## 2. Если есть failures/errors — исправь

### Типичные проблемы:

**Import errors (LocalLLM → create_llm_for_stage):**
- Патч `'agents.X.LocalLLM'` → `'agents.X.create_llm_for_stage'`
- Добавь мок: `mock_llm.return_value = Mock()`

**Async nodes без await:**
- Добавь `@pytest.mark.asyncio` 
- Измени `def test_` → `async def test_`
- Добавь `await` перед вызовом async функций

**Изменённые сигнатуры:**
- Проверь актуальные параметры в коде агента
- Обнови fixture и вызовы в тестах

**Отсутствующие моки:**
- `get_model_router` — всегда мокай для агентов (авто-выбор моделей)
- `get_prompt_enhancer` — мокай для coder/test_generator
- `create_llm_for_stage` — мокай для всех агентов
- `get_workflow_config()` — мокай если нужно переопределить конфигурацию
- `_get_streaming_agent_for_state()` — мокай для стриминговых узлов

## 3. Проверь покрытие новых фич

Если в текущей сессии были добавлены новые:
- Функции → добавь unit тесты
- API endpoints → добавь integration тесты  
- Workflow nodes → добавь async тесты с моками

## 4. Финальная проверка

```bash
source .venv/bin/activate && python -m pytest tests/ -v --tb=short
```

Все тесты должны проходить (100% passed).

## 5. Коммит

После успешных тестов закоммить изменения с описанием что было исправлено.

---

**Когда вызывать:** После рефакторинга, изменения сигнатур, добавления новых агентов/фич.
