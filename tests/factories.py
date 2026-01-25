"""Factories для создания тестовых данных.

Централизованное место для создания тестовых объектов,
чтобы избежать дублирования и упростить поддержку.
"""
from typing import Any, Dict, Optional
from infrastructure.workflow_state import AgentState
from agents.intent import IntentResult
from agents.reflection import ReflectionResult
from agents.debugger import DebugResult


# Константы для тестов
TEST_MODELS = {
    "simple": "phi3:mini",
    "medium": "qwen2.5-coder:7b",
    "complex": "deepseek-r1:7b",
    "default": "test-model",
}

TEST_IDS = {
    "task": "test-task-123",
    "conversation": "test-conv-123",
    "message": "test-msg-123",
}


def create_agent_state(**overrides) -> AgentState:
    """Создаёт тестовый AgentState с дефолтными значениями.
    
    Args:
        **overrides: Поля для переопределения
        
    Returns:
        AgentState с дефолтными значениями + overrides
    """
    default: AgentState = {
        "task": "test task",
        "max_iterations": 3,
        "disable_web_search": False,
        "model": None,
        "temperature": 0.25,
        "intent_result": None,
        "plan": "",
        "context": "",
        "tests": "",
        "code": "",
        "validation_results": {},
        "debug_result": None,
        "reflection_result": None,
        "iteration": 0,
        "task_id": TEST_IDS["task"],
        "enable_sse": False,
        "file_path": None,
        "file_context": None,
        "interaction_mode": "code",
        "conversation_id": None,
        "conversation_history": None,
        "chat_response": None,
        "project_path": None,
        "file_extensions": None,
        "critic_report": None,
        "event_references": None,
    }
    default.update(overrides)
    return default


def create_intent_result(
    intent_type: str = "create",
    confidence: float = 0.95,
    **overrides
) -> IntentResult:
    """Создаёт тестовый IntentResult.
    
    Args:
        intent_type: Тип намерения
        confidence: Уверенность
        **overrides: Поля для переопределения
        
    Returns:
        IntentResult с тестовыми данными
    """
    default: Dict[str, Any] = {
        "type": intent_type,
        "confidence": confidence,
        "description": f"Тестовое описание для {intent_type}",
        "reasoning": f"Тестовое рассуждение для {intent_type}",
    }
    default.update(overrides)
    return IntentResult(**default)


def create_reflection_result(
    planning_score: float = 0.8,
    research_score: float = 0.85,
    testing_score: float = 0.9,
    coding_score: float = 0.88,
    overall_score: float = 0.875,
    **overrides
) -> ReflectionResult:
    """Создаёт тестовый ReflectionResult.
    
    Args:
        planning_score: Оценка планирования
        research_score: Оценка исследования
        testing_score: Оценка тестирования
        coding_score: Оценка кодирования
        overall_score: Общая оценка
        **overrides: Поля для переопределения
        
    Returns:
        ReflectionResult с тестовыми данными
    """
    default: Dict[str, Any] = {
        "planning_score": planning_score,
        "research_score": research_score,
        "testing_score": testing_score,
        "coding_score": coding_score,
        "overall_score": overall_score,
        "analysis": "Тестовый анализ",
        "improvements": "Тестовые улучшения",
        "should_retry": False,
    }
    default.update(overrides)
    return ReflectionResult(**default)


def create_debug_result(
    success: bool = True,
    error_type: str = "syntax",
    **overrides
) -> DebugResult:
    """Создаёт тестовый DebugResult.
    
    Args:
        success: Успешно ли исправлено
        error_type: Тип ошибки
        **overrides: Поля для переопределения
        
    Returns:
        DebugResult с тестовыми данными
    """
    default: Dict[str, Any] = {
        "success": success,
        "error_type": error_type,
        "error_message": "Тестовое сообщение об ошибке",
        "fixed_code": "def test():\n    pass" if success else None,
        "suggestions": ["Тестовое предложение"],
    }
    default.update(overrides)
    return DebugResult(**default)


def create_mock_ollama_response(
    response: str = "def hello():\n    return 'Hello, World!'",
    model: str = TEST_MODELS["default"],
    done: bool = True,
) -> Dict[str, Any]:
    """Создаёт мок ответ от Ollama.
    
    Args:
        response: Текст ответа
        model: Название модели
        done: Завершен ли ответ
        
    Returns:
        Словарь с мок ответом
    """
    return {
        "model": model,
        "response": response,
        "done": done,
    }


def create_mock_task(
    task: str = "Create a function that returns hello world",
    model: Optional[str] = None,
    temperature: float = 0.25,
) -> Dict[str, Any]:
    """Создаёт мок задачу.
    
    Args:
        task: Текст задачи
        model: Модель (если None, используется default)
        temperature: Температура
        
    Returns:
        Словарь с мок задачей
    """
    return {
        "task": task,
        "model": model or TEST_MODELS["default"],
        "temperature": temperature,
    }
