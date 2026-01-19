# Метрики качества

## Целевые показатели

| Метрика | Цель |
|---------|------|
| Покрытие тестами | ≥ 85% |
| Тесты перед коммитом | 100% passed |
| mypy strict | 0 ошибок |
| bandit | medium и ниже |
| Уверенность агентов | ≥ 0.75 |
| Веб-поиск | ≤ 20% задач |

## Проверка перед коммитом

```bash
# Тесты
source .venv/bin/activate && python -m pytest tests/ -v

# Типы
mypy agents/ infrastructure/ utils/ --strict

# Безопасность
bandit -r agents/ infrastructure/ -ll
```

## Структура тестов

```
tests/
├── conftest.py              # Fixtures, pytest-asyncio
├── test_<agent>.py          # Unit тесты агентов
├── test_workflow_*.py       # Тесты workflow
└── test_<module>.py         # Тесты инфраструктуры
```

## Правила тестов

1. **Моки агентов:**
   - Патчить `create_llm_for_stage` (не `LocalLLM`)
   - Патчить `get_model_router`
   - Патчить `get_prompt_enhancer` для Coder/TestGenerator

2. **Async тесты:**
   - Декоратор `@pytest.mark.asyncio`
   - `async def test_*`
   - `await` для async функций

3. **Workflow тесты:**
   - Мокать `_initialize_agents`, `_save_checkpoint`
   - Использовать `create_test_state()` helper
