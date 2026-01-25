"""Общие утилиты для тестов.

Централизованные функции для создания моков и тестовых данных.
"""
from unittest.mock import Mock, patch, MagicMock
from typing import Optional, Dict, Any


def create_mock_model_router(model: str = "test-model") -> Mock:
    """Создаёт мок ModelRouter.
    
    Args:
        model: Название модели для возврата
        
    Returns:
        Мок ModelRouter
    """
    mock_router = Mock()
    mock_router.select_model.return_value = Mock(model=model)
    return mock_router


def create_mock_llm(
    model: str = "test-model",
    temperature: float = 0.25,
    response: str = "test response"
) -> Mock:
    """Создаёт мок LLM.
    
    Args:
        model: Название модели
        temperature: Температура
        response: Текст ответа
        
    Returns:
        Мок LLM
    """
    mock_llm = Mock()
    mock_llm.model = model
    mock_llm.temperature = temperature
    mock_llm.invoke = Mock(return_value=response)
    mock_llm.stream = Mock(return_value=iter([response]))
    return mock_llm


def create_mock_agent_dependencies(
    model: str = "test-model",
    temperature: float = 0.25
) -> Dict[str, Any]:
    """Создаёт моки для всех зависимостей агента.
    
    Args:
        model: Название модели
        temperature: Температура
        
    Returns:
        Словарь с моками зависимостей (без get_model_router, его нужно мокать отдельно)
    """
    return {
        "create_llm_for_stage": Mock(return_value=create_mock_llm(model, temperature)),
    }


# Fixtures определены в conftest.py для использования pytest
