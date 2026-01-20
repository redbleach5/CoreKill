# Архитектура проекта

## Workflow (LangGraph)

```
START → intent_node → [greeting: END, else: planner_node]
planner_node → researcher_node → test_generator_node → coder_node → validator_node
validator_node → [passed: reflection_node, failed: debugger_node → fixer_node → validator_node]
reflection_node → critic_node → END
```

**Файлы:**
- `infrastructure/workflow_graph.py` — граф
- `infrastructure/workflow_nodes.py` — узлы (async)
- `infrastructure/workflow_edges.py` — условные переходы
- `infrastructure/workflow_state.py` — AgentState

## Агенты

| Агент | Файл | Назначение |
|-------|------|------------|
| Intent | `agents/intent.py` | Определение типа задачи |
| Planner | `agents/planner.py` | Создание плана |
| Researcher | `agents/researcher.py` | Сбор контекста (RAG + web) |
| TestGenerator | `agents/test_generator.py` | Генерация pytest тестов |
| Coder | `agents/coder.py` | Генерация кода |
| Debugger | `agents/debugger.py` | Анализ ошибок |
| Reflection | `agents/reflection.py` | Оценка качества |
| Critic | `agents/critic.py` | Критический анализ |
| Chat | `agents/chat.py` | Диалоговый режим |

## Dependency Injection

```python
from backend.dependencies import get_memory_agent, get_rag_system
from infrastructure.local_llm import create_llm_for_stage

# Singleton агенты
memory = get_memory_agent()
rag = get_rag_system()

# LLM с правильным таймаутом
llm = create_llm_for_stage(stage="coding", model="qwen2.5-coder:7b")
```

## Ключевые модули

| Модуль | Назначение |
|--------|------------|
| `infrastructure/local_llm.py` | Работа с Ollama (sync/async) |
| `infrastructure/model_router.py` | Выбор модели по задаче |
| `infrastructure/performance_metrics.py` | Метрики производительности |
| `infrastructure/task_checkpointer.py` | Сохранение состояния задач |
| `backend/sse_manager.py` | Server-Sent Events |
| `utils/config.py` | Конфигурация из config.toml |

## Передовая архитектура (2026)

См. `future/ROADMAP_2026.md` для плана перехода на:

| Технология | Статус | Документ |
|------------|--------|----------|
| Reasoning Models (DeepSeek-R1) | 🚀 Приоритет | `future/reasoning_models.md` |
| Structured Output (Pydantic) | 🚀 Приоритет | `future/structured_output.md` |
| Compiler-in-the-Loop | 🚀 Приоритет | `future/compiler_in_the_loop.md` |
| Code Retrieval (Few-shot) | 📋 Планируется | `future/code_retrieval.md` |
| Multi-Agent Debate | 📋 Планируется | `future/advanced_architecture_2026.md` |
| AST Analysis | 📋 Планируется | `future/context_engine_ast_parsing.md` |

**Принципы новой архитектуры:**
- Reasoning models вместо prompt engineering
- Structured output вместо хрупкого парсинга
- Немедленная валидация вместо отложенной
- Примеры кода вместо инструкций
- AST парсинг где LLM не нужен
