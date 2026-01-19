Обязательный порядок агентов для каждой задачи (реализован через LangGraph):

Workflow определён в `infrastructure/workflow_graph.py` и использует LangGraph для управления состоянием и переходами.

1. Intent          → определение типа: create | modify | debug | optimize | explain | test | refactor | greeting
   • Если greeting → END (завершение workflow)
   • Иначе → Planner

2. Planner         → план + 2–3 альтернативных подхода
   • Использует Memory Agent (через DependencyContainer) для получения рекомендаций из прошлых задач
   • → Researcher

3. Researcher      → 
   • сначала локальный RAG (ChromaDB)
   • веб-поиск включается ТОЛЬКО если:
     - intent НЕ в {create, test, refactor, greeting, modify}
     - И (confidence < 0.7 ИЛИ мало результатов ИЛИ RAG пустой)
   • для explain/debug/optimize: поиск если RAG пустой
   • для modify/debug: загружает файл как контекст
   • результат → в контекст
   • → TestGenerator

4. TestGenerator   → пишем тесты ДО кода (pytest)
   • → Coder

5. Coder           → пишем код по тестам + плану (type hints, docstrings)
   • Использует PromptEnhancer для улучшения промптов
   • → Validator

6. Validator       → pytest, mypy, bandit
   • Условный переход:
     - Если all_passed или iteration >= max_iterations → Reflection
     - Иначе → Debugger (цикл self-healing)

7. Debugger        → цикл self-healing (если валидация провалилась):
   • анализирует ошибки (pytest, mypy, bandit)
   • генерирует конкретные инструкции для исправления
   • → Fixer

8. Fixer           → исправляет код по инструкциям от Debugger
   • Увеличивает iteration
   • → Validator (цикл)

9. Reflection      → анализ результата
   • оценка способностей системы (planning/coding/testing/etc)
   • сохраняет опыт в Memory Agent (через DependencyContainer)
   • → Critic

10. Critic         → критический анализ сгенерированного кода
    • оценивает качество, выявляет проблемы
    • формирует итоговый отчёт
    • → END

### Структура графа LangGraph

```
START → intent_node
intent_node → should_skip_greeting
should_skip_greeting → [skip: END, continue: planner_node]
planner_node → researcher_node
researcher_node → test_generator_node
test_generator_node → coder_node
coder_node → validator_node
validator_node → should_continue_self_healing
should_continue_self_healing → [continue: debugger_node, finish: reflection_node]
debugger_node → fixer_node
fixer_node → validator_node (цикл)
reflection_node → critic_node
critic_node → END
```

### Узлы и переходы

- **Узлы**: Определены в `infrastructure/workflow_nodes.py`
- **Условные переходы**: Определены в `infrastructure/workflow_edges.py`
- **State**: Определён в `infrastructure/workflow_state.py`
- **Граф**: Создаётся в `infrastructure/workflow_graph.py`

### Self-Healing цикл

Максимум max_iterations итераций (по умолчанию из config.toml, ограничено до 5):
- Validator (Fail) → Debugger → Fixer → Validator (повторная проверка)
- Если all_passed или iteration >= max_iterations → Reflection → Critic → END

### Dependency Injection

MemoryAgent и RAGSystem создаются через `backend/dependencies.py` (Singleton паттерн).
Все модули используют централизованные экземпляры:
```python
from backend.dependencies import get_memory_agent, get_rag_system

memory = get_memory_agent()  # Singleton
rag = get_rag_system()       # Singleton
```