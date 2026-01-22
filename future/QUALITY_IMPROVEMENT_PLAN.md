# План улучшения качества и развития проекта Cursor Killer

## Дата: 2026-01-21

---

## 📊 Общая оценка проекта

### Сильные стороны ✅
- **Современная архитектура**: LangGraph workflow, структурированный код
- **Reasoning models**: Поддержка DeepSeek-R1, QwQ с real-time стримингом
- **Хорошая документация**: README, ARCHITECTURE, ROADMAP
- **Модульность**: Чёткое разделение agents, infrastructure, backend
- **SmartModelRouter**: Умный выбор модели по сложности задачи
- **Тестовое покрытие**: 21 тестовый файл

### Слабые стороны ⚠️
- **Дублирование кода**: Синхронные + стриминговые агенты (переходная фаза)
- **Примитивный Context Engine**: Нет AST парсинга, графа зависимостей
- **Отсутствие Learning System**: Нет анализа паттернов успешности
- **Нет метрик**: Performance tracking отсутствует
- **Безопасность**: Нет аутентификации, валидации промптов
- **Observability**: Нет structured logging, трейсинга, дашбордов

---

## 🔴 КРИТИЧЕСКИЕ ПРОБЛЕМЫ (требуют немедленного исправления)

### 1. Безопасность (Priority: CRITICAL)

**Проблемы:**
- Нет аутентификации/авторизации
- Отсутствует валидация промптов (prompt injection)
- Нет rate limiting на критичных endpoints
- Веб-поиск может быть уязвим (SSRF)
- Отсутствует санитизация выполняемого кода

**Решение:**
```python
# backend/security/auth.py
"""Базовая аутентификация через API keys."""

from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import secrets

security = HTTPBearer()

# Хранение API keys (позже - в БД)
VALID_API_KEYS = set()

def generate_api_key() -> str:
    """Генерирует новый API ключ."""
    return secrets.token_urlsafe(32)

async def verify_api_key(credentials: HTTPAuthorizationCredentials = Security(security)):
    """Проверяет API ключ."""
    if credentials.credentials not in VALID_API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return credentials.credentials
```

```python
# backend/security/validation.py
"""Валидация и санитизация входных данных."""

import re
from typing import Optional

MAX_PROMPT_LENGTH = 50000
MAX_CODE_LENGTH = 100000
DANGEROUS_PATTERNS = [
    r'__import__\s*\(',
    r'eval\s*\(',
    r'exec\s*\(',
    r'compile\s*\(',
    r'os\.system',
    r'subprocess\.',
]

class SecurityError(Exception):
    """Ошибка безопасности."""
    pass

def validate_prompt(prompt: str) -> None:
    """Проверяет промпт на безопасность.
    
    Raises:
        SecurityError: Если промпт опасен
    """
    if not prompt or not prompt.strip():
        raise SecurityError("Empty prompt")
    
    if len(prompt) > MAX_PROMPT_LENGTH:
        raise SecurityError(f"Prompt too long: {len(prompt)} > {MAX_PROMPT_LENGTH}")
    
    # Базовая проверка на prompt injection
    suspicious = ['ignore previous', 'disregard', 'new instructions', 'system:']
    for pattern in suspicious:
        if pattern.lower() in prompt.lower():
            raise SecurityError(f"Suspicious pattern detected: {pattern}")

def validate_code(code: str) -> None:
    """Проверяет сгенерированный код на опасные конструкции."""
    if len(code) > MAX_CODE_LENGTH:
        raise SecurityError("Generated code too long")
    
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, code):
            raise SecurityError(f"Dangerous pattern: {pattern}")
```

**Checklist:**
- [ ] Добавить аутентификацию через API keys
- [ ] Валидация всех входных данных
- [ ] Rate limiting на `/api/stream` (10 req/min per user)
- [ ] Sandbox для выполнения кода
- [ ] HTTPS в production
- [ ] Документация security best practices

**Время:** 2-3 дня

---

### 2. Observability и мониторинг (Priority: HIGH)

**Проблемы:**
- Логи неструктурированные (сложно парсить)
- Нет метрик производительности
- Нет трейсинга для отладки
- Нет алертов при ошибках

**Решение:**

```python
# infrastructure/telemetry.py
"""Телеметрия и метрики."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
import time
import json
from pathlib import Path

@dataclass
class Metric:
    """Метрика производительности."""
    name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    tags: Dict[str, str] = field(default_factory=dict)

class MetricsCollector:
    """Сборщик метрик."""
    
    def __init__(self, output_file: Optional[Path] = None):
        self.metrics: List[Metric] = []
        self.output_file = output_file or Path("output/metrics.jsonl")
        self.output_file.parent.mkdir(exist_ok=True, parents=True)
    
    def record(self, name: str, value: float, **tags):
        """Записывает метрику."""
        metric = Metric(name=name, value=value, tags=tags)
        self.metrics.append(metric)
        
        # Append to JSONL file
        with open(self.output_file, 'a') as f:
            f.write(json.dumps({
                'name': metric.name,
                'value': metric.value,
                'timestamp': metric.timestamp.isoformat(),
                'tags': metric.tags
            }) + '\n')
    
    def timer(self, name: str, **tags):
        """Context manager для замера времени."""
        return MetricTimer(self, name, tags)

class MetricTimer:
    """Таймер для метрик."""
    
    def __init__(self, collector: MetricsCollector, name: str, tags: Dict):
        self.collector = collector
        self.name = name
        self.tags = tags
        self.start = 0.0
    
    def __enter__(self):
        self.start = time.time()
        return self
    
    def __exit__(self, *args):
        elapsed = time.time() - self.start
        self.collector.record(f"{self.name}_duration_seconds", elapsed, **self.tags)

# Глобальный коллектор
_metrics = MetricsCollector()

def get_metrics() -> MetricsCollector:
    return _metrics
```

```python
# infrastructure/logging/structured.py
"""Структурированное логирование."""

import logging
import json
from datetime import datetime
from typing import Any, Dict

class StructuredFormatter(logging.Formatter):
    """JSON форматтер для логов."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Добавляем extra поля
        if hasattr(record, 'extra'):
            log_data.update(record.extra)
        
        # Добавляем exception если есть
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)

def setup_structured_logging(level: int = logging.INFO):
    """Настраивает структурированное логирование."""
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredFormatter())
    
    logger = logging.getLogger()
    logger.setLevel(level)
    logger.addHandler(handler)
```

**Использование в агентах:**

```python
# agents/coder.py
from infrastructure.telemetry import get_metrics

class CoderAgent:
    def generate_code(self, ...):
        metrics = get_metrics()
        
        with metrics.timer("coder_generate", model=self.model, complexity=complexity):
            code = self.llm.generate(...)
        
        metrics.record("code_length_chars", len(code), model=self.model)
        
        return code
```

**Checklist:**
- [ ] Structured logging (JSON)
- [ ] Метрики производительности (latency, tokens, success rate)
- [ ] Dashboard для визуализации (Grafana или простой HTML)
- [ ] Alerts на ошибки (email/Telegram)
- [ ] OpenTelemetry integration (опционально)

**Время:** 3-4 дня

---

### 3. Дублирование кода и техдолг (Priority: MEDIUM)

**Проблемы:**
- Синхронные и стриминговые агенты дублируются
- Нет базового класса для агентов
- Много повторяющегося кода в промптах

**Решение:**

```python
# agents/base.py
"""Базовый класс для всех агентов."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, AsyncGenerator
from dataclasses import dataclass
from infrastructure.local_llm import LocalLLM, create_llm_for_stage
from infrastructure.telemetry import get_metrics
from utils.logger import get_logger

logger = get_logger()

@dataclass
class AgentConfig:
    """Конфигурация агента."""
    model: Optional[str] = None
    temperature: float = 0.25
    stage: str = "default"

class BaseAgent(ABC):
    """Базовый класс для всех агентов.
    
    Обеспечивает:
    - Ленивую инициализацию LLM
    - Автоматический сбор метрик
    - Единый интерфейс для синхронных/стриминговых операций
    - Обработку ошибок
    """
    
    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()
        self._llm: Optional[LocalLLM] = None
        self.metrics = get_metrics()
    
    @property
    def llm(self) -> LocalLLM:
        """Ленивая инициализация LLM."""
        if self._llm is None:
            self._llm = create_llm_for_stage(
                stage=self.config.stage,
                model=self.config.model or self._get_default_model(),
                temperature=self.config.temperature
            )
        return self._llm
    
    @abstractmethod
    def _get_default_model(self) -> str:
        """Возвращает модель по умолчанию для агента."""
        pass
    
    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """Синхронное выполнение основной операции агента."""
        pass
    
    async def execute_stream(self, **kwargs) -> AsyncGenerator:
        """Стриминговое выполнение (опционально)."""
        raise NotImplementedError(f"{self.__class__.__name__} не поддерживает стриминг")
    
    def _build_prompt(self, template: str, **kwargs) -> str:
        """Строит промпт из шаблона с валидацией."""
        from backend.security.validation import validate_prompt
        
        prompt = template.format(**kwargs)
        validate_prompt(prompt)
        return prompt
```

**Рефакторинг CoderAgent:**

```python
# agents/coder.py
from agents.base import BaseAgent, AgentConfig

class CoderAgent(BaseAgent):
    """Агент для генерации кода."""
    
    # Шаблон промпта вынесен в константу
    GENERATE_PROMPT = """You are an expert Python programmer.

TASK:
{plan}

TESTS TO PASS:
```python
{tests}
```

CONTEXT:
{context}

Generate clean, well-documented Python code that passes all tests.
Follow PEP8. Use type hints.

CODE:"""
    
    def __init__(self, model: Optional[str] = None, temperature: float = 0.25):
        super().__init__(AgentConfig(
            model=model,
            temperature=temperature,
            stage="coding"
        ))
    
    def _get_default_model(self) -> str:
        from infrastructure.model_router import get_model_router
        router = get_model_router()
        return router.select_model("coding").model
    
    def execute(self, plan: str, tests: str, context: str, **kwargs) -> str:
        """Генерирует код (синхронно)."""
        with self.metrics.timer("coder_execute", model=self.config.model):
            prompt = self._build_prompt(
                self.GENERATE_PROMPT,
                plan=plan,
                tests=tests,
                context=context
            )
            
            response = self.llm.generate(prompt, num_predict=4096)
            code = self._extract_code(response)
            
            self.metrics.record("code_generated_length", len(code))
            return code
    
    async def execute_stream(self, plan: str, tests: str, context: str, **kwargs):
        """Генерирует код с стримингом."""
        prompt = self._build_prompt(
            self.GENERATE_PROMPT,
            plan=plan,
            tests=tests,
            context=context
        )
        
        async for chunk in self.llm.generate_stream(prompt):
            if chunk.is_thinking:
                yield ("thinking", chunk.content)
            else:
                yield ("code_chunk", chunk.content)
        
        yield ("done", chunk.full_response)
```

**Checklist:**
- [ ] Создать BaseAgent с общей логикой
- [ ] Рефакторинг всех агентов на BaseAgent
- [ ] Вынести промпты в константы/файлы
- [ ] Удалить дублирующийся код
- [ ] Обновить тесты

**Время:** 4-5 дней

---

## 🟡 ВАЖНЫЕ УЛУЧШЕНИЯ (следующий спринт)

### 4. Context Engine v2 (Priority: HIGH)

**Текущие проблемы:**
- Простое разбиение на чанки без учёта AST
- Нет графа зависимостей
- Нет иерархических сводок
- Примитивная оценка релевантности

**Решение - поэтапное улучшение:**

**Этап 1: AST парсинг (1-2 дня)**

```python
# infrastructure/context_engine_v2/ast_analyzer.py
"""AST анализ для точного понимания структуры кода."""

import ast
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional
from pathlib import Path

@dataclass
class CodeEntity:
    """Сущность кода (функция, класс, модуль)."""
    name: str
    type: str  # "function" | "class" | "method" | "module"
    file_path: str
    start_line: int
    end_line: int
    signature: str
    docstring: Optional[str] = None
    
    # Зависимости
    imports: List[str] = field(default_factory=list)
    calls: List[str] = field(default_factory=list)
    inherits_from: List[str] = field(default_factory=list)
    
    # Метрики
    complexity: int = 0  # Cyclomatic complexity
    lines_of_code: int = 0

class ASTAnalyzer:
    """Анализирует код через AST."""
    
    def analyze_file(self, file_path: Path) -> List[CodeEntity]:
        """Парсит файл и извлекает сущности."""
        content = file_path.read_text()
        tree = ast.parse(content)
        
        entities: List[CodeEntity] = []
        
        # Извлекаем imports
        imports = self._extract_imports(tree)
        
        # Извлекаем функции и классы
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                entity = self._analyze_function(node, file_path, content, imports)
                entities.append(entity)
            elif isinstance(node, ast.ClassDef):
                entity = self._analyze_class(node, file_path, content, imports)
                entities.append(entity)
        
        return entities
    
    def _extract_imports(self, tree: ast.AST) -> List[str]:
        """Извлекает все импорты."""
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}")
        return imports
    
    def _analyze_function(
        self,
        node: ast.FunctionDef,
        file_path: Path,
        content: str,
        imports: List[str]
    ) -> CodeEntity:
        """Анализирует функцию."""
        # Извлекаем вызовы функций
        calls = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    calls.append(child.func.id)
        
        # Cyclomatic complexity
        complexity = self._calculate_complexity(node)
        
        return CodeEntity(
            name=node.name,
            type="function",
            file_path=str(file_path),
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            signature=self._get_signature(node, content),
            docstring=ast.get_docstring(node),
            imports=imports,
            calls=calls,
            complexity=complexity,
            lines_of_code=(node.end_lineno or node.lineno) - node.lineno
        )
    
    def _calculate_complexity(self, node: ast.AST) -> int:
        """Вычисляет цикломатическую сложность."""
        complexity = 1  # Базовая сложность
        
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        
        return complexity
    
    # ... остальные методы
```

**Этап 2: Граф зависимостей (2-3 дня)**

```python
# infrastructure/context_engine_v2/dependency_graph.py
"""Граф зависимостей кода."""

from typing import Dict, List, Set
from dataclasses import dataclass
import networkx as nx

@dataclass
class DependencyGraph:
    """Граф зависимостей проекта."""
    
    def __init__(self):
        self.graph = nx.DiGraph()
    
    def add_entity(self, entity: CodeEntity):
        """Добавляет сущность в граф."""
        self.graph.add_node(
            entity.name,
            type=entity.type,
            file=entity.file_path,
            complexity=entity.complexity
        )
        
        # Добавляем рёбра зависимостей
        for call in entity.calls:
            self.graph.add_edge(entity.name, call, type="calls")
        
        for parent in entity.inherits_from:
            self.graph.add_edge(entity.name, parent, type="inherits")
    
    def get_dependencies(self, entity_name: str, max_depth: int = 2) -> List[str]:
        """Получает зависимости сущности."""
        if entity_name not in self.graph:
            return []
        
        # BFS для поиска зависимостей
        dependencies = []
        visited = set()
        queue = [(entity_name, 0)]
        
        while queue:
            current, depth = queue.pop(0)
            if current in visited or depth > max_depth:
                continue
            
            visited.add(current)
            dependencies.append(current)
            
            # Добавляем соседей
            for neighbor in self.graph.successors(current):
                queue.append((neighbor, depth + 1))
        
        return dependencies[1:]  # Исключаем саму сущность
    
    def get_important_entities(self, top_n: int = 10) -> List[str]:
        """Находит важные сущности через PageRank."""
        if len(self.graph) == 0:
            return []
        
        pagerank = nx.pagerank(self.graph)
        sorted_entities = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)
        
        return [name for name, score in sorted_entities[:top_n]]
```

**Checklist:**
- [ ] AST парсинг для Python
- [ ] Граф зависимостей через networkx
- [ ] PageRank для важности
- [ ] Интеграция с ResearcherAgent
- [ ] Кэширование графа
- [ ] Тесты

**Время:** 4-5 дней

---

### 5. Learning System (Priority: MEDIUM)

**Цель:** Система должна учиться на своих успехах и ошибках.

```python
# infrastructure/learning_system.py
"""Система обучения на опыте."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict
from pathlib import Path

@dataclass
class TaskResult:
    """Результат выполнения задачи."""
    task: str
    intent_type: str
    complexity: str
    model_used: str
    success: bool
    quality_score: float
    duration_seconds: float
    error_type: Optional[str] = None
    timestamp: datetime = datetime.now()

class LearningSystem:
    """Система обучения и аналитики."""
    
    def __init__(self, db_path: Path = Path("output/learning.db")):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Инициализирует БД."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS task_results (
                    id INTEGER PRIMARY KEY,
                    task TEXT,
                    intent_type TEXT,
                    complexity TEXT,
                    model_used TEXT,
                    success BOOLEAN,
                    quality_score REAL,
                    duration_seconds REAL,
                    error_type TEXT,
                    timestamp DATETIME
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS model_performance (
                    model_name TEXT,
                    task_type TEXT,
                    complexity TEXT,
                    avg_quality REAL,
                    success_rate REAL,
                    avg_duration REAL,
                    total_tasks INTEGER,
                    last_updated DATETIME,
                    PRIMARY KEY (model_name, task_type, complexity)
                )
            """)
    
    def record_result(self, result: TaskResult):
        """Записывает результат задачи."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO task_results (
                    task, intent_type, complexity, model_used,
                    success, quality_score, duration_seconds,
                    error_type, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.task, result.intent_type, result.complexity,
                result.model_used, result.success, result.quality_score,
                result.duration_seconds, result.error_type,
                result.timestamp
            ))
        
        # Обновляем статистику модели
        self._update_model_stats(result)
    
    def _update_model_stats(self, result: TaskResult):
        """Обновляет статистику производительности модели."""
        with sqlite3.connect(self.db_path) as conn:
            # Получаем текущую статистику
            row = conn.execute("""
                SELECT avg_quality, success_rate, avg_duration, total_tasks
                FROM model_performance
                WHERE model_name = ? AND task_type = ? AND complexity = ?
            """, (result.model_used, result.intent_type, result.complexity)).fetchone()
            
            if row:
                # Обновляем скользящее среднее
                avg_quality, success_rate, avg_duration, total = row
                new_total = total + 1
                
                new_avg_quality = (avg_quality * total + result.quality_score) / new_total
                new_success_rate = (success_rate * total + (1 if result.success else 0)) / new_total
                new_avg_duration = (avg_duration * total + result.duration_seconds) / new_total
                
                conn.execute("""
                    UPDATE model_performance
                    SET avg_quality = ?, success_rate = ?, avg_duration = ?,
                        total_tasks = ?, last_updated = ?
                    WHERE model_name = ? AND task_type = ? AND complexity = ?
                """, (
                    new_avg_quality, new_success_rate, new_avg_duration,
                    new_total, datetime.now(),
                    result.model_used, result.intent_type, result.complexity
                ))
            else:
                # Первая запись
                conn.execute("""
                    INSERT INTO model_performance VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    result.model_used, result.intent_type, result.complexity,
                    result.quality_score, 1 if result.success else 0,
                    result.duration_seconds, 1, datetime.now()
                ))
    
    def get_best_model(self, task_type: str, complexity: str) -> Optional[str]:
        """Находит лучшую модель для задачи."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("""
                SELECT model_name, avg_quality, success_rate
                FROM model_performance
                WHERE task_type = ? AND complexity = ?
                  AND total_tasks >= 5  -- Минимум 5 задач для надёжности
                ORDER BY (avg_quality * 0.7 + success_rate * 0.3) DESC
                LIMIT 1
            """, (task_type, complexity)).fetchone()
            
            return row[0] if row else None
    
    def get_common_errors(self, limit: int = 10) -> List[Dict]:
        """Находит частые ошибки."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("""
                SELECT error_type, COUNT(*) as count,
                       AVG(quality_score) as avg_quality
                FROM task_results
                WHERE success = 0 AND error_type IS NOT NULL
                GROUP BY error_type
                ORDER BY count DESC
                LIMIT ?
            """, (limit,)).fetchall()
            
            return [
                {'error_type': row[0], 'count': row[1], 'avg_quality': row[2]}
                for row in rows
            ]
```

**Интеграция в workflow:**

```python
# infrastructure/workflow_nodes.py

from infrastructure.learning_system import LearningSystem, TaskResult

learning = LearningSystem()

@workflow_node(stage="reflection")
async def reflection_node(state: AgentState) -> AgentState:
    # ... существующий код рефлексии ...
    
    # Записываем результат в Learning System
    result = TaskResult(
        task=state.get("task", ""),
        intent_type=state.get("intent_result").type,
        complexity=state.get("intent_result").complexity.value,
        model_used=state.get("model", "unknown"),
        success=state.get("validation_results", {}).get("all_passed", False),
        quality_score=reflection_result.overall_score,
        duration_seconds=time.time() - state.get("start_time", time.time()),
        error_type=state.get("debug_result").error_type if state.get("debug_result") else None
    )
    
    learning.record_result(result)
    
    return state
```

**Checklist:**
- [ ] SQLite БД для результатов
- [ ] Запись результатов после каждой задачи
- [ ] Статистика производительности моделей
- [ ] API для получения рекомендаций
- [ ] Dashboard для визуализации
- [ ] Экспорт данных в CSV/JSON

**Время:** 3-4 дня

---

## 🟢 ДОПОЛНИТЕЛЬНЫЕ УЛУЧШЕНИЯ (бэклог)

### 6. Performance Optimization

**Цели:**
- Уменьшить latency на 30%
- Увеличить throughput в 2x
- Снизить memory usage на 20%

**Методы:**
1. **Connection Pooling везде:**
   - Использовать httpx pool для Ollama
   - Redis для кэша (опционально)

2. **Параллелизация:**
   - Параллельный запуск независимых агентов (Researcher + TestGenerator)
   - Batch processing для нескольких задач

3. **Кэширование:**
   - LRU cache для частых запросов
   - Кэш LLM ответов для одинаковых промптов

4. **Оптимизация промптов:**
   - Сократить промпты на 20-30%
   - Убрать избыточные инструкции

**Время:** 5-7 дней

---

### 7. Frontend Improvements

**Необходимо:**

1. **ThinkingBlock компонент:**
```tsx
// frontend/src/components/ThinkingBlock.tsx
import { useState } from 'react'
import { ChevronDown, Brain } from 'lucide-react'

interface ThinkingBlockProps {
  content: string
  isStreaming?: boolean
}

export function ThinkingBlock({ content, isStreaming = false }: ThinkingBlockProps) {
  const [collapsed, setCollapsed] = useState(true)
  
  return (
    <div className="border border-blue-300 rounded-lg bg-blue-50 dark:bg-blue-900/20 p-4">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center gap-2 text-blue-700 dark:text-blue-300"
      >
        <Brain size={16} />
        <span className="font-medium">
          {isStreaming ? 'Thinking...' : 'Reasoning Process'}
        </span>
        <ChevronDown
          size={16}
          className={`transition-transform ${collapsed ? '' : 'rotate-180'}`}
        />
      </button>
      
      {!collapsed && (
        <pre className="mt-3 text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">
          {content}
        </pre>
      )}
    </div>
  )
}
```

2. **Прогресс-бар для долгих операций:**
```tsx
// frontend/src/components/ProgressBar.tsx
import { Progress } from '@/components/ui/progress'

const STAGES = [
  'intent', 'planning', 'research', 'testing',
  'coding', 'validation', 'reflection'
]

export function WorkflowProgress({ currentStage }: { currentStage: string }) {
  const progress = (STAGES.indexOf(currentStage) + 1) / STAGES.length * 100
  
  return (
    <div className="space-y-2">
      <Progress value={progress} className="h-2" />
      <div className="flex justify-between text-xs text-gray-500">
        {STAGES.map(stage => (
          <span
            key={stage}
            className={currentStage === stage ? 'text-blue-600 font-medium' : ''}
          >
            {stage}
          </span>
        ))}
      </div>
    </div>
  )
}
```

3. **Offline mode:**
   - Service Worker для кэширования
   - IndexedDB для локального хранения диалогов
   - Sync при восстановлении подключения

**Время:** 4-5 дней

---

### 8. Testing Improvements

**Текущая проблема:** Нет покрытия, нет E2E тестов

**План:**

1. **Unit тесты - цель 80% покрытие:**
```bash
pytest tests/ --cov=agents --cov=infrastructure --cov-report=html
```

2. **Integration тесты:**
```python
# tests/test_integration_workflow.py
"""E2E тесты полного workflow."""

import pytest
from infrastructure.workflow_graph import create_workflow

@pytest.mark.asyncio
async def test_full_workflow_simple_task():
    """Тест полного workflow для простой задачи."""
    workflow = create_workflow()
    
    initial_state = {
        "task": "напиши функцию для сложения двух чисел",
        "model": "qwen2.5-coder:7b",
        "temperature": 0.25
    }
    
    # Запускаем workflow
    final_state = await workflow.ainvoke(initial_state)
    
    # Проверяем результат
    assert final_state["code"] != ""
    assert "def " in final_state["code"]
    assert final_state["validation_results"]["all_passed"] == True
    assert final_state["reflection_result"].overall_score > 0.7
```

3. **Load tests:**
```python
# tests/test_load.py
"""Нагрузочные тесты."""

import asyncio
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_concurrent_requests():
    """Тест 10 одновременных запросов."""
    async with AsyncClient() as client:
        tasks = [
            client.get("http://localhost:8000/api/stream?task=hello")
            for _ in range(10)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Все должны завершиться успешно
        assert all(r.status_code == 200 for r in results)
```

**Время:** 5-6 дней

---

## 📅 Roadmap реализации

### Спринт 1 (2 недели): КРИТИЧЕСКИЕ ПРОБЛЕМЫ
- [ ] Безопасность (authentication, validation)
- [ ] Observability (structured logging, metrics)
- [ ] Рефакторинг дублирования (BaseAgent)

**Результат:** Продакшн-готовая система с security и monitoring

---

### Спринт 2 (2 недели): ВАЖНЫЕ УЛУЧШЕНИЯ
- [ ] Context Engine v2 (AST + граф зависимостей)
- [ ] Learning System (SQLite analytics)
- [ ] Performance optimization (connection pool, caching)

**Результат:** Улучшение качества генерации и скорости

---

### Спринт 3 (2 недели): ДОПОЛНИТЕЛЬНЫЕ ФИЧИ
- [ ] Frontend improvements (ThinkingBlock, ProgressBar, offline)
- [ ] Testing (80% coverage, E2E, load tests)
- [ ] Code Retrieval (Фаза 4 из roadmap)

**Результат:** Полированный UX и надёжность

---

### Спринт 4 (1-2 недели): БУДУЩЕЕ
- [ ] Multi-Agent Debate (Фаза 5)
- [ ] Tree-sitter для мультиязычности
- [ ] Распределённая обработка (Celery/RQ)

**Результат:** Масштабируемая enterprise-система

---

## 🎯 Метрики успеха

### Качество кода
- [ ] Code coverage >= 80%
- [ ] Type hints coverage >= 90%
- [ ] No critical security issues
- [ ] Linter warnings < 10

### Производительность
- [ ] Median latency < 30s для simple задач
- [ ] Median latency < 120s для complex задач
- [ ] Throughput >= 10 req/min
- [ ] Memory usage < 2GB

### Качество генерации
- [ ] Success rate >= 85% для simple
- [ ] Success rate >= 70% для medium
- [ ] Success rate >= 60% для complex
- [ ] Код компилируется сразу >= 80%

### UX/Frontend
- [ ] Loading state для всех операций
- [ ] Error handling для всех случаев
- [ ] Mobile responsive
- [ ] Accessibility (WCAG AA)

---

## 💡 Рекомендации

### Архитектурные принципы
1. **Постепенность:** Не переписывать всё сразу, инкрементально улучшать
2. **Backward compatibility:** Сохранять совместимость API при рефакторинге
3. **Test-driven:** Писать тесты ПЕРЕД рефакторингом
4. **Documentation-first:** Обновлять доки одновременно с кодом
5. **Метрики:** Измерять всё, оптимизировать на основе данных

### Практики разработки
1. **Code review:** Все изменения через PR с review
2. **CI/CD:** Автотесты на каждый commit
3. **Conventional commits:** Структурированные commit messages
4. **Semantic versioning:** Понятная система версий
5. **Changelog:** Документировать все изменения

### Приоритизация
- **Security first:** Безопасность важнее функциональности
- **User experience:** UX важнее технических деталей
- **Performance:** Скорость важнее избыточной функциональности
- **Simplicity:** Простота важнее сложной архитектуры

---

## 🔗 Связанные документы

- [ROADMAP_2026.md](ROADMAP_2026.md) - Общий roadmap
- [code_retrieval.md](code_retrieval.md) - Детали Фазы 4
- [context_engine_ast_parsing.md](context_engine_ast_parsing.md) - Детали Фазы 6
- [../ARCHITECTURE.md](../ARCHITECTURE.md) - Архитектура проекта
- [../DEPRECATION.md](../DEPRECATION.md) - План удаления устаревшего кода

---

**Автор:** AI Assistant  
**Дата создания:** 2026-01-21  
**Версия:** 1.0
