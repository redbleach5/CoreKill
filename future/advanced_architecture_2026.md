# Архитектура нового поколения: 2026

## Статус: 🚀 ПРИОРИТЕТ

## Цель

Переход от prompt-based архитектуры к cutting-edge подходам:
- **Reasoning models** вместо prompt engineering
- **Compiler-in-the-loop** вместо отложенной валидации
- **Code retrieval** вместо описательных промптов
- **Multi-agent debate** для критического анализа
- **Structured output** с гарантиями формата

---

## Текущие проблемы

| Проблема | Текущее решение | Ограничение |
|----------|-----------------|-------------|
| Классификация intent | Промпт + JSON parsing | Хрупко, галлюцинации |
| Генерация кода | Длинные инструкции | Модель может игнорировать |
| Валидация | В конце workflow | Поздняя обратная связь |
| Анализ проекта | Промпт для ChatAgent | Нет глубокого понимания |
| Критика кода | Промпт для CriticAgent | Субъективно |

---

## Новая архитектура

### 1. Reasoning Models (DeepSeek-R1, Qwen-QwQ)

**Что это:** Модели с встроенным chain-of-thought, которые САМИ рассуждают.

**Зачем:** Не нужны сложные промпты типа "think step by step". Модель сама разбивает задачу на шаги.

**Реализация:**
```python
# model_router.py
REASONING_MODELS = {
    "deepseek-r1:7b": {"reasoning": True, "quality": 0.95},
    "deepseek-r1:14b": {"reasoning": True, "quality": 0.98},
    "qwq:32b": {"reasoning": True, "quality": 0.97},
}

def select_model_for_complexity(self, complexity, task_type):
    if complexity == TaskComplexity.COMPLEX:
        # Предпочитаем reasoning модели для сложных задач
        return self._find_reasoning_model() or self._find_best_quality()
```

**Преимущества:**
- Меньше prompt engineering
- Лучше качество на сложных задачах
- Самоисправление ошибок рассуждения

---

### 2. Compiler-in-the-Loop (Tight Feedback)

**Что это:** Запуск кода СРАЗУ после генерации каждого блока, не в конце.

**Зачем:** Ранняя обратная связь = меньше исправлений в конце.

**Текущий workflow:**
```
Plan → Research → Tests → Code → Validate → Debug → Fix
                                    ↑
                            (слишком поздно!)
```

**Новый workflow:**
```
Plan → Research → Tests
                    ↓
              [Generate function 1]
                    ↓
              [Run tests for function 1] ← immediate feedback
                    ↓
              [Fix if needed]
                    ↓
              [Generate function 2]
                    ...
```

**Реализация:**
```python
# agents/incremental_coder.py
class IncrementalCoder:
    """Генерирует и валидирует код по частям."""
    
    async def generate_with_feedback(self, plan: str, tests: str) -> str:
        functions = self._parse_plan_into_functions(plan)
        code_parts = []
        
        for func_spec in functions:
            # Генерируем одну функцию
            func_code = await self._generate_function(func_spec)
            
            # Сразу запускаем тесты для неё
            result = await self._run_partial_tests(code_parts + [func_code], tests)
            
            if not result.passed:
                # Исправляем СРАЗУ, пока контекст свежий
                func_code = await self._fix_with_error(func_code, result.error)
            
            code_parts.append(func_code)
        
        return "\n\n".join(code_parts)
```

**Преимущества:**
- Ошибки ловятся рано
- Контекст ошибки свежий
- Меньше итераций debug-fix

---

### 3. Code Retrieval (Example-Based Generation)

**Что это:** Вместо описания "как писать код" — находим похожий код и даём как пример.

**Зачем:** Примеры работают лучше инструкций. "Show, don't tell."

**Реализация:**
```python
# infrastructure/code_retrieval.py
class CodeRetriever:
    """Поиск похожего кода для few-shot примеров."""
    
    def __init__(self):
        self.local_index = CodebaseIndex()  # Локальный проект
        self.github_search = GitHubCodeSearch()  # Открытые репозитории
        self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    
    def find_similar_code(self, task_description: str, n: int = 3) -> List[CodeExample]:
        """Находит похожие реализации."""
        # 1. Поиск в локальном проекте
        local_examples = self.local_index.search(task_description, n=2)
        
        # 2. Поиск в GitHub (если локальных мало)
        if len(local_examples) < n:
            github_examples = self.github_search.search(
                query=task_description,
                language="python",
                n=n - len(local_examples)
            )
            local_examples.extend(github_examples)
        
        return local_examples


# Использование в CoderAgent
class CoderAgent:
    def generate_code(self, task: str, plan: str, ...) -> str:
        # Находим похожий код
        examples = self.retriever.find_similar_code(task, n=3)
        
        # Даём модели примеры вместо длинных инструкций
        prompt = f"""Generate code similar to these examples:

{self._format_examples(examples)}

Task: {task}
Plan: {plan}

Code:"""
```

**Преимущества:**
- Модель видит РЕАЛЬНЫЙ рабочий код
- Меньше "галлюцинаций" в синтаксисе
- Стиль кода консистентный с проектом

---

### 4. Multi-Agent Debate

**Что это:** Несколько агентов с разными "точками зрения" обсуждают решение.

**Зачем:** Один агент может пропустить баг. Три — вряд ли.

**Реализация:**
```python
# infrastructure/debate.py
class DebateOrchestrator:
    """Оркестрирует дебаты между агентами."""
    
    def __init__(self):
        self.agents = [
            Agent(role="implementer", bias="get it working"),
            Agent(role="security_reviewer", bias="find vulnerabilities"),
            Agent(role="performance_critic", bias="find inefficiencies"),
        ]
    
    async def debate(self, code: str, max_rounds: int = 3) -> DebateResult:
        issues = []
        
        for round in range(max_rounds):
            for agent in self.agents:
                critique = await agent.review(code, previous_issues=issues)
                issues.extend(critique.new_issues)
            
            if not any(i.severity == "high" for i in issues):
                break  # Консенсус достигнут
            
            # Implementer исправляет критические issues
            code = await self.agents[0].fix(code, high_severity_issues(issues))
        
        return DebateResult(final_code=code, issues=issues, rounds=round + 1)
```

**Преимущества:**
- Разные перспективы на код
- Баги ловятся до продакшена
- Самоулучшающийся цикл

---

### 5. Structured Output с Pydantic

**Что это:** Гарантированный формат ответа через JSON Schema + валидация.

**Зачем:** Никаких "парсинг не удался", "модель вернула мусор".

**Реализация:**
```python
# agents/intent.py
from pydantic import BaseModel, Field
from enum import Enum

class IntentType(str, Enum):
    CREATE = "create"
    MODIFY = "modify"
    DEBUG = "debug"
    ANALYZE = "analyze"
    EXPLAIN = "explain"
    # ...

class IntentResponse(BaseModel):
    intent: IntentType
    confidence: float = Field(ge=0.0, le=1.0)
    complexity: str = Field(pattern="^(simple|medium|complex)$")
    reasoning: str  # Почему модель так решила

class IntentAgent:
    def determine_intent(self, query: str) -> IntentResponse:
        response = self.llm.generate(
            prompt=f"Classify: {query}",
            format="json",
            schema=IntentResponse.model_json_schema()
        )
        
        # Pydantic валидирует и гарантирует формат
        return IntentResponse.model_validate_json(response)
```

**Преимущества:**
- Гарантированный формат
- Автоматическая валидация
- Type safety в IDE

---

### 6. AST-Based Analysis (не LLM)

**Что это:** Анализ кода через парсинг AST, а не через промпты.

**Зачем:** AST не галлюцинирует. 100% точность для структурного анализа.

**Где применять:**
- Подсчёт функций/классов → AST
- Граф зависимостей → AST
- Поиск unused imports → AST
- Определение сложности → AST metrics (cyclomatic complexity)

**Где НЕ применять (оставить LLM):**
- Понимание intent пользователя
- Генерация нового кода
- Объяснение что делает код
- Креативные задачи

**Реализация:**
```python
# infrastructure/ast_analyzer.py
import ast
from dataclasses import dataclass

@dataclass
class CodeMetrics:
    functions: int
    classes: int
    lines_of_code: int
    cyclomatic_complexity: float
    imports: List[str]
    dependencies: Dict[str, List[str]]

class ASTAnalyzer:
    """Анализ кода без LLM — только AST."""
    
    def analyze(self, code: str) -> CodeMetrics:
        tree = ast.parse(code)
        
        return CodeMetrics(
            functions=self._count_functions(tree),
            classes=self._count_classes(tree),
            lines_of_code=len(code.splitlines()),
            cyclomatic_complexity=self._calculate_complexity(tree),
            imports=self._extract_imports(tree),
            dependencies=self._build_dependency_graph(tree)
        )
```

---

## План миграции

### Фаза 1: Reasoning Models (1-2 дня)
- [ ] Добавить DeepSeek-R1 в model_router
- [ ] Обновить select_model_for_complexity
- [ ] Тесты на reasoning задачах

### Фаза 2: Structured Output (1 день)
- [ ] Pydantic модели для всех агентов
- [ ] Миграция IntentAgent на structured output
- [ ] Валидация через JSON Schema

### Фаза 3: Compiler-in-the-Loop (2-3 дня)
- [ ] IncrementalCoder с пошаговой валидацией
- [ ] Интеграция в workflow
- [ ] Метрики времени до первой ошибки

### Фаза 4: Code Retrieval (2-3 дня)
- [ ] Локальный индекс через embeddings
- [ ] GitHub Code Search интеграция
- [ ] Few-shot примеры в промптах

### Фаза 5: Multi-Agent Debate (2 дня)
- [ ] DebateOrchestrator
- [ ] Специализированные reviewer агенты
- [ ] Интеграция в critic stage

### Фаза 6: AST Analysis (1-2 дня)
- [ ] ASTAnalyzer для метрик
- [ ] Замена промптов на AST где возможно
- [ ] Граф зависимостей

---

## Метрики успеха

| Метрика | Текущее | Цель |
|---------|---------|------|
| Первая успешная компиляция | ~60% | >85% |
| Среднее кол-во debug итераций | 2.5 | <1.5 |
| Время до рабочего кода | ~45 сек | <30 сек |
| Точность intent classification | ~85% | >95% |
| Покрытие edge cases | ~70% | >90% |

---

## Зависимости

```toml
# requirements.txt additions
deepseek-r1  # Через Ollama
pydantic>=2.0
sentence-transformers  # Для embeddings
PyGithub  # Для GitHub Code Search (опционально)
```

---

## Риски и митигация

| Риск | Митигация |
|------|-----------|
| DeepSeek-R1 требует много VRAM | Fallback на qwen2.5-coder |
| GitHub API rate limits | Кэширование + локальный индекс |
| Сложность отладки multi-agent | Детальное логирование каждого агента |
| Breaking changes в workflow | Feature flags для постепенного rollout |

---

## Связанные документы

- `future/context_engine_ast_parsing.md` — AST для Context Engine
- `future/tree_sitter_multilang.md` — Мультиязычный парсинг
- `future/migrate_agents_to_chat_api.md` — Миграция на chat API
- `.cursor/rules/architecture.md` — Текущая архитектура
