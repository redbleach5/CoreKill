"""Конфигурация для pytest."""
import pytest
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

# Конфигурация pytest-asyncio
pytest_plugins = ('pytest_asyncio',)


def pytest_configure(config):
    """Регистрация кастомных маркеров."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )


@pytest.fixture
def mock_ollama_response():
    """Мок ответ от Ollama."""
    return {
        "model": "codellama:7b",
        "response": "def hello():\n    return 'Hello, World!'",
        "done": True
    }


@pytest.fixture
def mock_task():
    """Мок задача."""
    return {
        "task": "Create a function that returns hello world",
        "model": "codellama:7b",
        "temperature": 0.25
    }


@pytest.fixture
def mock_intent_result():
    """Мок результат определения намерения."""
    return {
        "type": "create",
        "confidence": 0.95,
        "description": "Создание новой функции",
        "reasoning": "Пользователь просит создать функцию"
    }
