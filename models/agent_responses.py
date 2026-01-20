"""Pydantic модели для структурированных ответов агентов.

Обеспечивают:
- Гарантированный формат ответов через JSON Schema
- Автоматическую валидацию типов
- Type safety в IDE
- Документацию через Field descriptions

Использование:
    from models import IntentResponse
    
    response = llm.generate_structured(prompt, IntentResponse)
    # response теперь типизирован и валидирован
"""
from enum import Enum
from typing import List, Optional, Literal

from pydantic import BaseModel, Field, ConfigDict


# ===== Intent Agent =====

class IntentType(str, Enum):
    """Типы намерений пользователя."""
    GREETING = "greeting"     # Приветствие (привет, hello)
    HELP = "help"             # Вопрос о возможностях системы
    CREATE = "create"         # Создать новый код
    MODIFY = "modify"         # Изменить существующий код
    DEBUG = "debug"           # Найти и исправить баги
    OPTIMIZE = "optimize"     # Улучшить производительность
    EXPLAIN = "explain"       # Объяснить код
    TEST = "test"             # Написать тесты
    REFACTOR = "refactor"     # Реструктурировать код
    ANALYZE = "analyze"       # Анализ проекта/кодовой базы


class IntentResponse(BaseModel):
    """Структурированный ответ IntentAgent.
    
    Example:
        {
            "intent": "create",
            "confidence": 0.95,
            "complexity": "medium",
            "reasoning": "Пользователь просит создать новую функцию"
        }
    """
    model_config = ConfigDict(use_enum_values=True)
    
    intent: IntentType = Field(description="Тип намерения пользователя")
    confidence: float = Field(
        ge=0.0, le=1.0, 
        description="Уверенность классификации 0-1"
    )
    complexity: Literal["simple", "medium", "complex"] = Field(
        description="Сложность задачи: simple (<100 строк), medium (100-500), complex (500+)"
    )
    reasoning: Optional[str] = Field(
        default=None, 
        description="Почему выбран этот intent (опционально)"
    )


# ===== Planner Agent =====

class PlanStep(BaseModel):
    """Один шаг плана реализации."""
    step_number: int = Field(ge=1, description="Номер шага")
    action: str = Field(min_length=5, description="Описание действия")
    expected_output: str = Field(description="Ожидаемый результат")
    dependencies: List[int] = Field(
        default_factory=list, 
        description="Номера шагов, от которых зависит этот шаг"
    )


class PlanResponse(BaseModel):
    """Структурированный ответ PlannerAgent.
    
    Example:
        {
            "goal": "Создать HTTP клиент",
            "steps": [
                {"step_number": 1, "action": "Создать класс HTTPClient", ...}
            ],
            "estimated_complexity": "medium",
            "suggested_approach": "Использовать httpx для async"
        }
    """
    goal: str = Field(description="Цель задачи")
    steps: List[PlanStep] = Field(min_length=1, description="Шаги реализации")
    estimated_complexity: Literal["simple", "medium", "complex"] = Field(
        description="Оценка сложности"
    )
    suggested_approach: str = Field(description="Рекомендуемый подход")


# ===== Debugger Agent =====

class ErrorType(str, Enum):
    """Типы ошибок."""
    SYNTAX = "syntax"       # Синтаксическая ошибка
    RUNTIME = "runtime"     # Ошибка во время выполнения
    LOGIC = "logic"         # Логическая ошибка
    TYPE = "type"           # Ошибка типов
    IMPORT = "import"       # Ошибка импорта
    TEST = "test"           # Ошибка теста (assertion failed)


class DebugResponse(BaseModel):
    """Структурированный ответ DebuggerAgent.
    
    Example:
        {
            "error_type": "type",
            "error_location": "utils/parser.py:42",
            "root_cause": "Передаётся str вместо int",
            "fix_instructions": "Добавить int() преобразование",
            "confidence": 0.9
        }
    """
    model_config = ConfigDict(use_enum_values=True)
    
    error_type: ErrorType = Field(description="Категория ошибки")
    error_location: str = Field(description="Место ошибки (файл:строка)")
    root_cause: str = Field(description="Корневая причина ошибки")
    fix_instructions: str = Field(description="Инструкции по исправлению")
    confidence: float = Field(ge=0.0, le=1.0, description="Уверенность в диагнозе")


# ===== Critic Agent =====

class IssueSeverity(str, Enum):
    """Серьёзность проблемы."""
    LOW = "low"             # Незначительная (стиль, форматирование)
    MEDIUM = "medium"       # Средняя (потенциальный баг)
    HIGH = "high"           # Высокая (серьёзный баг)
    CRITICAL = "critical"   # Критическая (безопасность, потеря данных)


class CodeIssue(BaseModel):
    """Одна проблема в коде."""
    model_config = ConfigDict(use_enum_values=True)
    
    severity: IssueSeverity = Field(description="Серьёзность")
    category: str = Field(
        description="Категория: security, performance, style, logic, maintainability"
    )
    location: str = Field(description="Место в коде")
    description: str = Field(description="Описание проблемы")
    suggestion: str = Field(description="Как исправить")


class CriticResponse(BaseModel):
    """Структурированный ответ CriticAgent.
    
    Example:
        {
            "overall_score": 0.75,
            "issues": [...],
            "strengths": ["Хорошее покрытие тестами"],
            "summary": "Код работает, но есть проблемы с производительностью"
        }
    """
    overall_score: float = Field(
        ge=0.0, le=1.0, 
        description="Общая оценка качества 0-1"
    )
    issues: List[CodeIssue] = Field(
        default_factory=list, 
        description="Найденные проблемы"
    )
    strengths: List[str] = Field(
        default_factory=list, 
        description="Сильные стороны кода"
    )
    summary: str = Field(description="Общее резюме")


# ===== Reflection Agent =====

class ReflectionResponse(BaseModel):
    """Структурированный ответ ReflectionAgent.
    
    Example:
        {
            "planning_score": 0.8,
            "research_score": 0.9,
            "testing_score": 0.7,
            "coding_score": 0.85,
            "overall_score": 0.81,
            "analysis": "Хорошая реализация, но тесты неполные",
            "improvements": ["Добавить edge cases", "Улучшить документацию"],
            "should_retry": false
        }
    """
    planning_score: float = Field(ge=0.0, le=1.0, description="Оценка планирования")
    research_score: float = Field(ge=0.0, le=1.0, description="Оценка исследования")
    testing_score: float = Field(ge=0.0, le=1.0, description="Оценка тестов")
    coding_score: float = Field(ge=0.0, le=1.0, description="Оценка кода")
    overall_score: float = Field(ge=0.0, le=1.0, description="Общая оценка")
    analysis: str = Field(description="Анализ результатов")
    improvements: List[str] = Field(
        default_factory=list, 
        description="Рекомендации по улучшению"
    )
    should_retry: bool = Field(
        default=False, 
        description="Нужна ли повторная попытка"
    )


# ===== Analyze Response =====

class ProjectStructure(BaseModel):
    """Структура проекта."""
    main_directories: List[str] = Field(description="Основные директории")
    key_files: List[str] = Field(description="Ключевые файлы")
    tech_stack: List[str] = Field(description="Технологический стек")


class AnalyzeResponse(BaseModel):
    """Структурированный ответ для анализа проекта.
    
    Example:
        {
            "structure": {...},
            "architecture_patterns": ["MVC", "Repository"],
            "strengths": ["Хорошая модульность"],
            "improvements": ["Добавить типы"],
            "overall_assessment": "Проект хорошо структурирован",
            "complexity_score": 0.6
        }
    """
    structure: ProjectStructure = Field(description="Структура проекта")
    architecture_patterns: List[str] = Field(
        default_factory=list, 
        description="Используемые паттерны"
    )
    strengths: List[str] = Field(
        default_factory=list, 
        description="Сильные стороны"
    )
    improvements: List[str] = Field(
        default_factory=list, 
        description="Рекомендации по улучшению"
    )
    overall_assessment: str = Field(description="Общая оценка проекта")
    complexity_score: float = Field(
        ge=0.0, le=1.0, 
        description="Оценка сложности 0-1"
    )
