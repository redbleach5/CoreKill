# Roadmap: Развитие проекта

## Статус: ✅ ВСЕ ФАЗЫ РЕАЛИЗОВАНЫ

---

## Реализованные фазы

| # | Фаза | Описание | Статус |
|---|------|----------|--------|
| 1 | Reasoning Models | DeepSeek-R1/QwQ + real-time стриминг thinking | ✅ Готово |
| 2 | Structured Output | Pydantic для Intent/Debugger/Reflection + fallback | ✅ Готово |
| 3 | Compiler-in-the-Loop | IncrementalCoder для complex задач | ✅ Готово |
| 4 | Code Retrieval | Few-shot примеры из кода | ✅ Готово |
| 5 | Multi-Agent Debate | Несколько критиков | ✅ Готово |
| 6 | AST Analysis | Парсинг вместо LLM | ✅ Готово |

**🎉 Все 6 фаз ROADMAP 2026 реализованы!**

### Что реализовано:

**Фаза 1 — Reasoning Models:**
- `infrastructure/reasoning_stream.py` — ReasoningStreamManager
- `infrastructure/reasoning_utils.py` — парсинг `<think>` блоков
- `agents/streaming_*.py` — 6 стриминговых агентов
- Автоматический выбор reasoning модели для COMPLEX задач

**Фаза 2 — Structured Output:**
- `models/agent_responses.py` — Pydantic модели
- `utils/structured_helpers.py` — `generate_with_fallback()`
- Миграция IntentAgent, DebuggerAgent, ReflectionAgent
- Feature flag в config.toml

**Фаза 3 — Compiler-in-the-Loop:**
- `agents/incremental_coder.py` — IncrementalCoder
- `utils/validation.validate_code_quick()` — быстрая валидация
- Интеграция в workflow для complex задач
- SSE события для прогресса

**Фаза 4 — Code Retrieval:**
- `infrastructure/code_retrieval.py` — CodeRetriever, CodeExample
- Интеграция с ChromaDB + sentence-transformers
- Интеграция в CoderAgent с few-shot промптами
- История успешных генераций
- 17 тестов

**Фаза 5 — Multi-Agent Debate:**
- `agents/specialized_reviewers.py` — SecurityReviewer, PerformanceReviewer, CorrectnessReviewer
- `infrastructure/debate.py` — DebateOrchestrator
- Интеграция в critic_node
- Параллельный запуск рецензентов
- 25 тестов

**Фаза 6 — AST Analysis:**
- `infrastructure/ast_analyzer.py` — ASTAnalyzer, DependencyGraph, ProjectAnalyzer
- Извлечение functions, classes, imports
- Граф зависимостей с PageRank-подобной важностью
- Cyclomatic complexity
- Интеграция в ChatAgent.analyze_project()
- 27 тестов

---

## Будущее развитие

| Фича | Описание | Статус |
|------|----------|--------|
| **Фаза 7: Under The Hood** | Визуализация как у Manus AI | ✅ Реализовано |
| Tree-sitter | Мультиязычный парсинг (JS/TS/Go/Rust) | 📋 Планируется |
| Frontend Thinking UI | Отображение `<think>` блоков в UI | ✅ Реализовано |
| Metrics Dashboard | Визуализация метрик генерации | ✅ Реализовано |

### Фаза 7: Under The Hood Visualization ✅ РЕАЛИЗОВАНО

**Цель:** Прозрачность работы AI как у Manus AI

**Реализованные компоненты:**
- `LiveLogsPanel.tsx` — real-time логи с фильтрацией
- `ToolCallsPanel.tsx` — отслеживание LLM вызовов
- `WorkflowGraph.tsx` — интерактивный граф workflow
- `UnderTheHoodPanel.tsx` — единая панель с табами
- `infrastructure/debug_events.py` — backend эмиттер событий
- Кнопка 👁️ в header с индикатором активных вызовов

**Как использовать:**
1. Нажмите 👁️ (Eye) в header справа
2. Переключайтесь между вкладками: Логи, Вызовы, Граф, Метрики
3. Панель можно развернуть на весь экран

**Подробный план:** `UNDER_THE_HOOD_VISUALIZATION.md`

### Frontend Thinking UI ✅
- Улучшен `ThinkingBlock.tsx` — анимация, автопрокрутка, компактный режим
- Градиенты и красивые индикаторы прогресса
- Поддержка свёрнутого/развёрнутого состояния

### Metrics Dashboard ✅
- `frontend/src/components/MetricsDashboard.tsx` — дашборд с метриками
- `backend/routers/metrics.py` — API endpoint `/api/metrics`
- Кнопка переключения на дашборд в header (иконка графика)
- Метрики по этапам, моделям, успешности

---

## Фаза 4: Code Retrieval ✅ РЕАЛИЗОВАНО

### Реализованные компоненты
- `infrastructure/code_retrieval.py` — CodeRetriever, CodeExample
- Интеграция с ChromaDB для embeddings (sentence-transformers)
- Интеграция в CoderAgent с few-shot промптами
- История успешных генераций (add_from_history)
- Конфигурация `[code_retrieval]` в config.toml
- 17 тестов в `tests/test_code_retrieval.py`

### Как использовать
```toml
# config.toml
[code_retrieval]
enabled = true
sources = ["local", "history"]
num_examples = 3
```

### Индексация проекта
```python
from infrastructure.code_retrieval import CodeRetriever

retriever = CodeRetriever()
count = retriever.index_project("/path/to/project")
print(f"Проиндексировано {count} функций")
```

**Подробный план:** `code_retrieval.md`

---

## Фаза 5: Multi-Agent Debate ✅ РЕАЛИЗОВАНО

### Реализованные компоненты
- `agents/specialized_reviewers.py` — SecurityReviewer, PerformanceReviewer, CorrectnessReviewer
- `infrastructure/debate.py` — DebateOrchestrator
- Интеграция в critic_node (workflow_nodes.py)
- Параллельный запуск рецензентов через asyncio
- Конфигурация `[multi_agent_debate]` в config.toml
- 25 тестов в `tests/test_debate.py`

### Как использовать
```toml
# config.toml
[multi_agent_debate]
enabled = true
max_rounds = 3
```

### Принцип: Devil's Advocate
```
SecurityReviewer: "⚠️ SQL injection на строке 42"
PerformanceReviewer: "⚠️ O(n²) можно O(n)"
CorrectnessReviewer: "⚠️ Не обработан None"
```

**Подробный план:** `multi_agent_debate.md`

---

## Фаза 6: AST Analysis ✅ РЕАЛИЗОВАНО

### Реализованные компоненты
- `infrastructure/ast_analyzer.py` — ASTAnalyzer, DependencyGraph, ProjectAnalyzer
- Извлечение функций, классов, импортов
- Cyclomatic complexity для каждой функции
- Граф зависимостей с PageRank-подобной важностью
- Интеграция в ChatAgent.analyze_project()
- 27 тестов в `tests/test_ast_analyzer.py`

### Как использовать
```python
from infrastructure.ast_analyzer import ASTAnalyzer, ProjectAnalyzer

# Анализ одного файла
analyzer = ASTAnalyzer()
result = analyzer.analyze_file("main.py")
print(f"Functions: {result.get_all_function_names()}")
print(f"Complexity: {result.metrics.avg_function_complexity}")

# Анализ проекта
project = ProjectAnalyzer()
stats = project.analyze_project("/path/to/project")
print(f"LOC: {stats['total_loc']}, Functions: {stats['total_functions']}")
```

### Принцип: AST не галлюцинирует
```
❌ LLM: "В файле примерно 5 функций..."
✅ AST: "В файле ровно 7 функций: main, process_data, validate, ..."
```

**Подробный план:** `context_engine_ast_parsing.md`

---

## Будущее (после Фазы 6)

| Фича | Описание | Документ |
|------|----------|----------|
| Tree-sitter | Мультиязычный парсинг (JS/TS/Go/Rust) | `tree_sitter_multilang.md` |
| Frontend Thinking UI | Отображение `<think>` блоков в UI | — |
| Metrics Dashboard | Визуализация метрик генерации | — |

---

## Метрики успеха

| Метрика | До Phase 1-3 | После Phase 1-3 | Цель Phase 4-6 |
|---------|--------------|-----------------|----------------|
| Код компилируется сразу | ~60% | ~75% | >85% |
| Debug итераций в среднем | 2.5 | 1.5 | <1.0 |
| Стиль соответствует проекту | ~50% | ~50% | >90% |
| Intent accuracy | ~85% | ~95% | >98% |

---

## Зависимости

```bash
# Уже установлено (Phase 1-3)
pydantic>=2.0
langchain langgraph ollama chromadb

# Phase 4: Code Retrieval
pip install sentence-transformers
pip install PyGithub  # опционально

# Phase 6: AST (встроено в Python)
# import ast  — уже есть
```

---

## Связанные документы

- `code_retrieval.md` — Детальный план Фазы 4
- `multi_agent_debate.md` — Детальный план Фазы 5
- `context_engine_ast_parsing.md` — Детальный план Фазы 6
- `tree_sitter_multilang.md` — Мультиязычность (будущее)
- `russia.md` — Работа в РФ
