"""Конфигурация для pytest."""
import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Добавляем корневую директорию в путь
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

# Импортируем factories для удобства
from tests.factories import (
    create_agent_state,
    create_intent_result,
    create_reflection_result,
    create_debug_result,
    TEST_MODELS,
    TEST_IDS,
)
from tests.test_utils import (
    create_mock_model_router,
    create_mock_llm,
    create_mock_agent_dependencies,
)

# Конфигурация pytest-asyncio
pytest_plugins = ('pytest_asyncio',)


def pytest_configure(config):
    """Регистрация кастомных маркеров."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )
    config.addinivalue_line(
        "markers", "frontend: тесты для frontend кода"
    )
    config.addinivalue_line(
        "markers", "backend: тесты для backend кода"
    )
    config.addinivalue_line(
        "markers", "integration: интеграционные тесты"
    )
    config.addinivalue_line(
        "markers", "unit: юнит-тесты"
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
    return create_intent_result()


@pytest.fixture
def mock_agent_state():
    """Мок AgentState для тестов."""
    return create_agent_state()


@pytest.fixture
def mock_model_router():
    """Мок ModelRouter для тестов."""
    return create_mock_model_router()


@pytest.fixture
def mock_llm():
    """Мок LLM для тестов."""
    return create_mock_llm()


@pytest.fixture
def mock_agent_dependencies():
    """Моки всех зависимостей агента."""
    return create_mock_agent_dependencies()


@pytest.fixture
def mock_ollama_client():
    """Fixture для мока Ollama клиента."""
    with patch('ollama.Client') as mock_client:
        mock_instance = Mock()
        mock_instance.generate = Mock(return_value={
            "model": TEST_MODELS["default"],
            "response": "test response",
            "done": True
        })
        mock_client.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_chromadb():
    """Fixture для мока ChromaDB."""
    with patch('chromadb.Client') as mock_client:
        mock_instance = Mock()
        mock_collection = Mock()
        mock_collection.query.return_value = {
            "ids": [[]],
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }
        mock_instance.get_or_create_collection.return_value = mock_collection
        mock_client.return_value = mock_instance
        yield mock_instance
