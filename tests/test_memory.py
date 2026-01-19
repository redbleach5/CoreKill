"""Тесты для MemoryAgent."""
import pytest
from agents.memory import MemoryAgent


class TestMemoryAgent:
    """Тесты для класса MemoryAgent."""
    
    @pytest.fixture
    def agent(self):
        """Создаёт экземпляр MemoryAgent для тестов."""
        return MemoryAgent()
    
    def test_init(self, agent):
        """Тест инициализации агента."""
        assert agent is not None
        assert hasattr(agent, 'memory_rag')
        assert hasattr(agent, 'collection_name')
